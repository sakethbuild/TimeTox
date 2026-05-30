#!/usr/bin/env python3
"""
Step 8: Validation and Sensitivity Analyses.

Addresses methodological concerns:
- 67% zero-delta phenomenon (characterization + chi-squared tests)
- Multiple control arm audit
- Intervention-only trials audit
- Sensitivity: key analyses on non-zero-delta subset only
- Sensitivity: all arms vs pos_idx=0 for regression
- Arm labeling spot check (TT inversions, drug name audit, multi-control hypothesis)
"""

import os
import sys
import re
import warnings
import pandas as pd
import numpy as np
from scipy import stats
import statsmodels.api as sm
from statsmodels.formula.api import logit as logit_formula
from sklearn.metrics import roc_auc_score

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import DATA_DIR, TABLES_DIR, MIN_GROUP_SIZE, DRUG_CLASSES

warnings.filterwarnings("ignore")


def main():
    print("=" * 60)
    print("STEP 8: Validation and Sensitivity Analyses")
    print("=" * 60)

    trials = pd.read_csv(os.path.join(DATA_DIR, "enriched_trials.csv"))
    arms_all = pd.read_csv(os.path.join(DATA_DIR, "enriched_arms.csv"))
    consensus_arms = pd.read_csv(os.path.join(DATA_DIR, "consensus_arms.csv"))

    validation_results = []

    # ==========================================
    # SECTION A: ZERO-DELTA CHARACTERIZATION
    # ==========================================
    print("\n" + "=" * 50)
    print("SECTION A: Zero-Delta Characterization")
    print("=" * 50)

    paired = trials.dropna(subset=["delta_12_months"])
    paired["is_zero_delta"] = (paired["delta_12_months"] == 0).astype(int)
    n_zero = paired["is_zero_delta"].sum()
    n_nonzero = len(paired) - n_zero
    print(f"  Zero-delta trials: {n_zero} ({100*n_zero/len(paired):.1f}%)")
    print(f"  Non-zero-delta trials: {n_nonzero} ({100*n_nonzero/len(paired):.1f}%)")

    # Chi-squared: are zero-delta trials systematically different?
    categorical_vars = [
        ("sponsor_binary", "Sponsorship"),
        ("disease_site", "Disease Site"),
        ("treatment_modality", "Treatment Modality"),
    ]

    print(f"\n  Chi-squared tests: Zero-delta vs Non-zero-delta")
    print(f"  {'Variable':<25} {'Chi2':>8} {'p-value':>10} {'Conclusion':<30}")
    print(f"  {'─'*75}")

    for col, label in categorical_vars:
        ct = pd.crosstab(paired[col], paired["is_zero_delta"])
        if ct.shape[0] >= 2 and ct.shape[1] >= 2:
            chi2, p, dof, expected = stats.chi2_contingency(ct)
            conclusion = "DIFFERENT" if p < 0.05 else "Not different"
            print(f"  {label:<25} {chi2:>8.2f} {p:>10.4f} {conclusion}")
            validation_results.append({
                "Test": f"Zero-Delta Chi2: {label}",
                "Statistic": chi2, "p_value": p,
                "Conclusion": conclusion,
            })

    # Continuous: publication year
    zero_years = paired[paired["is_zero_delta"] == 1]["start_year"].dropna()
    nonzero_years = paired[paired["is_zero_delta"] == 0]["start_year"].dropna()
    u_year, p_year = stats.mannwhitneyu(zero_years, nonzero_years, alternative="two-sided")
    conclusion = "DIFFERENT" if p_year < 0.05 else "Not different"
    print(f"  {'Trial Start Year':<25} {u_year:>8.0f} {p_year:>10.4f} {conclusion}")
    print(f"    Zero-delta median year: {zero_years.median():.0f}")
    print(f"    Non-zero median year: {nonzero_years.median():.0f}")
    validation_results.append({
        "Test": "Zero-Delta Mann-Whitney: Trial Start Year",
        "Statistic": u_year, "p_value": p_year,
        "Conclusion": conclusion,
    })

    # Proportional breakdown
    print(f"\n  Proportional breakdown by Sponsorship:")
    for delta_status, delta_label in [(1, "Zero-delta"), (0, "Non-zero-delta")]:
        subset = paired[paired["is_zero_delta"] == delta_status]
        n = len(subset)
        ind_pct = 100 * (subset["sponsor_binary"] == "Industry").mean()
        print(f"    {delta_label} (N={n}): Industry={ind_pct:.1f}%")

    print(f"\n  Proportional breakdown by Treatment Modality:")
    for delta_status, delta_label in [(1, "Zero-delta"), (0, "Non-zero-delta")]:
        subset = paired[paired["is_zero_delta"] == delta_status]
        n = len(subset)
        top_mods = subset["treatment_modality"].value_counts().head(5)
        print(f"    {delta_label} (N={n}):")
        for mod, count in top_mods.items():
            print(f"      {mod}: {count} ({100*count/n:.1f}%)")

    # TT level comparison
    print(f"\n  TT level comparison:")
    zero_tt = paired[paired["is_zero_delta"] == 1]["intervention_12_months"].dropna()
    nonzero_tt = paired[paired["is_zero_delta"] == 0]["intervention_12_months"].dropna()
    print(f"    Zero-delta median TT: {zero_tt.median():.1f} (IQR: {zero_tt.quantile(0.25):.1f}-{zero_tt.quantile(0.75):.1f})")
    print(f"    Non-zero median TT: {nonzero_tt.median():.1f} (IQR: {nonzero_tt.quantile(0.25):.1f}-{nonzero_tt.quantile(0.75):.1f})")

    # ==========================================
    # SECTION B: MULTI-CONTROL-ARM AUDIT
    # ==========================================
    print("\n" + "=" * 50)
    print("SECTION B: Multi-Control-Arm Audit")
    print("=" * 50)

    ctrl_arms = consensus_arms[consensus_arms["intervention_type"] == "control"]
    ctrl_per_trial = ctrl_arms.groupby("filename").size()
    multi_ctrl = ctrl_per_trial[ctrl_per_trial > 1]
    print(f"  Protocols with 1 control: {(ctrl_per_trial == 1).sum()}")
    print(f"  Protocols with 2 controls: {(ctrl_per_trial == 2).sum()}")
    print(f"  Protocols with 3 controls: {(ctrl_per_trial == 3).sum()}")

    audit_rows = []
    print(f"\n  Multi-control arm details:")
    for filename in multi_ctrl.index:
        arms_for_trial = consensus_arms[consensus_arms["filename"] == filename]
        ctrl_for_trial = arms_for_trial[arms_for_trial["intervention_type"] == "control"]
        tt_values = ctrl_for_trial["12_months"].values
        tt_spread = tt_values.max() - tt_values.min()
        n_ctrl = len(ctrl_for_trial)
        print(f"    {filename[:50]}: {n_ctrl} controls, TT range={tt_values.min():.0f}-{tt_values.max():.0f} (spread={tt_spread:.0f})")
        audit_rows.append({
            "filename": filename, "n_control_arms": n_ctrl,
            "ctrl_tt_min": tt_values.min(), "ctrl_tt_max": tt_values.max(),
            "ctrl_tt_spread": tt_spread,
        })

    # Flag concerning cases (spread > 20 days)
    high_spread = [r for r in audit_rows if r["ctrl_tt_spread"] > 20]
    print(f"\n  Concerning cases (control spread > 20 days): {len(high_spread)}")
    for r in high_spread:
        print(f"    {r['filename'][:50]}: spread={r['ctrl_tt_spread']:.0f}")

    # ==========================================
    # SECTION C: INTERVENTION-ONLY TRIALS
    # ==========================================
    print("\n" + "=" * 50)
    print("SECTION C: Intervention-Only Trials Audit")
    print("=" * 50)

    interv_only = trials[trials["control_12_months"].isna() & trials["intervention_12_months"].notna()]
    print(f"  Total intervention-only trials: {len(interv_only)}")
    for _, row in interv_only.iterrows():
        fname = row["filename"][:60]
        n_arms = len(arms_all[arms_all["filename"] == row["filename"]])
        print(f"\n    {fname}")
        print(f"      Disease Site: {row.get('disease_site', 'N/A')}")
        print(f"      Treatment: {row.get('treatment_modality', 'N/A')}")
        print(f"      Sponsor: {row.get('sponsor_binary', 'N/A')}")
        print(f"      Intervention TT: {row['intervention_12_months']:.0f} days")
        print(f"      Arms in dataset: {n_arms}")
        # Show arm details
        trial_arms = arms_all[arms_all["filename"] == row["filename"]]
        for _, arm in trial_arms.iterrows():
            print(f"        {arm.get('arm_name', 'N/A')[:40]}: {arm['intervention_type']}, "
                  f"12mo={arm['12_months']:.0f}")

    # ==========================================
    # SECTION D: SENSITIVITY — NON-ZERO-DELTA SUBSET
    # ==========================================
    print("\n" + "=" * 50)
    print("SECTION D: Sensitivity Analyses on Non-Zero-Delta Subset")
    print("=" * 50)

    nonzero = paired[paired["delta_12_months"] != 0].copy()
    print(f"  Non-zero delta subset: {len(nonzero)} trials")

    # D1: Sponsorship Wilcoxon on non-zero subset
    print(f"\n  --- D1: Sponsorship (non-zero delta only) ---")
    ind_nz = nonzero[nonzero["sponsor_binary"] == "Industry"]["intervention_12_months"].dropna()
    noind_nz = nonzero[nonzero["sponsor_binary"] == "Non-Industry"]["intervention_12_months"].dropna()
    if len(ind_nz) >= 5 and len(noind_nz) >= 5:
        u, p = stats.mannwhitneyu(ind_nz, noind_nz, alternative="two-sided")
        print(f"    Industry (N={len(ind_nz)}): median={ind_nz.median():.1f}")
        print(f"    Non-Industry (N={len(noind_nz)}): median={noind_nz.median():.1f}")
        print(f"    Mann-Whitney U={u:.0f}, p={p:.4f}")
        print(f"    {'SIGNIFICANT' if p < 0.05 else 'Not significant'}")
        validation_results.append({
            "Test": "Sensitivity: Sponsorship (non-zero delta)",
            "Statistic": u, "p_value": p,
            "Conclusion": "Significant" if p < 0.05 else "Not significant",
        })

    # D2: Temporal trend on non-zero subset
    print(f"\n  --- D2: Temporal Trend (non-zero delta only) ---")
    temporal_nz = nonzero.dropna(subset=["intervention_12_months", "start_year"])
    if len(temporal_nz) >= 10:
        y_nz = temporal_nz["intervention_12_months"]
        x_nz = temporal_nz["start_year"]
        rho_nz, p_sp_nz = stats.spearmanr(x_nz, y_nz)
        X_nz = sm.add_constant(x_nz)
        model_nz = sm.OLS(y_nz, X_nz).fit()
        slope_nz = model_nz.params.iloc[1]
        p_ols_nz = model_nz.pvalues.iloc[1]
        print(f"    OLS Slope = {slope_nz:.3f} d/yr, p = {p_ols_nz:.4f}")
        print(f"    Spearman rho = {rho_nz:.3f}, p = {p_sp_nz:.4f}")
        print(f"    {'SIGNIFICANT' if p_ols_nz < 0.05 else 'Not significant'}")
        validation_results.append({
            "Test": "Sensitivity: Temporal Trend (non-zero delta)",
            "Statistic": slope_nz, "p_value": p_ols_nz,
            "Conclusion": "Significant" if p_ols_nz < 0.05 else "Not significant",
        })

    # D3: Disease site Kruskal-Wallis on non-zero subset
    print(f"\n  --- D3: Disease Site (non-zero delta only) ---")
    site_nz = nonzero.dropna(subset=["intervention_12_months", "disease_site"])
    site_groups_nz = {}
    for site, grp in site_nz.groupby("disease_site"):
        if len(grp) >= 5:  # relaxed threshold for smaller subset
            site_groups_nz[site] = grp["intervention_12_months"].values
    if len(site_groups_nz) >= 3:
        h_nz, p_kw_nz = stats.kruskal(*site_groups_nz.values())
        print(f"    Sites with N>=5: {list(site_groups_nz.keys())}")
        print(f"    Kruskal-Wallis H={h_nz:.2f}, p={p_kw_nz:.6f}")
        print(f"    {'SIGNIFICANT' if p_kw_nz < 0.05 else 'Not significant'}")
        validation_results.append({
            "Test": "Sensitivity: Disease Site KW (non-zero delta)",
            "Statistic": h_nz, "p_value": p_kw_nz,
            "Conclusion": "Significant" if p_kw_nz < 0.05 else "Not significant",
        })

    # D4: Delta-specific analyses on non-zero subset
    print(f"\n  --- D4: Delta TT Summary (non-zero only) ---")
    nz_delta = nonzero["delta_12_months"]
    print(f"    N = {len(nz_delta)}")
    print(f"    Median: {nz_delta.median():.1f}")
    print(f"    IQR: ({nz_delta.quantile(0.25):.1f} to {nz_delta.quantile(0.75):.1f})")
    print(f"    Mean ± SD: {nz_delta.mean():.1f} ± {nz_delta.std():.1f}")
    print(f"    Positive (interv > ctrl): {(nz_delta > 0).sum()} ({100*(nz_delta > 0).mean():.1f}%)")
    print(f"    Negative (ctrl > interv): {(nz_delta < 0).sum()} ({100*(nz_delta < 0).mean():.1f}%)")

    # ==========================================
    # SECTION E: REGRESSION SENSITIVITY — ALL ARMS vs pos_idx=0
    # ==========================================
    print("\n" + "=" * 50)
    print("SECTION E: Regression Sensitivity — All Arms vs pos_idx=0")
    print("=" * 50)

    def run_logistic(df_input, label):
        """Run logistic regression and return key results."""
        df = df_input.dropna(subset=["12_months", "disease_site", "treatment_modality",
                                      "sponsor_binary", "start_year"]).copy()
        df = df[df["12_months"] > 0]

        # Filter small groups
        for col in ["disease_site", "treatment_modality"]:
            counts = df[col].value_counts()
            valid = counts[counts >= MIN_GROUP_SIZE].index
            df = df[df[col].isin(valid)]

        median_tt = df["12_months"].median()
        df["high_tt"] = (df["12_months"] > median_tt).astype(int)
        df["year_centered"] = df["start_year"] - df["start_year"].mean()

        most_common_site = df["disease_site"].value_counts().idxmax()

        formula = (
            f'high_tt ~ C(sponsor_binary, Treatment("Non-Industry")) + '
            f'C(disease_site, Treatment("{most_common_site}")) + '
            f'C(treatment_modality, Treatment("Chemotherapy")) + '
            f'year_centered + '
            f'C(intervention_type, Treatment("control"))'
        )

        model = logit_formula(formula, data=df).fit(disp=0)
        y_pred = model.predict(df)
        auc = roc_auc_score(df["high_tt"], y_pred)

        # Extract key ORs
        key_predictors = {}
        for name in model.params.index:
            if name == "Intercept":
                continue
            # Simplify name
            clean = name
            for pattern in [
                'C(sponsor_binary, Treatment("Non-Industry"))[T.',
                f'C(disease_site, Treatment("{most_common_site}"))[T.',
                'C(treatment_modality, Treatment("Chemotherapy"))[T.',
                'C(intervention_type, Treatment("control"))[T.',
            ]:
                clean = clean.replace(pattern, "").rstrip("]")
            if name == "year_centered":
                clean = "Year"

            key_predictors[clean] = {
                "OR": np.exp(model.params[name]),
                "CI_lo": np.exp(model.conf_int().loc[name, 0]),
                "CI_hi": np.exp(model.conf_int().loc[name, 1]),
                "p": model.pvalues[name],
            }

        return {
            "label": label, "N": len(df), "AUC": auc,
            "pseudo_r2": model.prsquared, "median_threshold": median_tt,
            "predictors": key_predictors,
        }

    # Run both models
    primary_arms = arms_all[arms_all["pos_idx"] == 0].copy()
    res_primary = run_logistic(primary_arms, "Primary arms (pos_idx=0)")
    res_all = run_logistic(arms_all, "All arms")

    print(f"\n  {'Metric':<30} {'pos_idx=0':>15} {'All arms':>15}")
    print(f"  {'─'*60}")
    print(f"  {'N':<30} {res_primary['N']:>15} {res_all['N']:>15}")
    print(f"  {'AUC-ROC':<30} {res_primary['AUC']:>15.3f} {res_all['AUC']:>15.3f}")
    print(f"  {'Pseudo R²':<30} {res_primary['pseudo_r2']:>15.4f} {res_all['pseudo_r2']:>15.4f}")
    print(f"  {'Median threshold':<30} {res_primary['median_threshold']:>15.1f} {res_all['median_threshold']:>15.1f}")

    # Compare key ORs
    key_vars = ["Industry", "Immunotherapy", "Targeted Therapy", "Endocrine", "Year", "intervention"]
    print(f"\n  {'Predictor':<25} {'OR (pos_idx=0)':>15} {'OR (all)':>15} {'Diff':>8}")
    print(f"  {'─'*65}")
    for var in key_vars:
        or1 = res_primary["predictors"].get(var, {}).get("OR", np.nan)
        or2 = res_all["predictors"].get(var, {}).get("OR", np.nan)
        p1 = res_primary["predictors"].get(var, {}).get("p", np.nan)
        p2 = res_all["predictors"].get(var, {}).get("p", np.nan)
        diff = abs(or1 - or2) if pd.notna(or1) and pd.notna(or2) else np.nan
        sig1 = "*" if pd.notna(p1) and p1 < 0.05 else ""
        sig2 = "*" if pd.notna(p2) and p2 < 0.05 else ""
        print(f"  {var:<25} {or1:>12.2f}{sig1:<3} {or2:>12.2f}{sig2:<3} {diff:>8.2f}")

    validation_results.append({
        "Test": "Regression: pos_idx=0 AUC",
        "Statistic": res_primary["AUC"], "p_value": None,
        "Conclusion": f"N={res_primary['N']}",
    })
    validation_results.append({
        "Test": "Regression: All arms AUC",
        "Statistic": res_all["AUC"], "p_value": None,
        "Conclusion": f"N={res_all['N']}",
    })

    # ==========================================
    # SECTION F: ARM LABELING SPOT CHECK
    # ==========================================
    print("\n" + "=" * 50)
    print("SECTION F: Arm Labeling Spot Check")
    print("=" * 50)

    # --- F1: TT Inversion Check (all trials) ---
    print("\n--- F1: TT Inversion Check ---")
    paired_check = trials.dropna(subset=["intervention_12_months", "control_12_months"])
    inverted = paired_check[paired_check["control_12_months"] > paired_check["intervention_12_months"]]
    n_inverted = len(inverted)
    n_total_paired = len(paired_check)
    print(f"  Trials where control TT > intervention TT: {n_inverted} ({100*n_inverted/n_total_paired:.1f}%)")
    print(f"  (Out of {n_total_paired} paired trials)")

    # Characterize inversions
    if n_inverted > 0:
        inv_diff = inverted["control_12_months"] - inverted["intervention_12_months"]
        print(f"  Inversion magnitude: median={inv_diff.median():.1f}, "
              f"IQR=({inv_diff.quantile(0.25):.1f}-{inv_diff.quantile(0.75):.1f})")
        print(f"  Max inversion: {inv_diff.max():.0f} days")

        # Show top 10 most inverted
        top_inv = inverted.nlargest(10, "control_12_months")
        print(f"\n  Top 10 most inverted trials:")
        for _, row in top_inv.iterrows():
            print(f"    {str(row['filename'])[:50]}: "
                  f"ctrl={row['control_12_months']:.0f}, "
                  f"interv={row['intervention_12_months']:.0f}, "
                  f"diff={row['control_12_months']-row['intervention_12_months']:.0f}")

    # --- F2: Multi-Control Drug Name Audit ---
    print("\n--- F2: Multi-Control Drug Name Audit ---")

    # Define supportive drugs to exclude from mislabeling check
    supportive_drugs = {k for k, v in DRUG_CLASSES.items() if v == "Supportive"}
    active_drugs = {k for k, v in DRUG_CLASSES.items() if v != "Supportive"}

    # Control keywords
    control_keywords = [
        "placebo", "standard of care", "soc", "bsc", "best supportive",
        "observation", "watchful waiting", "physician's choice",
        "investigator's choice", "active surveillance", "standard",
        "comparator", "usual care",
    ]

    ctrl_arms_check = consensus_arms[consensus_arms["intervention_type"] == "control"]
    ctrl_per_trial_check = ctrl_arms_check.groupby("filename").size()
    multi_ctrl_fnames = ctrl_per_trial_check[ctrl_per_trial_check > 1].index

    labeling_audit_rows = []
    n_suspect = 0
    n_multi_ctrl_suspect_trials = 0

    for fname in multi_ctrl_fnames:
        trial_arms_all = consensus_arms[consensus_arms["filename"] == fname]
        ctrl_for_trial = trial_arms_all[trial_arms_all["intervention_type"] == "control"]
        interv_for_trial = trial_arms_all[trial_arms_all["intervention_type"] == "intervention"]

        n_ctrl = len(ctrl_for_trial)
        n_interv = len(interv_for_trial)

        # Get max intervention TT for comparison
        max_interv_tt = interv_for_trial["12_months"].max() if len(interv_for_trial) > 0 else 0

        trial_has_suspect = False

        for _, arm in ctrl_for_trial.iterrows():
            arm_name_lower = str(arm.get("arm_name", "")).lower()

            # Check for control keywords
            has_control_keyword = any(kw in arm_name_lower for kw in control_keywords)

            # Check for active drug names
            active_drugs_found = []
            for drug in active_drugs:
                if drug.lower() in arm_name_lower:
                    active_drugs_found.append(drug)

            # Check if TT exceeds intervention arm
            tt_exceeds_intervention = arm["12_months"] > max_interv_tt if max_interv_tt > 0 else False

            # Classify
            if has_control_keyword:
                suspect_flag = "Likely correct"
                reason = f"Has control keyword"
            elif active_drugs_found and tt_exceeds_intervention and not has_control_keyword:
                suspect_flag = "Suspect"
                reason = (f"Active drug(s): {', '.join(active_drugs_found[:3])}; "
                         f"TT ({arm['12_months']:.0f}) > intervention ({max_interv_tt:.0f}); "
                         f"no control keyword")
                n_suspect += 1
                trial_has_suspect = True
            elif active_drugs_found and not has_control_keyword:
                suspect_flag = "Ambiguous"
                reason = f"Active drug(s): {', '.join(active_drugs_found[:3])}; no control keyword"
            else:
                suspect_flag = "Likely correct"
                reason = "No active drugs or has control keyword"

            labeling_audit_rows.append({
                "filename": fname,
                "arm_name": arm.get("arm_name", "N/A"),
                "current_label": "control",
                "12mo_TT": arm["12_months"],
                "suspect_flag": suspect_flag,
                "reason": reason,
                "n_controls_in_trial": n_ctrl,
                "n_interventions_in_trial": n_interv,
                "max_intervention_TT": max_interv_tt,
            })

        if trial_has_suspect:
            n_multi_ctrl_suspect_trials += 1

    print(f"  Multi-control protocols audited: {len(multi_ctrl_fnames)}")
    print(f"  Total control arms in multi-control trials: {len(labeling_audit_rows)}")
    suspect_arms = [r for r in labeling_audit_rows if r["suspect_flag"] == "Suspect"]
    ambiguous_arms = [r for r in labeling_audit_rows if r["suspect_flag"] == "Ambiguous"]
    correct_arms = [r for r in labeling_audit_rows if r["suspect_flag"] == "Likely correct"]
    print(f"  Classification:")
    print(f"    Likely correct: {len(correct_arms)}")
    print(f"    Ambiguous: {len(ambiguous_arms)}")
    print(f"    Suspect mislabeling: {len(suspect_arms)}")
    print(f"  Trials with at least one suspect arm: {n_multi_ctrl_suspect_trials}")

    if suspect_arms:
        print(f"\n  SUSPECT ARMS (active drug + TT > intervention + no control keyword):")
        for arm in suspect_arms:
            print(f"    {str(arm['filename'])[:50]}")
            print(f"      Arm: {str(arm['arm_name'])[:60]}")
            print(f"      TT: {arm['12mo_TT']:.0f} (max intervention: {arm['max_intervention_TT']:.0f})")
            print(f"      Reason: {arm['reason']}")

    if ambiguous_arms:
        print(f"\n  AMBIGUOUS ARMS (active drug, no control keyword, TT ≤ intervention):")
        for arm in ambiguous_arms[:10]:  # Show top 10
            print(f"    {str(arm['filename'])[:50]}: "
                  f"{str(arm['arm_name'])[:40]}, TT={arm['12mo_TT']:.0f}")
        if len(ambiguous_arms) > 10:
            print(f"    ... and {len(ambiguous_arms) - 10} more")

    # --- F3: User's Hypothesis — Multi-Control as Multi-Intervention ---
    print("\n--- F3: Multi-Control as Multi-Intervention Hypothesis ---")

    atypical_count = 0
    atypical_trials = []
    for fname in multi_ctrl_fnames:
        trial_arms_all = consensus_arms[consensus_arms["filename"] == fname]
        n_ctrl = (trial_arms_all["intervention_type"] == "control").sum()
        n_interv = (trial_arms_all["intervention_type"] == "intervention").sum()

        if n_ctrl > n_interv:
            atypical_count += 1
            ctrl_tt = trial_arms_all[trial_arms_all["intervention_type"] == "control"]["12_months"]
            interv_tt = trial_arms_all[trial_arms_all["intervention_type"] == "intervention"]["12_months"]
            atypical_trials.append({
                "filename": fname,
                "n_ctrl": n_ctrl, "n_interv": n_interv,
                "ctrl_tt_range": f"{ctrl_tt.min():.0f}-{ctrl_tt.max():.0f}",
                "interv_tt_range": f"{interv_tt.min():.0f}-{interv_tt.max():.0f}" if len(interv_tt) > 0 else "N/A",
            })

    print(f"  Trials with n_control > n_intervention: {atypical_count} / {len(multi_ctrl_fnames)}")
    print(f"  (This pattern supports the hypothesis of mislabeled interventions)")

    if atypical_trials:
        print(f"\n  Atypical trials (more controls than interventions):")
        for t in atypical_trials:
            print(f"    {str(t['filename'])[:50]}")
            print(f"      Controls: {t['n_ctrl']} (TT range: {t['ctrl_tt_range']})")
            print(f"      Interventions: {t['n_interv']} (TT range: {t['interv_tt_range']})")

    # Summary statistics
    print(f"\n--- F: SUMMARY ---")
    print(f"  TT inversions (ctrl > interv): {n_inverted}/{n_total_paired} ({100*n_inverted/n_total_paired:.1f}%)")
    print(f"  Multi-control suspect mislabelings: {len(suspect_arms)} arms in {n_multi_ctrl_suspect_trials} trials")
    print(f"  Multi-control ambiguous: {len(ambiguous_arms)} arms")
    print(f"  Trials with more controls than interventions: {atypical_count}")

    validation_results.append({
        "Test": "Arm Labeling: TT inversions",
        "Statistic": n_inverted, "p_value": None,
        "Conclusion": f"{n_inverted}/{n_total_paired} trials ({100*n_inverted/n_total_paired:.1f}%)",
    })
    validation_results.append({
        "Test": "Arm Labeling: Suspect mislabelings",
        "Statistic": len(suspect_arms), "p_value": None,
        "Conclusion": f"{len(suspect_arms)} arms in {n_multi_ctrl_suspect_trials} trials",
    })
    validation_results.append({
        "Test": "Arm Labeling: Atypical designs (n_ctrl > n_interv)",
        "Statistic": atypical_count, "p_value": None,
        "Conclusion": f"{atypical_count}/{len(multi_ctrl_fnames)} multi-control trials",
    })

    # Save labeling audit
    if labeling_audit_rows:
        labeling_audit_df = pd.DataFrame(labeling_audit_rows)
        labeling_audit_df.to_csv(
            os.path.join(TABLES_DIR, "table_arm_labeling_audit.csv"), index=False)
        print(f"  Saved: tables/table_arm_labeling_audit.csv")

    # ==========================================
    # SAVE VALIDATION RESULTS
    # ==========================================
    print("\n" + "=" * 50)
    print("SAVING RESULTS")
    print("=" * 50)

    val_df = pd.DataFrame(validation_results)
    val_df.to_csv(os.path.join(TABLES_DIR, "table_validation_summary.csv"), index=False)
    print(f"  Saved: tables/table_validation_summary.csv")

    audit_df = pd.DataFrame(audit_rows)
    audit_df.to_csv(os.path.join(DATA_DIR, "validation_audit.csv"), index=False)
    print(f"  Saved: data/validation_audit.csv")

    print("\n" + "=" * 60)
    print("STEP 8 COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
