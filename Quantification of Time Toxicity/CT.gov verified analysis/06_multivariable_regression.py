#!/usr/bin/env python3
"""
Step 6: Multivariable Logistic Regression

Identifies independent predictors of "High Time Toxicity" (above median)
at the arm level. Also runs sensitivity analyses.
"""

import os
import sys
import warnings
import pandas as pd
import numpy as np
from scipy import stats
import statsmodels.api as sm
from statsmodels.formula.api import logit as logit_formula
from statsmodels.stats.outliers_influence import variance_inflation_factor
from sklearn.metrics import roc_auc_score

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import DATA_DIR, TABLES_DIR, FIGURES_DIR, MIN_GROUP_SIZE

warnings.filterwarnings("ignore")


def hosmer_lemeshow(model, y, n_groups=10):
    """Compute Hosmer-Lemeshow goodness-of-fit test."""
    predicted = model.predict()
    df = pd.DataFrame({"y": y, "p": predicted})
    df["group"] = pd.qcut(df["p"], q=n_groups, duplicates="drop")
    grouped = df.groupby("group").agg(
        obs_events=("y", "sum"),
        obs_total=("y", "count"),
        pred_events=("p", "sum"),
    )
    grouped["expected_non_events"] = grouped["obs_total"] - grouped["pred_events"]
    grouped["obs_non_events"] = grouped["obs_total"] - grouped["obs_events"]

    # HL statistic
    hl_stat = 0
    for _, row in grouped.iterrows():
        if row["pred_events"] > 0:
            hl_stat += (row["obs_events"] - row["pred_events"]) ** 2 / row["pred_events"]
        if row["expected_non_events"] > 0:
            hl_stat += (row["obs_non_events"] - row["expected_non_events"]) ** 2 / row["expected_non_events"]

    p_value = 1 - stats.chi2.cdf(hl_stat, n_groups - 2)
    return hl_stat, p_value


