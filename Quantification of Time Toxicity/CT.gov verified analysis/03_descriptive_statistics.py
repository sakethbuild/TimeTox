#!/usr/bin/env python3
"""
Step 3: Descriptive Statistics and Summary Tables.

Generates Table 1 (cohort characteristics) and basic distribution summaries.
"""

import os
import sys
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import DATA_DIR, TABLES_DIR, TIMEPOINTS, TT_THRESHOLDS


def iqr_str(series):
    """Format median (IQR) as string."""
    s = series.dropna()
    if len(s) == 0:
        return "N/A"
    med = s.median()
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    return f"{med:.1f} ({q1:.1f}-{q3:.1f})"


def main():
    print("=" * 60)
    print("STEP 3: Descriptive Statistics")
    print("=" * 60)

    # Load data
    trials = pd.read_csv(os.path.join(DATA_DIR, "enriched_trials.csv"))
    arms = pd.read_csv(os.path.join(DATA_DIR, "enriched_arms.csv"))

    interv_arms = arms[arms["intervention_type"] == "intervention"]
    control_arms = arms[arms["intervention_type"] == "control"]

    # ==========================================
    # COHORT OVERVIEW
    # ==========================================
    print("\n" + "=" * 50)
    print("COHORT OVERVIEW")
    print("=" * 50)
    print(f"Total unique trials: {len(trials)}")
    print(f"Total arms: {len(arms)}")
    print(f"  Intervention arms: {len(interv_arms)}")
    print(f"  Control arms: {len(control_arms)}")
    n_paired = trials.dropna(subset=["intervention_12_months", "control_12_months"]).shape[0]
    print(f"  Trials with matched intervention+control: {n_paired}")

    # ==========================================
    # TIME TOXICITY SUMMARY
    # ==========================================
    print("\n" + "=" * 50)
    print("TIME TOXICITY AT 12 MONTHS")
    print("=" * 50)
    print(f"Intervention arms — Median (IQR): {iqr_str(interv_arms['12_months'])}")
    print(f"Control arms — Median (IQR): {iqr_str(control_arms['12_months'])}")

    delta = trials["delta_12_months"].dropna()
    print(f"\nDelta TT (Intervention - Control):")
    print(f"  Median (IQR): {iqr_str(delta)}")
    print(f"  Mean ± SD: {delta.mean():.1f} ± {delta.std():.1f}")
    print(f"  Range: [{delta.min():.0f}, {delta.max():.0f}]")
    print(f"  Trials with positive delta (intervention more burdensome): {(delta > 0).sum()} ({100*(delta > 0).mean():.1f}%)")
    print(f"  Trials with zero delta: {(delta == 0).sum()} ({100*(delta == 0).mean():.1f}%)")
    print(f"  Trials with negative delta (control more burdensome): {(delta < 0).sum()} ({100*(delta < 0).mean():.1f}%)")

    # ==========================================
    # ZERO-DELTA DIAGNOSTIC
    # ==========================================
    print("\n" + "=" * 50)
    print("ZERO-DELTA DIAGNOSTIC")
    print("=" * 50)
    n_total_delta = len(delta)
    n_zero = (delta == 0).sum()
    n_nonzero = (delta != 0).sum()
    print(f"  Total trials with delta: {n_total_delta}")
    print(f"  Trials with delta == 0: {n_zero} ({100*n_zero/n_total_delta:.1f}%)")
    print(f"  Trials with delta != 0: {n_nonzero} ({100*n_nonzero/n_total_delta:.1f}%)")

    # Confirm zero deltas arise from equal non-zero values
    paired = trials.dropna(subset=["intervention_12_months", "control_12_months"])
    zero_delta_trials = paired[paired["delta_12_months"] == 0]
    both_zero = zero_delta_trials[
        (zero_delta_trials["intervention_12_months"] == 0) &
        (zero_delta_trials["control_12_months"] == 0)
    ]
    print(f"\n  Zero-delta breakdown:")
    print(f"    Both arms TT > 0 but equal: {len(zero_delta_trials) - len(both_zero)}")
    print(f"    Both arms TT == 0: {len(both_zero)}")

    # Most common equal value pairs
    print(f"\n  Top 10 most common (interv, control) pairs for delta==0:")
    value_pairs = zero_delta_trials.groupby(
        ["intervention_12_months", "control_12_months"]
    ).size().sort_values(ascending=False).head(10)
    for (iv, cv), count in value_pairs.items():
        print(f"    ({iv:.0f}, {cv:.0f}): {count} trials")

    # Non-zero delta summary
    nonzero_delta = delta[delta != 0]
    if len(nonzero_delta) > 0:
        print(f"\n  Among non-zero deltas (N={len(nonzero_delta)}):")
        print(f"    Median: {nonzero_delta.median():.1f}")
        print(f"    IQR: ({nonzero_delta.quantile(0.25):.1f} to {nonzero_delta.quantile(0.75):.1f})")
        print(f"    Mean ± SD: {nonzero_delta.mean():.1f} ± {nonzero_delta.std():.1f}")
        print(f"    Range: [{nonzero_delta.min():.0f}, {nonzero_delta.max():.0f}]")

    # ==========================================
    # EXTREME TT THRESHOLDS
    # ==========================================
    print("\n" + "=" * 50)
    print("EXTREME TT THRESHOLDS")
    print("=" * 50)

    # Use primary arms only (pos_idx=0) for threshold analysis
    primary_interv = interv_arms[interv_arms["pos_idx"] == 0]
    primary_ctrl = control_arms[control_arms["pos_idx"] == 0]

    threshold_rows = []
    for threshold in TT_THRESHOLDS:
        n_iv = (primary_interv["12_months"] > threshold).sum()
        pct_iv = 100 * n_iv / len(primary_interv["12_months"].dropna())
        n_cv = (primary_ctrl["12_months"] > threshold).sum()
        pct_cv = 100 * n_cv / len(primary_ctrl["12_months"].dropna())
        n_delta = (delta.abs() > threshold).sum()
        pct_delta = 100 * n_delta / len(delta)
        print(f"  >{threshold} days:")
        print(f"    Intervention (pos_idx=0): {n_iv} ({pct_iv:.1f}%)")
        print(f"    Control (pos_idx=0): {n_cv} ({pct_cv:.1f}%)")
        print(f"    |Delta| > {threshold}: {n_delta} ({pct_delta:.1f}%)")
        threshold_rows.append({
            "Threshold": f">{threshold} days",
            "Intervention_N": n_iv, "Intervention_pct": round(pct_iv, 1),
            "Control_N": n_cv, "Control_pct": round(pct_cv, 1),
            "AbsDelta_N": n_delta, "AbsDelta_pct": round(pct_delta, 1),
        })

    thresh_df = pd.DataFrame(threshold_rows)
    thresh_df.to_csv(os.path.join(TABLES_DIR, "table_threshold_analysis.csv"), index=False)
    print(f"  Saved: tables/table_threshold_analysis.csv")

    # ==========================================
    # INTENSITY SCORE
    # ==========================================
    print("\n" + "=" * 50)
    print("INTENSITY SCORE (visits/month)")
    print("=" * 50)
    print(f"Intervention arms: {iqr_str(interv_arms['intensity_score'])}")
    print(f"Control arms: {iqr_str(control_arms['intensity_score'])}")

    # ==========================================
    # TT TRAJECTORY
    # ==========================================
    print("\n" + "=" * 50)
    print("TT TRAJECTORY — Median at Each Timepoint")
    print("=" * 50)
    print(f"{'Timepoint':<15} {'Intervention':<20} {'Control':<20}")
    print("-" * 55)
    for tp in TIMEPOINTS:
        iv = interv_arms[tp].median()
        cv = control_arms[tp].median()
        print(f"{tp:<15} {iv:<20.1f} {cv:<20.1f}")

    # ==========================================
    # DISTRIBUTION BY SUBGROUPS
    # ==========================================
    print("\n" + "=" * 50)
    print("DISTRIBUTION BY SPONSORSHIP")
    print("=" * 50)
    for sponsor, grp in trials.groupby("sponsor_binary"):
        n = len(grp)
        iv_tt = grp["intervention_12_months"].dropna()
        print(f"  {sponsor}: N={n}, Intervention 12mo TT = {iqr_str(iv_tt)}")

    print("\n" + "=" * 50)
    print("DISTRIBUTION BY DISEASE SITE")
    print("=" * 50)
    for site, grp in trials.groupby("disease_site"):
        n = len(grp)
        iv_tt = grp["intervention_12_months"].dropna()
        print(f"  {site}: N={n}, Intervention 12mo TT = {iqr_str(iv_tt)}")

    print("\n" + "=" * 50)
    print("DISTRIBUTION BY TREATMENT MODALITY")
    print("=" * 50)
    for modality, grp in trials.groupby("treatment_modality"):
        n = len(grp)
        iv_tt = grp["intervention_12_months"].dropna()
        print(f"  {modality}: N={n}, Intervention 12mo TT = {iqr_str(iv_tt)}")

    print("\n" + "=" * 50)
    print("DISTRIBUTION BY TRIAL START YEAR")
    print("=" * 50)
    trials["year_bin"] = pd.cut(trials["start_year"], bins=[1998, 2004, 2008, 2012, 2016, 2020],
                                labels=["1999-2004", "2005-2008", "2009-2012", "2013-2016", "2017-2020"])
    for ybin, grp in trials.groupby("year_bin"):
        n = len(grp)
        iv_tt = grp["intervention_12_months"].dropna()
        print(f"  {ybin}: N={n}, Intervention 12mo TT = {iqr_str(iv_tt)}")

    # ==========================================
    # BUILD TABLE 1
    # ==========================================
    print("\n--- Building Table 1 ---")
    rows = []

    rows.append({"Characteristic": "Total trials", "Value": str(len(trials))})
    rows.append({"Characteristic": "Total arms", "Value": str(len(arms))})
    rows.append({"Characteristic": "  Intervention", "Value": str(len(interv_arms))})
    rows.append({"Characteristic": "  Control", "Value": str(len(control_arms))})
    rows.append({"Characteristic": "Matched pairs", "Value": str(n_paired)})
    rows.append({"Characteristic": "", "Value": ""})

    rows.append({"Characteristic": "12-Month TT, median (IQR)", "Value": ""})
    rows.append({"Characteristic": "  Intervention arms", "Value": iqr_str(interv_arms["12_months"])})
    rows.append({"Characteristic": "  Control arms", "Value": iqr_str(control_arms["12_months"])})
    rows.append({"Characteristic": "  Delta (Intervention - Control)", "Value": iqr_str(delta)})
    rows.append({"Characteristic": "", "Value": ""})

    rows.append({"Characteristic": "Delta TT Diagnostic", "Value": ""})
    rows.append({"Characteristic": "  Trials with zero delta",
                  "Value": f"{n_zero} ({100*n_zero/n_total_delta:.1f}%)"})
    rows.append({"Characteristic": "  Trials with non-zero delta",
                  "Value": f"{n_nonzero} ({100*n_nonzero/n_total_delta:.1f}%)"})
    if len(nonzero_delta) > 0:
        rows.append({"Characteristic": "  Non-zero delta, median (IQR)",
                      "Value": f"{nonzero_delta.median():.1f} ({nonzero_delta.quantile(0.25):.1f}-{nonzero_delta.quantile(0.75):.1f})"})
    rows.append({"Characteristic": "", "Value": ""})

    rows.append({"Characteristic": "Extreme TT (Intervention arms)", "Value": ""})
    for threshold in TT_THRESHOLDS:
        n_t = (primary_interv["12_months"] > threshold).sum()
        pct_t = 100 * n_t / len(primary_interv["12_months"].dropna())
        rows.append({"Characteristic": f"  >{threshold} days",
                      "Value": f"{n_t} ({pct_t:.1f}%)"})
    rows.append({"Characteristic": "", "Value": ""})

    rows.append({"Characteristic": "Intensity Score (days/month), median (IQR)", "Value": ""})
    rows.append({"Characteristic": "  Intervention arms", "Value": iqr_str(interv_arms["intensity_score"])})
    rows.append({"Characteristic": "  Control arms", "Value": iqr_str(control_arms["intensity_score"])})
    rows.append({"Characteristic": "", "Value": ""})

    rows.append({"Characteristic": "Trial Start Year, median (range)", "Value":
                  f"{int(trials['start_year'].median())} ({int(trials['start_year'].min())}-{int(trials['start_year'].max())})"})
    rows.append({"Characteristic": "", "Value": ""})

    rows.append({"Characteristic": "Sponsorship, N (%)", "Value": ""})
    for sponsor in ["Industry", "Non-Industry"]:
        n = (trials["sponsor_binary"] == sponsor).sum()
        rows.append({"Characteristic": f"  {sponsor}", "Value": f"{n} ({100*n/len(trials):.1f}%)"})
    rows.append({"Characteristic": "", "Value": ""})

    rows.append({"Characteristic": "Disease Site, N (%)", "Value": ""})
    for site, n in trials["disease_site"].value_counts().sort_values(ascending=False).items():
        rows.append({"Characteristic": f"  {site}", "Value": f"{n} ({100*n/len(trials):.1f}%)"})
    rows.append({"Characteristic": "", "Value": ""})

    rows.append({"Characteristic": "Treatment Modality, N (%)", "Value": ""})
    for mod, n in trials["treatment_modality"].value_counts().sort_values(ascending=False).items():
        rows.append({"Characteristic": f"  {mod}", "Value": f"{n} ({100*n/len(trials):.1f}%)"})

    table1 = pd.DataFrame(rows)
    table1.to_csv(os.path.join(TABLES_DIR, "table1_cohort_characteristics.csv"), index=False)

    # LaTeX version
    with open(os.path.join(TABLES_DIR, "table1_cohort_characteristics.tex"), "w") as f:
        f.write("\\begin{table}[htbp]\n")
        f.write("\\centering\n")
        f.write("\\caption{Cohort Characteristics}\n")
        f.write("\\begin{tabular}{lc}\n")
        f.write("\\toprule\n")
        f.write("Characteristic & Value \\\\\n")
        f.write("\\midrule\n")
        for _, row in table1.iterrows():
            char = row["Characteristic"].replace("%", "\\%").replace("_", "\\_")
            val = str(row["Value"]).replace("%", "\\%").replace("_", "\\_")
            if char == "":
                f.write("\\addlinespace\n")
            else:
                f.write(f"{char} & {val} \\\\\n")
        f.write("\\bottomrule\n")
        f.write("\\end{tabular}\n")
        f.write("\\end{table}\n")

    print(f"  Saved: tables/table1_cohort_characteristics.csv")
    print(f"  Saved: tables/table1_cohort_characteristics.tex")

    print("\n" + "=" * 60)
    print("STEP 3 COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
