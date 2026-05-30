#!/usr/bin/env python3
"""
Step 4: Comparative Analyses

a) Sponsorship — Wilcoxon rank-sum (Industry vs Non-Industry)
b) Disease Site — Kruskal-Wallis (across cancer types)
c) Treatment Type — Wilcoxon rank-sum (Immunotherapy vs Chemotherapy) + Kruskal-Wallis
d) Temporal Trend — Linear regression + Spearman correlation
e) Industry-Specific Temporal Trend — Stratified trends + interaction
f) Front-Loading Analysis — Early vs late TT accumulation
g) IQR Comparison Tables
h) Adjusted Temporal Trend — Controlling for disease site & modality
i) Within-Disease-Site Temporal Trends
j) Adjusted Sponsorship Comparison — Controlling for disease site & modality
k) Funder x Time Interaction — Adjusted
"""

import os
import sys
import warnings
import pandas as pd
import numpy as np
from scipy import stats
import statsmodels.api as sm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import DATA_DIR, TABLES_DIR, FIGURES_DIR, MIN_GROUP_SIZE, TIMEPOINTS

warnings.filterwarnings("ignore", category=FutureWarning)


def rank_biserial(u, n1, n2):
    """Compute rank-biserial correlation (effect size for Mann-Whitney U)."""
    return 1 - (2 * u) / (n1 * n2)


def wilcoxon_report(group1, group2, label1, label2, outcome_name):
    """Run Wilcoxon rank-sum and print detailed report."""
    g1 = group1.dropna()
    g2 = group2.dropna()

    u_stat, p_value = stats.mannwhitneyu(g1, g2, alternative="two-sided")
    r = rank_biserial(u_stat, len(g1), len(g2))

    print(f"\n  {label1} (N={len(g1)}): median={g1.median():.1f}, IQR=({g1.quantile(0.25):.1f}-{g1.quantile(0.75):.1f})")
    print(f"  {label2} (N={len(g2)}): median={g2.median():.1f}, IQR=({g2.quantile(0.25):.1f}-{g2.quantile(0.75):.1f})")
    print(f"  Mann-Whitney U = {u_stat:.0f}, p = {p_value:.4f}")
    print(f"  Rank-biserial r = {r:.3f}")
    if p_value < 0.05:
        print(f"  ** SIGNIFICANT at alpha=0.05 **")

    return {
        "comparison": f"{label1} vs {label2}",
        "outcome": outcome_name,
        "n1": len(g1), "median1": g1.median(), "iqr1": f"{g1.quantile(0.25):.1f}-{g1.quantile(0.75):.1f}",
        "n2": len(g2), "median2": g2.median(), "iqr2": f"{g2.quantile(0.25):.1f}-{g2.quantile(0.75):.1f}",
        "U": u_stat, "p_value": p_value, "rank_biserial_r": r,
    }