def main():
    print("=" * 60)
    print("STEP 6: Multivariable Logistic Regression")
    print("=" * 60)

    # Load arm-level enriched data
    arms_all = pd.read_csv(os.path.join(DATA_DIR, "enriched_arms.csv"))
    print(f"  Total arms (all): {len(arms_all)}")

    # Filter to primary arms only (pos_idx=0) to avoid pseudo-replication
    # from multi-arm trials contributing secondary arms
    arms = arms_all[arms_all["pos_idx"] == 0].copy()
    print(f"  Primary arms (pos_idx=0): {len(arms)}")
    print(f"  Secondary arms excluded: {len(arms_all) - len(arms)}")

    # ==========================================
    # PREPARE DATA
    # ==========================================
    print("\n--- Preparing analysis dataset ---")

    # Keep only arms with valid TT and metadata
    df = arms.dropna(subset=["12_months", "disease_site", "treatment_modality",
                              "sponsor_binary", "start_year"]).copy()
    df = df[df["12_months"] > 0]
    print(f"  Arms with complete data: {len(df)}")

    # Define High TT (above median)
    median_tt = df["12_months"].median()
    df["high_tt"] = (df["12_months"] > median_tt).astype(int)
    print(f"  Median TT threshold: {median_tt:.1f} days")
    print(f"  High TT: {df['high_tt'].sum()} ({100*df['high_tt'].mean():.1f}%)")
    print(f"  Low TT: {(1-df['high_tt']).sum():.0f} ({100*(1-df['high_tt'].mean()):.1f}%)")

    # Center trial start year
    df["year_centered"] = df["start_year"] - df["start_year"].mean()
    print(f"  Year centered at: {df['start_year'].mean():.1f}")

    # Filter disease sites with sufficient N
    site_counts = df["disease_site"].value_counts()
    valid_sites = site_counts[site_counts >= MIN_GROUP_SIZE].index.tolist()
    df = df[df["disease_site"].isin(valid_sites)]
    print(f"  Disease sites included: {valid_sites}")

    # Filter treatment modalities with sufficient N
    mod_counts = df["treatment_modality"].value_counts()
    valid_mods = mod_counts[mod_counts >= MIN_GROUP_SIZE].index.tolist()
    df = df[df["treatment_modality"].isin(valid_mods)]
    print(f"  Treatment modalities included: {valid_mods}")
    print(f"  Final analysis N: {len(df)}")

    # Reference categories
    most_common_site = df["disease_site"].value_counts().idxmax()
    print(f"  Reference disease site: {most_common_site}")
    print(f"  Reference treatment: Chemotherapy")
    print(f"  Reference sponsor: Non-Industry")
    print(f"  Reference arm: control")

    # ==========================================
    # PRIMARY MODEL: Logistic Regression
    # ==========================================
    print("\n" + "=" * 50)
    print("PRIMARY MODEL: Logistic Regression")
    print("=" * 50)

    formula = (
        f'high_tt ~ C(sponsor_binary, Treatment("Non-Industry")) + '
        f'C(disease_site, Treatment("{most_common_site}")) + '
        f'C(treatment_modality, Treatment("Chemotherapy")) + '
        f'year_centered + '
        f'C(intervention_type, Treatment("control"))'
    )

    model = logit_formula(formula, data=df).fit(disp=0)

    print("\n" + str(model.summary2()))

    # ==========================================
    # ODDS RATIOS TABLE
    # ==========================================
    print("\n" + "=" * 50)
    print("ODDS RATIOS (95% CI)")
    print("=" * 50)

    params = model.params
    conf = model.conf_int()
    pvalues = model.pvalues

    or_rows = []
    print(f"\n  {'Predictor':<50} {'OR':>8} {'95% CI':>20} {'p':>10}")
    print(f"  {'─'*90}")

    for name in params.index:
        if name == "Intercept":
            continue
        odds_ratio = np.exp(params[name])
        ci_lo = np.exp(conf.loc[name, 0])
        ci_hi = np.exp(conf.loc[name, 1])
        p = pvalues[name]

        # Clean up predictor name
        clean_name = name.replace("C(sponsor_binary, Treatment(\"Non-Industry\"))", "Sponsor: ")
        clean_name = clean_name.replace(f"C(disease_site, Treatment(\"{most_common_site}\"))", "Site: ")
        clean_name = clean_name.replace("C(treatment_modality, Treatment(\"Chemotherapy\"))", "Treatment: ")
        clean_name = clean_name.replace("C(intervention_type, Treatment(\"control\"))", "Arm: ")
        clean_name = clean_name.replace("[T.", "").replace("]", "")
        if name == "year_centered":
            clean_name = "Trial Start Year (per year)"

        sig = "*" if p < 0.05 else ("**" if p < 0.01 else "")
        print(f"  {clean_name:<50} {odds_ratio:>8.2f} ({ci_lo:>6.2f}-{ci_hi:>6.2f})  {p:>10.4f} {sig}")

        or_rows.append({
            "Predictor": clean_name,
            "OR": odds_ratio,
            "CI_lower": ci_lo,
            "CI_upper": ci_hi,
            "p_value": p,
            "coefficient": params[name],
        })

    or_df = pd.DataFrame(or_rows)

    # ==========================================
    # MODEL DIAGNOSTICS
    # ==========================================
    print("\n" + "=" * 50)
    print("MODEL DIAGNOSTICS")
    print("=" * 50)

    # AUC-ROC
    y_pred_prob = model.predict(df)
    auc = roc_auc_score(df["high_tt"], y_pred_prob)
    print(f"\n  AUC-ROC: {auc:.3f}")

    # Hosmer-Lemeshow
    hl_stat, hl_p = hosmer_lemeshow(model, df["high_tt"])
    print(f"  Hosmer-Lemeshow: chi2={hl_stat:.2f}, p={hl_p:.4f}")
    if hl_p > 0.05:
        print(f"  Good fit (p > 0.05)")
    else:
        print(f"  Poor fit (p < 0.05)")

    # Pseudo R-squared
    print(f"  Pseudo R² (McFadden): {model.prsquared:.4f}")
    print(f"  Log-Likelihood: {model.llf:.1f}")
    print(f"  AIC: {model.aic:.1f}")
    print(f"  BIC: {model.bic:.1f}")

    # VIF (using design matrix)
    print("\n--- Variance Inflation Factors ---")
    X = pd.get_dummies(df[["sponsor_binary", "disease_site", "treatment_modality",
                           "intervention_type", "year_centered"]], drop_first=True)
    X = sm.add_constant(X)
    # Ensure all columns are float for VIF computation
    X = X.astype(float)
    try:
        vif_data = pd.DataFrame()
        vif_data["Variable"] = X.columns
        vif_data["VIF"] = [variance_inflation_factor(X.values, i) for i in range(X.shape[1])]
        for _, row in vif_data.iterrows():
            if row["Variable"] != "const":
                flag = " *** HIGH" if row["VIF"] > 5 else ""
                print(f"  {row['Variable']:<40} VIF = {row['VIF']:.2f}{flag}")
    except Exception as e:
        print(f"  VIF computation skipped: {e}")

    # ==========================================
    # SENSITIVITY ANALYSIS 1: Linear Regression on log(TT)
    # ==========================================
    print("\n" + "=" * 50)
    print("SENSITIVITY: Linear Regression on log(TT)")
    print("=" * 50)

    df["log_tt"] = np.log(df["12_months"])
    formula_linear = (
        f'log_tt ~ C(sponsor_binary, Treatment("Non-Industry")) + '
        f'C(disease_site, Treatment("{most_common_site}")) + '
        f'C(treatment_modality, Treatment("Chemotherapy")) + '
        f'year_centered + '
        f'C(intervention_type, Treatment("control"))'
    )
    model_linear = sm.OLS.from_formula(formula_linear, data=df).fit()
    print(f"\n  R² = {model_linear.rsquared:.4f}")
    print(f"  Adjusted R² = {model_linear.rsquared_adj:.4f}")
    print(f"  F-statistic p = {model_linear.f_pvalue:.6f}")

    # Print significant predictors
    print(f"\n  Significant predictors (p<0.05):")
    for name in model_linear.params.index:
        if name == "Intercept":
            continue
        p = model_linear.pvalues[name]
        if p < 0.05:
            coef = model_linear.params[name]
            pct_change = (np.exp(coef) - 1) * 100
            print(f"    {name}: coef={coef:.3f} ({pct_change:+.1f}% change in TT), p={p:.4f}")

    # ==========================================
    # SAVE RESULTS
    # ==========================================
    print("\n--- Saving regression results ---")

    or_df.to_csv(os.path.join(TABLES_DIR, "table3_regression_results.csv"), index=False)

    # LaTeX table
    with open(os.path.join(TABLES_DIR, "table3_regression_results.tex"), "w") as f:
        f.write("\\begin{table}[htbp]\n")
        f.write("\\centering\n")
        f.write("\\caption{Multivariable Logistic Regression: Predictors of High Time Toxicity}\n")
        f.write("\\begin{tabular}{lccc}\n")
        f.write("\\toprule\n")
        f.write("Predictor & OR & 95\\% CI & p-value \\\\\n")
        f.write("\\midrule\n")
        for _, row in or_df.iterrows():
            pred = row["Predictor"].replace("_", "\\_").replace("%", "\\%")
            sig = "$^*$" if row["p_value"] < 0.05 else ""
            f.write(f"{pred} & {row['OR']:.2f} & ({row['CI_lower']:.2f}-{row['CI_upper']:.2f}) & {row['p_value']:.4f}{sig} \\\\\n")
        f.write("\\bottomrule\n")
        f.write("\\multicolumn{4}{l}{\\footnotesize AUC-ROC = " + f"{auc:.3f}" + ", Hosmer-Lemeshow p = " + f"{hl_p:.3f}" + "} \\\\\n")
        f.write("\\end{tabular}\n")
        f.write("\\end{table}\n")

    # Save model summary for figure generation
    or_df.to_csv(os.path.join(DATA_DIR, "regression_odds_ratios.csv"), index=False)

    print(f"  Saved: tables/table3_regression_results.csv")
    print(f"  Saved: tables/table3_regression_results.tex")
    print(f"  Saved: data/regression_odds_ratios.csv")

    print("\n" + "=" * 60)
    print("STEP 6 COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
