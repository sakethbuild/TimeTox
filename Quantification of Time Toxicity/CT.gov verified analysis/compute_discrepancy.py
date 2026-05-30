#!/usr/bin/env python3
"""
Phase 1, Step 4: Compute discrepancy metrics + per-trial change log.

Simulates the trial-level re-derivation (pos_idx==0 of each corrected label,
sorted by 12_months) to compute the HEADLINE-IMPACT rate: how many trials'
delta_12_months actually changes after correction.

Outputs:
  tables/match_quality_summary.csv
  tables/per_trial_change_log.csv
  DISCREPANCY_REPORT.md
"""

import os
import sys
import math
import warnings

warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
TABLES = os.path.join(BASE, "tables")

TIMEPOINTS = ["screening", "1_month", "3_months", "6_months", "9_months", "12_months"]


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))) / denom
    return (max(0, center - half), min(1, center + half))


def derive_pos0(arms_sub, label_col):
    """Given arm rows with a label column, return (interv_12mo, control_12mo) using
    the pos_idx==0 (lowest 12mo) arm of each label, mirroring 01_build_consensus."""
    res = {}
    for lab in ("intervention", "control"):
        sub = arms_sub[arms_sub[label_col] == lab].sort_values("tt_12mo")
        res[lab] = sub["tt_12mo"].iloc[0] if len(sub) else np.nan
    return res["intervention"], res["control"]