def main():
    print("=" * 60)
    print("STEP 4: Comparative Analyses")
    print("=" * 60)

    trials = pd.read_csv(os.path.join(DATA_DIR, "enriched_trials.csv"))
    arms = pd.read_csv(os.path.join(DATA_DIR, "enriched_arms.csv"))

    results = []

    # ==========================================
    # 4a) SPONSORSHIP — Wilcoxon Rank-Sum
    # ==========================================
    print("\n" + "=" * 50)
    print("4a) SPONSORSHIP: Industry vs Non-Industry")
    print("=" * 50)

    # Intervention arm 12-month TT
    print("\n--- Intervention Arm 12-Month TT ---")
    industry = trials[trials["sponsor_binary"] == "Industry"]["intervention_12_months"]
    non_industry = trials[trials["sponsor_binary"] == "Non-Industry"]["intervention_12_months"]
    r1 = wilcoxon_report(industry, non_industry, "Industry", "Non-Industry", "Intervention 12mo TT")
    results.append(r1)

    # Delta TT
    print("\n--- Delta TT (Intervention - Control) ---")
    paired = trials.dropna(subset=["delta_12_months"])
    ind_delta = paired[paired["sponsor_binary"] == "Industry"]["delta_12_months"]
    noind_delta = paired[paired["sponsor_binary"] == "Non-Industry"]["delta_12_months"]
    r2 = wilcoxon_report(ind_delta, noind_delta, "Industry", "Non-Industry", "Delta TT")
    results.append(r2)

    # ==========================================
    # 4b) DISEASE SITE — Kruskal-Wallis
    # ==========================================
    print("\n" + "=" * 50)
    print("4b) DISEASE SITE: Kruskal-Wallis")
    print("=" * 50)

    # Filter to intervention arms at trial level
    tt_by_site = trials.dropna(subset=["intervention_12_months", "disease_site"])
    site_groups = {}
    for site, grp in tt_by_site.groupby("disease_site"):
        if len(grp) >= MIN_GROUP_SIZE:
            site_groups[site] = grp["intervention_12_months"].values

    print(f"\n  Sites included (N>={MIN_GROUP_SIZE}): {list(site_groups.keys())}")
    for site, vals in sorted(site_groups.items(), key=lambda x: np.median(x[1]), reverse=True):
        print(f"  {site}: N={len(vals)}, median={np.median(vals):.1f}, IQR=({np.percentile(vals, 25):.1f}-{np.percentile(vals, 75):.1f})")

    h_stat, p_value = stats.kruskal(*site_groups.values())
    print(f"\n  Kruskal-Wallis H = {h_stat:.2f}, p = {p_value:.6f}")
    if p_value < 0.05:
        print(f"  ** SIGNIFICANT at alpha=0.05 **")

    results.append({
        "comparison": "Disease Site (Kruskal-Wallis)",
        "outcome": "Intervention 12mo TT",
        "n1": sum(len(v) for v in site_groups.values()),
        "U": h_stat, "p_value": p_value,
    })

    # Post-hoc Dunn's test if significant
    if p_value < 0.05:
        print("\n--- Post-hoc Dunn's Test (Bonferroni corrected) ---")
        try:
            import scikit_posthocs as sp
            dunn_data = tt_by_site[tt_by_site["disease_site"].isin(site_groups.keys())]
            dunn_result = sp.posthoc_dunn(
                dunn_data, val_col="intervention_12_months",
                group_col="disease_site", p_adjust="bonferroni"
            )
            # Show significant pairwise comparisons
            sig_pairs = []
            for i in range(len(dunn_result)):
                for j in range(i + 1, len(dunn_result)):
                    site_a = dunn_result.index[i]
                    site_b = dunn_result.columns[j]
                    p = dunn_result.iloc[i, j]
                    if p < 0.05:
                        sig_pairs.append((site_a, site_b, p))

            if sig_pairs:
                print(f"  Significant pairwise differences (p<0.05):")
                for a, b, p in sorted(sig_pairs, key=lambda x: x[2]):
                    print(f"    {a} vs {b}: p={p:.4f}")
            else:
                print("  No pairwise comparisons significant after Bonferroni correction")
        except ImportError:
            print("  scikit-posthocs not available, skipping Dunn's test")

    # ==========================================
    # 4c) TREATMENT TYPE
    # ==========================================
    print("\n" + "=" * 50)
    print("4c) TREATMENT TYPE")
    print("=" * 50)

    tt_by_mod = trials.dropna(subset=["intervention_12_months", "treatment_modality"])

    # Primary: Immunotherapy vs Chemotherapy
    print("\n--- Primary: Immunotherapy vs Chemotherapy ---")
    immuno = tt_by_mod[tt_by_mod["treatment_modality"] == "Immunotherapy"]["intervention_12_months"]
    chemo = tt_by_mod[tt_by_mod["treatment_modality"] == "Chemotherapy"]["intervention_12_months"]
    r3 = wilcoxon_report(immuno, chemo, "Immunotherapy", "Chemotherapy", "Intervention 12mo TT")
    results.append(r3)

    # Secondary: Kruskal-Wallis across all modalities
    print("\n--- Secondary: Kruskal-Wallis across all treatment modalities ---")
    mod_groups = {}
    for mod, grp in tt_by_mod.groupby("treatment_modality"):
        if len(grp) >= MIN_GROUP_SIZE:
            mod_groups[mod] = grp["intervention_12_months"].values

    print(f"\n  Modalities included (N>={MIN_GROUP_SIZE}): {list(mod_groups.keys())}")
    for mod, vals in sorted(mod_groups.items(), key=lambda x: np.median(x[1]), reverse=True):
        print(f"  {mod}: N={len(vals)}, median={np.median(vals):.1f}")

    h_stat2, p_value2 = stats.kruskal(*mod_groups.values())
    print(f"\n  Kruskal-Wallis H = {h_stat2:.2f}, p = {p_value2:.6f}")
    if p_value2 < 0.05:
        print(f"  ** SIGNIFICANT at alpha=0.05 **")

    results.append({
        "comparison": "Treatment Modality (Kruskal-Wallis)",
        "outcome": "Intervention 12mo TT",
        "n1": sum(len(v) for v in mod_groups.values()),
        "U": h_stat2, "p_value": p_value2,
    })

    # Pairwise Wilcoxon with Bonferroni
    if p_value2 < 0.05:
        print("\n--- Pairwise Wilcoxon (Bonferroni corrected) ---")
        mod_names = sorted(mod_groups.keys())
        n_comparisons = len(mod_names) * (len(mod_names) - 1) // 2
        pair_results = []
        for i in range(len(mod_names)):
            for j in range(i + 1, len(mod_names)):
                u, p = stats.mannwhitneyu(mod_groups[mod_names[i]], mod_groups[mod_names[j]], alternative="two-sided")
                p_adj = min(p * n_comparisons, 1.0)
                pair_results.append((mod_names[i], mod_names[j], u, p, p_adj))

        for a, b, u, p, p_adj in sorted(pair_results, key=lambda x: x[3]):
            sig = "*" if p_adj < 0.05 else ""
            print(f"    {a} vs {b}: U={u:.0f}, p_raw={p:.4f}, p_adj={p_adj:.4f} {sig}")

    # ==========================================
    # 4d) TEMPORAL TREND
    # ==========================================
    print("\n" + "=" * 50)
    print("4d) TEMPORAL TREND: TT vs Trial Start Year")
    print("=" * 50)

    temporal = trials.dropna(subset=["intervention_12_months", "start_year"])
    y = temporal["intervention_12_months"]
    x = temporal["start_year"]

    # Spearman correlation
    rho, p_spearman = stats.spearmanr(x, y)
    print(f"\n  Spearman correlation: rho = {rho:.3f}, p = {p_spearman:.4f}")
    if p_spearman < 0.05:
        print(f"  ** SIGNIFICANT at alpha=0.05 **")

    # OLS Linear Regression
    X = sm.add_constant(x)
    model = sm.OLS(y, X).fit()
    slope = model.params.iloc[1]
    r_squared = model.rsquared
    p_ols = model.pvalues.iloc[1]
    ci = model.conf_int().iloc[1]

    print(f"\n  OLS Linear Regression:")
    print(f"    Slope = {slope:.3f} days/year (95% CI: {ci[0]:.3f} to {ci[1]:.3f})")
    print(f"    R² = {r_squared:.4f}")
    print(f"    p = {p_ols:.4f}")
    if p_ols < 0.05:
        print(f"  ** SIGNIFICANT at alpha=0.05 **")

    # Yearly medians
    print("\n  Yearly Median TT (Intervention):")
    yearly = temporal.groupby("start_year")["intervention_12_months"].agg(["median", "count"])
    for year, row in yearly.iterrows():
        print(f"    {int(year)}: median={row['median']:.1f} (N={int(row['count'])})")

    results.append({
        "comparison": "Temporal Trend (OLS)",
        "outcome": "Intervention 12mo TT ~ Trial Start Year",
        "n1": len(temporal),
        "U": slope, "p_value": p_ols,
        "rank_biserial_r": rho,
    })

    # ==========================================
    # 4e) INDUSTRY-SPECIFIC TEMPORAL TREND
    # ==========================================
    print("\n" + "=" * 50)
    print("4e) INDUSTRY-SPECIFIC TEMPORAL TREND")
    print("=" * 50)

    temporal_sponsor = trials.dropna(subset=["intervention_12_months", "start_year", "sponsor_binary"])
    industry_temporal_rows = []

    for sponsor in ["Industry", "Non-Industry"]:
        subset = temporal_sponsor[temporal_sponsor["sponsor_binary"] == sponsor]
        y_s = subset["intervention_12_months"]
        x_s = subset["start_year"]

        rho_s, p_sp_s = stats.spearmanr(x_s, y_s)
        X_s = sm.add_constant(x_s)
        model_s = sm.OLS(y_s, X_s).fit()
        slope_s = model_s.params.iloc[1]
        p_ols_s = model_s.pvalues.iloc[1]
        ci_s = model_s.conf_int().iloc[1]
        r2_s = model_s.rsquared

        print(f"\n  {sponsor} (N={len(subset)}):")
        print(f"    OLS Slope = {slope_s:.3f} days/year (95% CI: {ci_s[0]:.3f} to {ci_s[1]:.3f})")
        print(f"    R² = {r2_s:.4f}, p = {p_ols_s:.4f}")
        print(f"    Spearman rho = {rho_s:.3f}, p = {p_sp_s:.4f}")
        if p_ols_s < 0.05:
            print(f"    ** SIGNIFICANT **")

        results.append({
            "comparison": f"Temporal Trend ({sponsor})",
            "outcome": "Intervention 12mo TT ~ Trial Start Year",
            "n1": len(subset),
            "U": slope_s, "p_value": p_ols_s,
            "rank_biserial_r": rho_s,
        })

        industry_temporal_rows.append({
            "Sponsor": sponsor, "N": len(subset),
            "Slope": slope_s, "CI_lower": ci_s[0], "CI_upper": ci_s[1],
            "R2": r2_s, "p_OLS": p_ols_s,
            "Spearman_rho": rho_s, "p_Spearman": p_sp_s,
        })

    # Formal interaction test
    print(f"\n--- Interaction Test: Year x Sponsor ---")
    temporal_sponsor["is_industry"] = (temporal_sponsor["sponsor_binary"] == "Industry").astype(int)
    temporal_sponsor["year_x_industry"] = temporal_sponsor["start_year"] * temporal_sponsor["is_industry"]
    X_inter = sm.add_constant(temporal_sponsor[["start_year", "is_industry", "year_x_industry"]])
    model_inter = sm.OLS(temporal_sponsor["intervention_12_months"], X_inter).fit()
    p_interaction = model_inter.pvalues["year_x_industry"]
    coef_interaction = model_inter.params["year_x_industry"]
    print(f"  Interaction coefficient = {coef_interaction:.3f}")
    print(f"  p = {p_interaction:.4f}")
    print(f"  Industry slope is {'significantly' if p_interaction < 0.05 else 'not significantly'} different from Non-Industry")

    industry_temporal_rows.append({
        "Sponsor": "Interaction (Year x Industry)", "N": len(temporal_sponsor),
        "Slope": coef_interaction, "p_OLS": p_interaction,
    })

    it_df = pd.DataFrame(industry_temporal_rows)
    it_df.to_csv(os.path.join(TABLES_DIR, "table_industry_temporal.csv"), index=False)
    print(f"  Saved: tables/table_industry_temporal.csv")

    # ==========================================
    # 4f) FRONT-LOADING ANALYSIS
    # ==========================================
    print("\n" + "=" * 50)
    print("4f) FRONT-LOADING ANALYSIS: Early vs Late TT Accumulation")
    print("=" * 50)

    fl_arms = arms.dropna(subset=["3_months", "12_months"]).copy()
    fl_arms = fl_arms[fl_arms["12_months"] > 0]

    # Compute rates
    fl_arms["early_days"] = fl_arms["3_months"]
    fl_arms["late_days"] = fl_arms["12_months"] - fl_arms["3_months"]
    fl_arms["early_rate"] = fl_arms["early_days"] / 3.0
    fl_arms["late_rate"] = fl_arms["late_days"] / 9.0
    fl_arms["front_load_pct"] = np.where(
        fl_arms["late_rate"] > 0,
        ((fl_arms["early_rate"] - fl_arms["late_rate"]) / fl_arms["late_rate"]) * 100,
        np.nan
    )

    # Overall
    print(f"\n  Overall (N={len(fl_arms)} arms with TT > 0):")
    print(f"    Early rate (0-3mo): {fl_arms['early_rate'].median():.2f} days/month (median)")
    print(f"    Late rate (3-12mo): {fl_arms['late_rate'].median():.2f} days/month (median)")
    er_med = fl_arms['early_rate'].median()
    lr_med = fl_arms['late_rate'].median()
    if lr_med > 0:
        print(f"    Front-load ratio: {er_med/lr_med:.2f}x")

    # Wilcoxon signed-rank test (paired)
    valid_fl = fl_arms.dropna(subset=["early_rate", "late_rate"])
    valid_fl = valid_fl[(valid_fl["early_rate"] > 0) | (valid_fl["late_rate"] > 0)]
    stat_fl, p_fl = stats.wilcoxon(valid_fl["early_rate"], valid_fl["late_rate"])
    print(f"    Wilcoxon signed-rank: W={stat_fl:.0f}, p={p_fl:.6f}")
    if p_fl < 0.05:
        print(f"    ** Early rate significantly different from late rate **")

    # By intervention type
    print(f"\n  Front-loading by Arm Type:")
    for arm_type in ["intervention", "control"]:
        arm_data = fl_arms[fl_arms["intervention_type"] == arm_type]
        er = arm_data["early_rate"].median()
        lr = arm_data["late_rate"].median()
        print(f"    {arm_type}: early={er:.2f}, late={lr:.2f} d/mo"
              + (f", ratio={er/lr:.2f}x" if lr > 0 else ", late=0"))

    # By treatment modality
    print(f"\n  Front-loading by Treatment Modality:")
    fl_rows = []
    for mod, grp in fl_arms.groupby("treatment_modality"):
        if len(grp) >= MIN_GROUP_SIZE:
            er = grp["early_rate"].median()
            lr = grp["late_rate"].median()
            fl_pct = grp["front_load_pct"].median()
            print(f"    {mod} (N={len(grp)}): early={er:.2f}, late={lr:.2f}"
                  + (f", front-load={fl_pct:.1f}%" if pd.notna(fl_pct) else ""))
            fl_rows.append({
                "Treatment_Modality": mod, "N": len(grp),
                "Median_Early_Rate": round(er, 2), "Median_Late_Rate": round(lr, 2),
                "Median_Front_Load_Pct": round(fl_pct, 1) if pd.notna(fl_pct) else None,
            })

    # Incremental days per interval
    print(f"\n  Incremental Days per Interval (Intervention Arms, Median):")
    interv_fl = fl_arms[fl_arms["intervention_type"] == "intervention"]
    intervals = [
        ("screening → 1_month", "1_month", "screening", 1),
        ("1_month → 3_months", "3_months", "1_month", 2),
        ("3_months → 6_months", "6_months", "3_months", 3),
        ("6_months → 9_months", "9_months", "6_months", 3),
        ("9_months → 12_months", "12_months", "9_months", 3),
    ]
    for label, end_col, start_col, months in intervals:
        incr = interv_fl[end_col] - interv_fl[start_col]
        rate = incr / months
        print(f"    {label}: {incr.median():.1f} days ({rate.median():.2f} d/mo)")

    fl_df = pd.DataFrame(fl_rows)
    fl_df.to_csv(os.path.join(TABLES_DIR, "table_front_loading.csv"), index=False)
    print(f"  Saved: tables/table_front_loading.csv")

    # ==========================================
    # 4g) IQR COMPARISON TABLES
    # ==========================================
    print("\n" + "=" * 50)
    print("4g) IQR COMPARISON TABLES")
    print("=" * 50)

    def iqr_summary(series, label):
        s = series.dropna()
        if len(s) == 0:
            return {"Group": label, "N": 0}
        return {
            "Group": label, "N": len(s),
            "Median": round(s.median(), 1),
            "Q1": round(s.quantile(0.25), 1),
            "Q3": round(s.quantile(0.75), 1),
            "IQR": round(s.quantile(0.75) - s.quantile(0.25), 1),
            "Mean": round(s.mean(), 1),
            "SD": round(s.std(), 1),
        }

    iqr_rows = []

    # By sponsor
    for sponsor in ["Industry", "Non-Industry"]:
        subset = trials[trials["sponsor_binary"] == sponsor]["intervention_12_months"]
        iqr_rows.append(iqr_summary(subset, f"Sponsor: {sponsor}"))

    # By disease site
    for site in sorted(trials["disease_site"].dropna().unique()):
        subset = trials[trials["disease_site"] == site]["intervention_12_months"]
        if len(subset.dropna()) >= MIN_GROUP_SIZE:
            iqr_rows.append(iqr_summary(subset, f"Site: {site}"))

    # By modality
    for mod in sorted(trials["treatment_modality"].dropna().unique()):
        subset = trials[trials["treatment_modality"] == mod]["intervention_12_months"]
        if len(subset.dropna()) >= MIN_GROUP_SIZE:
            iqr_rows.append(iqr_summary(subset, f"Modality: {mod}"))

    iqr_df = pd.DataFrame(iqr_rows)
    iqr_df.to_csv(os.path.join(TABLES_DIR, "table_iqr_comparison.csv"), index=False)
    print(f"  Saved: tables/table_iqr_comparison.csv")

    for _, row in iqr_df.iterrows():
        print(f"  {row['Group']}: Median={row['Median']}, IQR={row['IQR']} "
              f"({row['Q1']}-{row['Q3']}), N={row['N']}")

    # ==========================================
    # 4h) ADJUSTED TEMPORAL TREND (KEY ANALYSIS)
    # ==========================================
    print("\n" + "=" * 50)
    print("4h) ADJUSTED TEMPORAL TREND: Controlling for Disease Site & Modality")
    print("=" * 50)

    adj_temp = trials.dropna(subset=["intervention_12_months", "start_year",
                                      "disease_site", "treatment_modality"]).copy()
    # Filter to sites and modalities with sufficient N
    site_cts = adj_temp["disease_site"].value_counts()
    valid_adj_sites = site_cts[site_cts >= MIN_GROUP_SIZE].index.tolist()
    adj_temp = adj_temp[adj_temp["disease_site"].isin(valid_adj_sites)]

    mod_cts = adj_temp["treatment_modality"].value_counts()
    valid_adj_mods = mod_cts[mod_cts >= MIN_GROUP_SIZE].index.tolist()
    adj_temp = adj_temp[adj_temp["treatment_modality"].isin(valid_adj_mods)]
    print(f"  Analysis N = {len(adj_temp)}")
    print(f"  Sites included: {valid_adj_sites}")
    print(f"  Modalities included: {valid_adj_mods}")

    # Identify reference categories
    most_common_site_adj = adj_temp["disease_site"].value_counts().idxmax()
    print(f"  Reference site: {most_common_site_adj}")
    print(f"  Reference modality: Chemotherapy")

    # Raw model (replicates 4d on this filtered subset)
    from statsmodels.formula.api import ols as ols_formula
    model_raw = ols_formula("intervention_12_months ~ start_year", data=adj_temp).fit()
    raw_slope = model_raw.params["start_year"]
    raw_ci = model_raw.conf_int().loc["start_year"]
    raw_p = model_raw.pvalues["start_year"]
    raw_r2 = model_raw.rsquared

    print(f"\n  RAW model (this subset):")
    print(f"    Slope = {raw_slope:.3f} d/yr (95% CI: {raw_ci[0]:.3f} to {raw_ci[1]:.3f})")
    print(f"    R² = {raw_r2:.4f}, p = {raw_p:.4f}")

    # Adjusted model
    adj_formula = (
        f'intervention_12_months ~ start_year + '
        f'C(disease_site, Treatment("{most_common_site_adj}")) + '
        f'C(treatment_modality, Treatment("Chemotherapy"))'
    )
    model_adj = ols_formula(adj_formula, data=adj_temp).fit()
    adj_slope = model_adj.params["start_year"]
    adj_ci = model_adj.conf_int().loc["start_year"]
    adj_p = model_adj.pvalues["start_year"]
    adj_r2 = model_adj.rsquared

    print(f"\n  ADJUSTED model (+ disease site + treatment modality):")
    print(f"    Slope = {adj_slope:.3f} d/yr (95% CI: {adj_ci[0]:.3f} to {adj_ci[1]:.3f})")
    print(f"    R² = {adj_r2:.4f}, p = {adj_p:.4f}")

    delta_slope = adj_slope - raw_slope
    print(f"\n  COMPARISON:")
    print(f"    Raw slope:     {raw_slope:+.3f} d/yr (p={raw_p:.4f})")
    print(f"    Adjusted slope: {adj_slope:+.3f} d/yr (p={adj_p:.4f})")
    print(f"    Change: {delta_slope:+.3f} d/yr")
    if abs(adj_slope) > abs(raw_slope):
        print(f"    ** Adjustment STRENGTHENS the temporal trend **")
    elif abs(adj_slope) < abs(raw_slope) and adj_p < 0.05:
        print(f"    ** Adjustment ATTENUATES but trend remains significant **")
    elif adj_p >= 0.05:
        print(f"    ** Trend is NOT significant after adjustment **")

    # Full model summary
    print(f"\n  Adjusted model summary (significant covariates p<0.05):")
    for name in model_adj.params.index:
        if name == "Intercept":
            continue
        p_val = model_adj.pvalues[name]
        if p_val < 0.05:
            coef = model_adj.params[name]
            ci_lo, ci_hi = model_adj.conf_int().loc[name]
            clean = name.replace(f'C(disease_site, Treatment("{most_common_site_adj}"))', "Site: ")
            clean = clean.replace('C(treatment_modality, Treatment("Chemotherapy"))', "Modality: ")
            clean = clean.replace("[T.", "").replace("]", "")
            print(f"    {clean}: coef={coef:.2f} ({ci_lo:.2f} to {ci_hi:.2f}), p={p_val:.4f}")

    results.append({
        "comparison": "Adjusted Temporal Trend",
        "outcome": "Intervention 12mo TT ~ start_year (adj site+modality)",
        "n1": len(adj_temp), "U": adj_slope, "p_value": adj_p,
    })

    # Save
    adj_temp_rows = [
        {"Model": "Raw (unadjusted)", "Slope": raw_slope, "CI_lower": raw_ci[0],
         "CI_upper": raw_ci[1], "p_value": raw_p, "R_squared": raw_r2, "N": len(adj_temp)},
        {"Model": "Adjusted (site + modality)", "Slope": adj_slope, "CI_lower": adj_ci[0],
         "CI_upper": adj_ci[1], "p_value": adj_p, "R_squared": adj_r2, "N": len(adj_temp)},
    ]
    pd.DataFrame(adj_temp_rows).to_csv(
        os.path.join(TABLES_DIR, "table_adjusted_temporal_trend.csv"), index=False)
    print(f"  Saved: tables/table_adjusted_temporal_trend.csv")

    # ==========================================
    # 4i) WITHIN-DISEASE-SITE TEMPORAL TRENDS
    # ==========================================
    print("\n" + "=" * 50)
    print("4i) WITHIN-DISEASE-SITE TEMPORAL TRENDS")
    print("=" * 50)

    site_temporal_rows = []
    temporal_by_site = trials.dropna(subset=["intervention_12_months", "start_year", "disease_site"])

    for site in sorted(temporal_by_site["disease_site"].unique()):
        subset = temporal_by_site[temporal_by_site["disease_site"] == site]
        if len(subset) < MIN_GROUP_SIZE:
            continue

        y_s = subset["intervention_12_months"]
        x_s = subset["start_year"]

        rho_s, p_sp_s = stats.spearmanr(x_s, y_s)
        X_s = sm.add_constant(x_s)
        model_s = sm.OLS(y_s, X_s).fit()
        slope_s = model_s.params.iloc[1]
        p_ols_s = model_s.pvalues.iloc[1]
        ci_s = model_s.conf_int().iloc[1]
        r2_s = model_s.rsquared

        sig = "**" if p_ols_s < 0.05 else ""
        print(f"  {site} (N={len(subset)}): slope={slope_s:+.3f} d/yr "
              f"(95% CI: {ci_s[0]:.3f} to {ci_s[1]:.3f}), p={p_ols_s:.4f} {sig}")

        site_temporal_rows.append({
            "Disease_Site": site, "N": len(subset),
            "Slope": slope_s, "CI_lower": ci_s[0], "CI_upper": ci_s[1],
            "R2": r2_s, "p_OLS": p_ols_s,
            "Spearman_rho": rho_s, "p_Spearman": p_sp_s,
        })

    # Sort by slope magnitude
    site_temporal_df = pd.DataFrame(site_temporal_rows).sort_values("Slope", ascending=False)
    print(f"\n  Sites ranked by slope (strongest upward first):")
    for _, row in site_temporal_df.iterrows():
        sig = "**" if row["p_OLS"] < 0.05 else ""
        print(f"    {row['Disease_Site']}: {row['Slope']:+.3f} d/yr (p={row['p_OLS']:.4f}) {sig}")

    # Identify drivers
    sig_positive = site_temporal_df[(site_temporal_df["p_OLS"] < 0.05) & (site_temporal_df["Slope"] > 0)]
    if len(sig_positive) > 0:
        print(f"\n  Significant upward trends: {', '.join(sig_positive['Disease_Site'].tolist())}")
    else:
        print(f"\n  No individual sites have statistically significant upward trends")

    site_temporal_df.to_csv(
        os.path.join(TABLES_DIR, "table_within_site_temporal.csv"), index=False)
    print(f"  Saved: tables/table_within_site_temporal.csv")

    # ==========================================
    # 4j) ADJUSTED SPONSORSHIP COMPARISON
    # ==========================================
    print("\n" + "=" * 50)
    print("4j) ADJUSTED SPONSORSHIP COMPARISON")
    print("=" * 50)

    adj_sponsor_rows = []

    # Model A: Absolute TT
    print("\n--- Model A: Absolute TT (Intervention 12-Month) ---")
    adj_sp = trials.dropna(subset=["intervention_12_months", "sponsor_binary",
                                    "disease_site", "treatment_modality"]).copy()
    adj_sp = adj_sp[adj_sp["disease_site"].isin(valid_adj_sites)]
    adj_sp = adj_sp[adj_sp["treatment_modality"].isin(valid_adj_mods)]

    # Raw comparison
    ind_abs = adj_sp[adj_sp["sponsor_binary"] == "Industry"]["intervention_12_months"]
    noind_abs = adj_sp[adj_sp["sponsor_binary"] == "Non-Industry"]["intervention_12_months"]
    u_raw_abs, p_raw_abs = stats.mannwhitneyu(ind_abs.dropna(), noind_abs.dropna(), alternative="two-sided")
    print(f"  Raw Wilcoxon: Industry median={ind_abs.median():.1f}, "
          f"Non-Industry median={noind_abs.median():.1f}, p={p_raw_abs:.4f}")

    # Adjusted OLS
    formula_abs = (
        f'intervention_12_months ~ C(sponsor_binary, Treatment("Non-Industry")) + '
        f'C(disease_site, Treatment("{most_common_site_adj}")) + '
        f'C(treatment_modality, Treatment("Chemotherapy"))'
    )
    model_abs = ols_formula(formula_abs, data=adj_sp).fit()
    sponsor_key = 'C(sponsor_binary, Treatment("Non-Industry"))[T.Industry]'
    ind_coef_abs = model_abs.params[sponsor_key]
    ind_ci_abs = model_abs.conf_int().loc[sponsor_key]
    ind_p_abs = model_abs.pvalues[sponsor_key]

    print(f"  Adjusted OLS: Industry coef = {ind_coef_abs:.2f} days "
          f"(95% CI: {ind_ci_abs[0]:.2f} to {ind_ci_abs[1]:.2f}), p = {ind_p_abs:.4f}")
    print(f"  R² = {model_abs.rsquared:.4f}")
    if ind_p_abs < 0.05:
        print(f"  ** Industry effect SIGNIFICANT after adjustment **")
    else:
        print(f"  Industry effect not significant after adjustment")

    adj_sponsor_rows.append({
        "Outcome": "Absolute TT", "Model": "Raw Wilcoxon",
        "Industry_Coef": ind_abs.median() - noind_abs.median(),
        "p_value": p_raw_abs, "N": len(adj_sp),
    })
    adj_sponsor_rows.append({
        "Outcome": "Absolute TT", "Model": "Adjusted OLS",
        "Industry_Coef": ind_coef_abs,
        "CI_lower": ind_ci_abs[0], "CI_upper": ind_ci_abs[1],
        "p_value": ind_p_abs, "R_squared": model_abs.rsquared, "N": len(adj_sp),
    })

    results.append({
        "comparison": "Adjusted Sponsorship (Absolute TT)",
        "outcome": "Intervention 12mo TT (adj site+modality)",
        "n1": len(adj_sp), "U": ind_coef_abs, "p_value": ind_p_abs,
    })

    # Model B: Delta TT
    print("\n--- Model B: Delta TT ---")
    adj_sp_delta = trials.dropna(subset=["delta_12_months", "sponsor_binary",
                                          "disease_site", "treatment_modality"]).copy()
    adj_sp_delta = adj_sp_delta[adj_sp_delta["disease_site"].isin(valid_adj_sites)]
    adj_sp_delta = adj_sp_delta[adj_sp_delta["treatment_modality"].isin(valid_adj_mods)]

    # Raw comparison
    ind_delta_raw = adj_sp_delta[adj_sp_delta["sponsor_binary"] == "Industry"]["delta_12_months"]
    noind_delta_raw = adj_sp_delta[adj_sp_delta["sponsor_binary"] == "Non-Industry"]["delta_12_months"]
    u_raw_d, p_raw_d = stats.mannwhitneyu(ind_delta_raw.dropna(), noind_delta_raw.dropna(), alternative="two-sided")
    print(f"  Raw Wilcoxon: Industry delta median={ind_delta_raw.median():.1f}, "
          f"Non-Industry delta median={noind_delta_raw.median():.1f}, p={p_raw_d:.4f}")

    # Adjusted OLS
    formula_delta = (
        f'delta_12_months ~ C(sponsor_binary, Treatment("Non-Industry")) + '
        f'C(disease_site, Treatment("{most_common_site_adj}")) + '
        f'C(treatment_modality, Treatment("Chemotherapy"))'
    )
    model_delta = ols_formula(formula_delta, data=adj_sp_delta).fit()
    ind_coef_d = model_delta.params[sponsor_key]
    ind_ci_d = model_delta.conf_int().loc[sponsor_key]
    ind_p_d = model_delta.pvalues[sponsor_key]

    print(f"  Adjusted OLS: Industry coef = {ind_coef_d:.2f} days "
          f"(95% CI: {ind_ci_d[0]:.2f} to {ind_ci_d[1]:.2f}), p = {ind_p_d:.4f}")
    print(f"  R² = {model_delta.rsquared:.4f}")
    if ind_p_d < 0.05:
        print(f"  ** Industry delta effect SIGNIFICANT after adjustment **")
    else:
        print(f"  Industry delta effect not significant after adjustment")

    adj_sponsor_rows.append({
        "Outcome": "Delta TT", "Model": "Raw Wilcoxon",
        "Industry_Coef": ind_delta_raw.median() - noind_delta_raw.median(),
        "p_value": p_raw_d, "N": len(adj_sp_delta),
    })
    adj_sponsor_rows.append({
        "Outcome": "Delta TT", "Model": "Adjusted OLS",
        "Industry_Coef": ind_coef_d,
        "CI_lower": ind_ci_d[0], "CI_upper": ind_ci_d[1],
        "p_value": ind_p_d, "R_squared": model_delta.rsquared, "N": len(adj_sp_delta),
    })

    results.append({
        "comparison": "Adjusted Sponsorship (Delta TT)",
        "outcome": "Delta TT (adj site+modality)",
        "n1": len(adj_sp_delta), "U": ind_coef_d, "p_value": ind_p_d,
    })

    pd.DataFrame(adj_sponsor_rows).to_csv(
        os.path.join(TABLES_DIR, "table_adjusted_sponsorship.csv"), index=False)
    print(f"  Saved: tables/table_adjusted_sponsorship.csv")

    # ==========================================
    # 4k) FUNDER x TIME INTERACTION (ADJUSTED)
    # ==========================================
    print("\n" + "=" * 50)
    print("4k) FUNDER x TIME INTERACTION (ADJUSTED)")
    print("=" * 50)

    adj_inter = trials.dropna(subset=["intervention_12_months", "start_year",
                                       "sponsor_binary", "disease_site",
                                       "treatment_modality"]).copy()
    adj_inter = adj_inter[adj_inter["disease_site"].isin(valid_adj_sites)]
    adj_inter = adj_inter[adj_inter["treatment_modality"].isin(valid_adj_mods)]

    # Unadjusted interaction (replicating 4e for comparison)
    adj_inter["is_industry"] = (adj_inter["sponsor_binary"] == "Industry").astype(int)
    adj_inter["year_x_industry"] = adj_inter["start_year"] * adj_inter["is_industry"]
    X_unadj = sm.add_constant(adj_inter[["start_year", "is_industry", "year_x_industry"]])
    model_unadj_inter = sm.OLS(adj_inter["intervention_12_months"], X_unadj).fit()
    unadj_coef = model_unadj_inter.params["year_x_industry"]
    unadj_p = model_unadj_inter.pvalues["year_x_industry"]
    print(f"\n  UNADJUSTED interaction (replicating 4e on this subset):")
    print(f"    Interaction coef = {unadj_coef:.3f}, p = {unadj_p:.4f}")

    # Adjusted interaction
    inter_formula = (
        f'intervention_12_months ~ start_year * C(sponsor_binary, Treatment("Non-Industry")) + '
        f'C(disease_site, Treatment("{most_common_site_adj}")) + '
        f'C(treatment_modality, Treatment("Chemotherapy"))'
    )
    model_adj_inter = ols_formula(inter_formula, data=adj_inter).fit()

    # Extract key terms
    start_year_key = "start_year"
    industry_key = 'C(sponsor_binary, Treatment("Non-Industry"))[T.Industry]'
    interaction_key = 'start_year:C(sponsor_binary, Treatment("Non-Industry"))[T.Industry]'

    adj_pub_slope = model_adj_inter.params[start_year_key]
    adj_pub_p = model_adj_inter.pvalues[start_year_key]
    adj_ind_coef = model_adj_inter.params[industry_key]
    adj_ind_p = model_adj_inter.pvalues[industry_key]
    adj_inter_coef = model_adj_inter.params[interaction_key]
    adj_inter_ci = model_adj_inter.conf_int().loc[interaction_key]
    adj_inter_p = model_adj_inter.pvalues[interaction_key]

    # Implied slopes
    non_ind_slope = adj_pub_slope
    ind_slope = adj_pub_slope + adj_inter_coef

    print(f"\n  ADJUSTED interaction (+ disease site + treatment modality):")
    print(f"    Non-Industry adjusted slope: {non_ind_slope:+.3f} d/yr (p={adj_pub_p:.4f})")
    print(f"    Industry adjusted slope: {ind_slope:+.3f} d/yr (= {non_ind_slope:.3f} + {adj_inter_coef:.3f})")
    print(f"    Interaction coefficient: {adj_inter_coef:+.3f} "
          f"(95% CI: {adj_inter_ci[0]:.3f} to {adj_inter_ci[1]:.3f}), p = {adj_inter_p:.4f}")
    print(f"    R² = {model_adj_inter.rsquared:.4f}")

    if adj_inter_p < 0.05:
        print(f"    ** Industry temporal acceleration is SIGNIFICANT after adjustment **")
    else:
        print(f"    Industry temporal acceleration not significant after adjustment")

    print(f"\n  COMPARISON:")
    print(f"    Unadjusted interaction: {unadj_coef:+.3f} (p={unadj_p:.4f})")
    print(f"    Adjusted interaction:   {adj_inter_coef:+.3f} (p={adj_inter_p:.4f})")

    results.append({
        "comparison": "Adjusted Funder x Time Interaction",
        "outcome": "Intervention 12mo TT (adj site+modality)",
        "n1": len(adj_inter), "U": adj_inter_coef, "p_value": adj_inter_p,
    })

    inter_rows = [
        {"Term": "start_year (Non-Industry slope)", "Coefficient": non_ind_slope,
         "p_value": adj_pub_p},
        {"Term": "Industry (main effect)", "Coefficient": adj_ind_coef,
         "p_value": adj_ind_p},
        {"Term": "start_year x Industry (interaction)", "Coefficient": adj_inter_coef,
         "CI_lower": adj_inter_ci[0], "CI_upper": adj_inter_ci[1],
         "p_value": adj_inter_p},
        {"Term": "Industry implied slope", "Coefficient": ind_slope},
        {"Term": "R_squared", "Coefficient": model_adj_inter.rsquared},
        {"Term": "N", "Coefficient": len(adj_inter)},
    ]
    pd.DataFrame(inter_rows).to_csv(
        os.path.join(TABLES_DIR, "table_funder_time_interaction.csv"), index=False)
    print(f"  Saved: tables/table_funder_time_interaction.csv")

    # ==========================================
    # Save all results
    # ==========================================
    print("\n--- Saving results ---")
    results_df = pd.DataFrame(results)
    results_df.to_csv(os.path.join(TABLES_DIR, "table2_comparative_analyses.csv"), index=False)
    print(f"  Saved: tables/table2_comparative_analyses.csv")

    print("\n" + "=" * 60)
    print("STEP 4 COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