def main():
    m = pd.read_csv(os.path.join(TABLES, "ctgov_arm_matches.csv"))

    # --- ARM-LEVEL discrepancy ---
    # Denominator: confidently matched arms (confident, confident_2arm). Exclude uncertain,
    # count_mismatch*, ctgov_404, no_armgroups, no_nct.
    confident_mask = m["match_status"].isin(["confident", "confident_2arm"])
    conf = m[confident_mask]
    n_arms_conf = len(conf)
    n_arms_flip = int(conf["label_flipped"].sum())
    arm_lo, arm_hi = wilson_ci(n_arms_flip, n_arms_conf)

    # --- per-TRIAL analysis ---
    trial_rows = []
    for (fn, nct), g in m.groupby(["filename", "nct"]):
        n_pipe = int(g["n_pipeline_arms"].iloc[0])
        n_ct = int(g["n_ctgov_arms"].iloc[0])
        status_set = set(g["match_status"])
        # trial-level status
        if {"ctgov_404", "no_nct"} & status_set:
            tstatus = "unverifiable"
        elif "ctgov_no_armgroups" in status_set:
            tstatus = "ctgov_no_armgroups"
        elif "count_mismatch" in status_set or "count_mismatch_leftover" in status_set:
            tstatus = "count_mismatch"
        elif "uncertain" in status_set:
            tstatus = "uncertain"
        else:
            tstatus = "confident"

        any_flip = bool(g["label_flipped"].any())

        # corrected labels: use ctgov_label where present, else original
        g = g.copy()
        g["corrected_label"] = g["ctgov_label"].fillna(g["original_label"])

        # original derived delta (from original labels)
        iv0, ct0 = derive_pos0(g.rename(columns={"original_label": "_l"}), "_l")
        delta0 = (iv0 - ct0) if (pd.notna(iv0) and pd.notna(ct0)) else np.nan
        # corrected derived delta
        iv1, ct1 = derive_pos0(g.rename(columns={"corrected_label": "_l"}), "_l")
        delta1 = (iv1 - ct1) if (pd.notna(iv1) and pd.notna(ct1)) else np.nan

        # headline impact: delta changed (incl NaN<->value transitions)
        if pd.isna(delta0) and pd.isna(delta1):
            delta_changed = False
        elif pd.isna(delta0) or pd.isna(delta1):
            delta_changed = True
        else:
            delta_changed = abs(delta0 - delta1) > 1e-9

        # edge: corrected labels yield no intervention or no control
        n_corr_iv = int((g["corrected_label"] == "intervention").sum())
        n_corr_ct = int((g["corrected_label"] == "control").sum())

        trial_rows.append({
            "filename": fn, "nct": nct, "trial_status": tstatus,
            "n_pipeline_arms": n_pipe, "n_ctgov_arms": n_ct,
            "count_mismatch": n_pipe != n_ct,
            "any_label_flip": any_flip,
            "iv_12mo_orig": iv0, "ct_12mo_orig": ct0, "delta12_orig": delta0,
            "iv_12mo_corr": iv1, "ct_12mo_corr": ct1, "delta12_corr": delta1,
            "delta12_changed": delta_changed,
            "n_corr_intervention_arms": n_corr_iv, "n_corr_control_arms": n_corr_ct,
            "corr_no_intervention": n_corr_iv == 0,
            "corr_no_control": n_corr_ct == 0,
            "min_confidence": round(float(g["confidence"].min()), 3),
        })

    tl = pd.DataFrame(trial_rows)
    tl.to_csv(os.path.join(TABLES, "per_trial_change_log.csv"), index=False)

    n_trials = len(tl)
    verifiable = tl[~tl["trial_status"].isin(["unverifiable", "ctgov_no_armgroups"])]
    n_verif = len(verifiable)

    n_trial_flip = int(verifiable["any_label_flip"].sum())
    tflip_lo, tflip_hi = wilson_ci(n_trial_flip, n_verif)

    n_delta_changed = int(verifiable["delta12_changed"].sum())
    dimp_lo, dimp_hi = wilson_ci(n_delta_changed, n_verif)

    n_count_mismatch = int(tl["count_mismatch"].sum())
    n_uncertain = int((tl["trial_status"] == "uncertain").sum())
    n_unverifiable = int((tl["trial_status"] == "unverifiable").sum())
    n_no_arms = int((tl["trial_status"] == "ctgov_no_armgroups").sum())
    n_corr_no_iv = int(tl["corr_no_intervention"].sum())
    n_corr_no_ct = int(tl["corr_no_control"].sum())

    # --- summary table ---
    summary = pd.DataFrame([
        {"metric": "Total trials", "value": n_trials},
        {"metric": "Total arm records", "value": len(m)},
        {"metric": "Arm-level: confidently matched arms", "value": n_arms_conf},
        {"metric": "Arm-level: label flips (confident)", "value": n_arms_flip},
        {"metric": "Arm-level discrepancy %", "value": round(100*n_arms_flip/n_arms_conf, 2)},
        {"metric": "Arm-level discrepancy 95% CI", "value": f"{100*arm_lo:.1f}-{100*arm_hi:.1f}%"},
        {"metric": "Verifiable trials (denom for trial rates)", "value": n_verif},
        {"metric": "Trial-level label-flip count", "value": n_trial_flip},
        {"metric": "Trial-level label-flip %", "value": round(100*n_trial_flip/n_verif, 2)},
        {"metric": "Trial-level label-flip 95% CI", "value": f"{100*tflip_lo:.1f}-{100*tflip_hi:.1f}%"},
        {"metric": "HEADLINE-IMPACT: delta12 changed count", "value": n_delta_changed},
        {"metric": "HEADLINE-IMPACT %", "value": round(100*n_delta_changed/n_verif, 2)},
        {"metric": "HEADLINE-IMPACT 95% CI", "value": f"{100*dimp_lo:.1f}-{100*dimp_hi:.1f}%"},
        {"metric": "Count-mismatch trials", "value": n_count_mismatch},
        {"metric": "Uncertain-match trials", "value": n_uncertain},
        {"metric": "Unverifiable trials (404/no NCT)", "value": n_unverifiable},
        {"metric": "CT.gov no-armgroups trials", "value": n_no_arms},
        {"metric": "Trials w/ NO intervention arm after correction", "value": n_corr_no_iv},
        {"metric": "Trials w/ NO control arm after correction", "value": n_corr_no_ct},
    ])
    summary.to_csv(os.path.join(TABLES, "match_quality_summary.csv"), index=False)

    # stratify discrepancy by arm-count class
    tl["arm_class"] = np.where(tl["n_pipeline_arms"] == 2, "2-arm", "multi-arm")
    strat = tl[tl["trial_status"].isin(["confident", "uncertain", "count_mismatch"])].groupby("arm_class").agg(
        trials=("filename", "count"),
        flips=("any_label_flip", "sum"),
        delta_changed=("delta12_changed", "sum"),
    )
    strat["flip_%"] = (100*strat["flips"]/strat["trials"]).round(1)
    strat["delta_changed_%"] = (100*strat["delta_changed"]/strat["trials"]).round(1)

    # --- markdown report ---
    md = []
    md.append("# CT.gov Verification — Phase 1 Discrepancy Report\n")
    md.append(f"Snapshot: all 644 NCTs fetched from ClinicalTrials.gov v2 API (0 errors, 0 404s).\n")
    md.append("## Headline numbers\n")
    md.append(f"- **Arm-level discrepancy: {n_arms_flip}/{n_arms_conf} = {100*n_arms_flip/n_arms_conf:.1f}%** "
              f"(95% CI {100*arm_lo:.1f}–{100*arm_hi:.1f}%) of confidently-matched arms have a flipped label.")
    md.append(f"- **Trial-level label-flip rate: {n_trial_flip}/{n_verif} = {100*n_trial_flip/n_verif:.1f}%** "
              f"(95% CI {100*tflip_lo:.1f}–{100*tflip_hi:.1f}%) of verifiable trials have ≥1 arm relabeled.")
    md.append(f"- **Headline-impact rate: {n_delta_changed}/{n_verif} = {100*n_delta_changed/n_verif:.1f}%** "
              f"(95% CI {100*dimp_lo:.1f}–{100*dimp_hi:.1f}%) of verifiable trials have a CHANGED 12-month delta "
              f"(the rest are inert because intervention and control share the same TT, or labels didn't move).")
    md.append("")
    md.append("## Match-quality / data-integrity counts\n")
    md.append(f"- **Count-mismatch trials (CT.gov arm count ≠ pipeline): {n_count_mismatch}**")
    md.append(f"- Uncertain-match trials (flagged, will get sensitivity re-run): {n_uncertain}")
    md.append(f"- Unverifiable (404 / no NCT): {n_unverifiable}")
    md.append(f"- CT.gov returned no arm groups: {n_no_arms}")
    md.append(f"- Trials with NO intervention arm after CT.gov mapping: {n_corr_no_iv}")
    md.append(f"- Trials with NO control arm after CT.gov mapping: {n_corr_no_ct}")
    md.append("")
    md.append("## Discrepancy stratified by arm count\n")
    md.append(strat.to_markdown())
    md.append("")
    md.append("## Interpretation\n")
    md.append(f"Of the {n_trial_flip} trials with a relabeled arm, only **{n_delta_changed}** actually change "
              f"a headline number (the 12-month delta), because ~62% of trials have identical intervention/control "
              f"TT where a label swap is numerically inert. The arm-level flip rate ({100*n_arms_flip/n_arms_conf:.1f}%) "
              f"is the cleanest measure of how often the pipeline's intervention/control assignment disagreed with CT.gov.")
    with open(os.path.join(BASE, "DISCREPANCY_REPORT.md"), "w") as f:
        f.write("\n".join(md))

    # console
    print("="*64)
    print("DISCREPANCY SUMMARY")
    print("="*64)
    print(summary.to_string(index=False))
    print("\nStratified by arm count:")
    print(strat.to_string())


if __name__ == "__main__":
    main()
