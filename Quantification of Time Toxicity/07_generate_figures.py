#!/usr/bin/env python3
"""
Step 7: Generate all publication-quality figures.

8 figures covering distributions, comparisons, components, and regression.
"""

import os
import sys
import warnings
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import statsmodels.api as sm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import DATA_DIR, FIGURES_DIR, TABLES_DIR, CATEGORIES, TIMEPOINTS, MIN_GROUP_SIZE

warnings.filterwarnings("ignore")

# Global style
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 11,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.1,
    "axes.spines.top": False,
    "axes.spines.right": False,
})
sns.set_palette("colorblind")


def save_fig(fig, name):
    path = os.path.join(FIGURES_DIR, name)
    fig.savefig(path)
    plt.close(fig)
    print(f"  Saved: figures/{name}")


def fig1_tt_distribution(arms):
    """Dual violin plot: intervention vs control 12-month TT."""
    fig, ax = plt.subplots(figsize=(8, 5))

    data = arms[arms["12_months"].notna()].copy()
    data["Arm Type"] = data["intervention_type"].map({
        "intervention": "Intervention",
        "control": "Control"
    })

    parts = ax.violinplot(
        [data[data["Arm Type"] == "Intervention"]["12_months"].values,
         data[data["Arm Type"] == "Control"]["12_months"].values],
        positions=[1, 2], showmeans=False, showmedians=True, showextrema=False
    )

    colors = sns.color_palette("colorblind", 2)
    for i, pc in enumerate(parts["bodies"]):
        pc.set_facecolor(colors[i])
        pc.set_alpha(0.7)
    parts["cmedians"].set_color("black")

    # Add box plot overlay
    bp = ax.boxplot(
        [data[data["Arm Type"] == "Intervention"]["12_months"].values,
         data[data["Arm Type"] == "Control"]["12_months"].values],
        positions=[1, 2], widths=0.15, showfliers=False,
        patch_artist=True, medianprops=dict(color="black", linewidth=2)
    )
    for i, patch in enumerate(bp["boxes"]):
        patch.set_facecolor(colors[i])
        patch.set_alpha(0.9)

    ax.set_xticks([1, 2])
    ax.set_xticklabels(["Intervention\n(N={})".format(len(data[data["Arm Type"] == "Intervention"])),
                          "Control\n(N={})".format(len(data[data["Arm Type"] == "Control"]))])
    ax.set_ylabel("Healthcare Contact Days at 12 Months")
    ax.set_title("Distribution of Time Toxicity by Arm Type")

    # Annotate medians
    for i, arm in enumerate(["Intervention", "Control"]):
        med = data[data["Arm Type"] == arm]["12_months"].median()
        iqr = data[data["Arm Type"] == arm]["12_months"].quantile([0.25, 0.75])
        ax.annotate(f"Median: {med:.0f}\nIQR: {iqr.iloc[0]:.0f}-{iqr.iloc[1]:.0f}",
                     xy=(i + 1, med), xytext=(i + 1.35, med + 15),
                     fontsize=9, ha="center",
                     arrowprops=dict(arrowstyle="->", color="gray", lw=0.8))

    save_fig(fig, "fig1_tt_distribution.pdf")


def fig2_delta_tt(trials):
    """Histogram of Delta TT with vertical line at zero."""
    fig, ax = plt.subplots(figsize=(8, 5))

    delta = trials["delta_12_months"].dropna()

    ax.hist(delta, bins=50, color=sns.color_palette("colorblind")[0],
            alpha=0.7, edgecolor="white")
    ax.axvline(x=0, color="red", linestyle="--", linewidth=2, label="Zero")
    ax.axvline(x=delta.median(), color="black", linestyle="-", linewidth=2,
               label=f"Median: {delta.median():.1f}")

    ax.set_xlabel("Delta Time Toxicity (Intervention - Control, days)")
    ax.set_ylabel("Number of Trials")
    ax.set_title("Distribution of Incremental Time Toxicity")
    ax.legend()

    # Annotate
    n_pos = (delta > 0).sum()
    n_zero = (delta == 0).sum()
    n_neg = (delta < 0).sum()
    textstr = f"Positive (intervention > control): {n_pos} ({100*n_pos/len(delta):.1f}%)\n"
    textstr += f"Zero: {n_zero} ({100*n_zero/len(delta):.1f}%)\n"
    textstr += f"Negative (control > intervention): {n_neg} ({100*n_neg/len(delta):.1f}%)"
    ax.text(0.97, 0.97, textstr, transform=ax.transAxes, fontsize=9,
            verticalalignment="top", horizontalalignment="right",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))

    save_fig(fig, "fig2_delta_tt_distribution.pdf")


def fig3_sponsorship(trials):
    """Box/violin plot: TT by sponsorship."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Left: Intervention arm TT
    data = trials.dropna(subset=["intervention_12_months", "sponsor_binary"])
    sns.violinplot(data=data, x="sponsor_binary", y="intervention_12_months",
                   ax=axes[0], inner="box", palette="colorblind", cut=0)
    axes[0].set_xlabel("")
    axes[0].set_ylabel("Healthcare Contact Days at 12 Months")
    axes[0].set_title("Intervention Arm TT by Sponsorship")

    # Add p-value
    ind = data[data["sponsor_binary"] == "Industry"]["intervention_12_months"]
    noind = data[data["sponsor_binary"] == "Non-Industry"]["intervention_12_months"]
    _, p = stats.mannwhitneyu(ind, noind, alternative="two-sided")
    axes[0].annotate(f"p = {p:.3f}", xy=(0.5, 0.95), xycoords="axes fraction",
                     ha="center", fontsize=10, fontweight="bold")

    # Right: Delta TT
    data2 = trials.dropna(subset=["delta_12_months", "sponsor_binary"])
    sns.violinplot(data=data2, x="sponsor_binary", y="delta_12_months",
                   ax=axes[1], inner="box", palette="colorblind", cut=0)
    axes[1].axhline(y=0, color="red", linestyle="--", alpha=0.5)
    axes[1].set_xlabel("")
    axes[1].set_ylabel("Delta TT (Intervention - Control, days)")
    axes[1].set_title("Incremental TT by Sponsorship")

    ind_d = data2[data2["sponsor_binary"] == "Industry"]["delta_12_months"]
    noind_d = data2[data2["sponsor_binary"] == "Non-Industry"]["delta_12_months"]
    _, p2 = stats.mannwhitneyu(ind_d, noind_d, alternative="two-sided")
    axes[1].annotate(f"p < 0.001" if p2 < 0.001 else f"p = {p2:.3f}",
                     xy=(0.5, 0.95), xycoords="axes fraction",
                     ha="center", fontsize=10, fontweight="bold")

    fig.tight_layout()
    save_fig(fig, "fig3_sponsorship_comparison.pdf")


def fig4_disease_site(trials):
    """Grouped box plot by disease site, ordered by median TT."""
    fig, ax = plt.subplots(figsize=(12, 6))

    data = trials.dropna(subset=["intervention_12_months", "disease_site"])
    # Order by median
    order = data.groupby("disease_site")["intervention_12_months"].median().sort_values(ascending=False).index

    sns.boxplot(data=data, x="disease_site", y="intervention_12_months",
                order=order, ax=ax, palette="colorblind", fliersize=2)

    ax.set_xlabel("Disease Site")
    ax.set_ylabel("Healthcare Contact Days at 12 Months")
    ax.set_title("Time Toxicity by Disease Site (Intervention Arms)")
    ax.tick_params(axis="x", rotation=45)

    # Annotate N below each box
    for i, site in enumerate(order):
        n = len(data[data["disease_site"] == site])
        med = data[data["disease_site"] == site]["intervention_12_months"].median()
        ax.annotate(f"N={n}", xy=(i, -8), fontsize=8, ha="center", color="gray")

    # Add overall median line
    overall_med = data["intervention_12_months"].median()
    ax.axhline(y=overall_med, color="red", linestyle="--", alpha=0.5,
               label=f"Overall median: {overall_med:.0f} days")
    ax.legend(loc="upper right")

    save_fig(fig, "fig4_disease_site_comparison.pdf")


def fig5_treatment_type(trials):
    """Violin plot by treatment modality."""
    fig, ax = plt.subplots(figsize=(10, 6))

    data = trials.dropna(subset=["intervention_12_months", "treatment_modality"])
    # Filter to modalities with N >= MIN_GROUP_SIZE
    counts = data["treatment_modality"].value_counts()
    valid = counts[counts >= MIN_GROUP_SIZE].index
    data = data[data["treatment_modality"].isin(valid)]

    order = data.groupby("treatment_modality")["intervention_12_months"].median().sort_values(ascending=False).index

    sns.violinplot(data=data, x="treatment_modality", y="intervention_12_months",
                   order=order, ax=ax, inner="box", palette="colorblind", cut=0)

    ax.set_xlabel("Treatment Modality")
    ax.set_ylabel("Healthcare Contact Days at 12 Months")
    ax.set_title("Time Toxicity by Treatment Modality (Intervention Arms)")
    ax.tick_params(axis="x", rotation=30)

    for i, mod in enumerate(order):
        n = len(data[data["treatment_modality"] == mod])
        ax.annotate(f"N={n}", xy=(i, -8), fontsize=8, ha="center", color="gray")

    save_fig(fig, "fig5_treatment_type_comparison.pdf")


def fig6_temporal_trend(trials):
    """Scatter + OLS regression + 95% CI: TT vs publication year."""
    fig, ax = plt.subplots(figsize=(10, 6))

    data = trials.dropna(subset=["intervention_12_months", "start_year"]).copy()

    # Scatter with jitter
    jitter_x = data["start_year"] + np.random.normal(0, 0.15, len(data))
    ax.scatter(jitter_x, data["intervention_12_months"], alpha=0.15, s=15,
              c=sns.color_palette("colorblind")[0], edgecolors="none")

    # Yearly medians
    yearly = data.groupby("start_year")["intervention_12_months"].agg(["median", "count"])
    ax.plot(yearly.index, yearly["median"], "ro-", markersize=6, linewidth=2,
            label="Yearly Median", zorder=5)

    # OLS regression line with CI
    X = sm.add_constant(data["start_year"])
    model = sm.OLS(data["intervention_12_months"], X).fit()
    x_pred = np.linspace(data["start_year"].min(), data["start_year"].max(), 100)
    X_pred = sm.add_constant(x_pred)
    y_pred = model.predict(X_pred)
    pred = model.get_prediction(X_pred)
    ci = pred.conf_int(alpha=0.05)

    ax.plot(x_pred, y_pred, "b-", linewidth=2,
            label=f"OLS: {model.params.iloc[1]:.2f} days/yr (p={model.pvalues.iloc[1]:.3f})")
    ax.fill_between(x_pred, ci[:, 0], ci[:, 1], alpha=0.15, color="blue")

    # Spearman
    rho, p_sp = stats.spearmanr(data["start_year"], data["intervention_12_months"])

    ax.set_xlabel("Trial Start Year")
    ax.set_ylabel("Healthcare Contact Days at 12 Months")
    ax.set_title(f"Temporal Trend in Time Toxicity (Spearman ρ={rho:.3f}, p={p_sp:.4f})")
    ax.legend(loc="upper left")
    ax.set_xlim(data["start_year"].min() - 0.5, data["start_year"].max() + 0.5)

    save_fig(fig, "fig6_temporal_trend.pdf")


def fig7_component_breakdown(tables_dir):
    """100% stacked bar chart of TT categories by disease site."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    # By disease site
    site_df = pd.read_csv(os.path.join(tables_dir, "component_by_disease_site.csv"))
    site_df = site_df.sort_values("Median TT", ascending=True)

    cat_labels = ["Core Treatment", "Imaging/Diagnostics", "Labs", "Clinic Visits"]
    cat_cols = ["Mean % core_treatment", "Mean % imaging_diagnostics", "Mean % labs", "Mean % clinic_visits"]
    colors = sns.color_palette("colorblind", 4)

    sites = site_df["Disease Site"].values
    bottom = np.zeros(len(sites))
    for i, (col, label) in enumerate(zip(cat_cols, cat_labels)):
        vals = site_df[col].values
        axes[0].barh(sites, vals, left=bottom, color=colors[i], label=label, edgecolor="white", linewidth=0.5)
        # Add percentage text for large segments
        for j, v in enumerate(vals):
            if v > 8:
                axes[0].text(bottom[j] + v / 2, j, f"{v:.0f}%", ha="center", va="center", fontsize=8)
        bottom += vals

    axes[0].set_xlabel("Percentage of Total Time Toxicity")
    axes[0].set_title("TT Composition by Disease Site")
    axes[0].legend(loc="lower right", fontsize=8)
    axes[0].set_xlim(0, 100)

    # By treatment modality
    mod_df = pd.read_csv(os.path.join(tables_dir, "component_by_modality.csv"))
    mod_df = mod_df.sort_values("Median TT", ascending=True)

    mods = mod_df["Treatment Modality"].values
    bottom = np.zeros(len(mods))
    for i, (col, label) in enumerate(zip(cat_cols, cat_labels)):
        vals = mod_df[col].values
        axes[1].barh(mods, vals, left=bottom, color=colors[i], label=label, edgecolor="white", linewidth=0.5)
        for j, v in enumerate(vals):
            if v > 8:
                axes[1].text(bottom[j] + v / 2, j, f"{v:.0f}%", ha="center", va="center", fontsize=8)
        bottom += vals

    axes[1].set_xlabel("Percentage of Total Time Toxicity")
    axes[1].set_title("TT Composition by Treatment Modality")
    axes[1].legend(loc="lower right", fontsize=8)
    axes[1].set_xlim(0, 100)

    fig.tight_layout()
    save_fig(fig, "fig7_component_breakdown.pdf")


def fig8_forest_plot():
    """Forest plot of logistic regression odds ratios."""
    or_df = pd.read_csv(os.path.join(DATA_DIR, "regression_odds_ratios.csv"))

    # Exclude Procedure (quasi-separation) and Intercept
    or_df = or_df[~or_df["Predictor"].str.contains("Procedure")]

    fig, ax = plt.subplots(figsize=(10, 8))

    y_positions = list(range(len(or_df)))
    y_positions.reverse()

    for i, (_, row) in enumerate(or_df.iterrows()):
        y = y_positions[i]
        or_val = row["OR"]
        ci_lo = row["CI_lower"]
        ci_hi = row["CI_upper"]
        p = row["p_value"]

        # Cap CI for display
        ci_hi_display = min(ci_hi, 8)

        color = "darkblue" if p < 0.05 else "gray"
        marker = "D" if p < 0.05 else "o"

        ax.plot(or_val, y, marker, color=color, markersize=8, zorder=5)
        ax.plot([ci_lo, ci_hi_display], [y, y], "-", color=color, linewidth=2)

        if ci_hi > 8:
            ax.annotate("→", xy=(7.8, y), fontsize=12, color=color)

    ax.axvline(x=1, color="red", linestyle="--", linewidth=1, alpha=0.7)

    ax.set_yticks(y_positions)
    ax.set_yticklabels(or_df["Predictor"].values, fontsize=9)
    ax.set_xlabel("Odds Ratio (95% CI)")
    ax.set_title("Independent Predictors of High Time Toxicity\n(Multivariable Logistic Regression)")
    ax.set_xscale("log")
    ax.set_xlim(0.02, 8)

    # Add significance annotation
    ax.text(0.98, 0.02, "Blue = p < 0.05\nGray = not significant\nRef: Chemo, Heme, Non-Industry, Control",
            transform=ax.transAxes, fontsize=8, ha="right", va="bottom",
            bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.8))

    fig.tight_layout()
    save_fig(fig, "fig8_forest_plot_regression.pdf")


def fig9_industry_temporal_trend(trials):
    """Stratified temporal trend: Industry vs Non-Industry with separate regression lines."""
    fig, ax = plt.subplots(figsize=(10, 6))

    data = trials.dropna(subset=["intervention_12_months", "start_year", "sponsor_binary"])
    colors = {"Industry": sns.color_palette("colorblind")[0],
              "Non-Industry": sns.color_palette("colorblind")[1]}

    for sponsor in ["Industry", "Non-Industry"]:
        subset = data[data["sponsor_binary"] == sponsor]
        y_s = subset["intervention_12_months"]
        x_s = subset["start_year"]

        # Scatter with jitter
        jx = x_s + np.random.normal(0, 0.15, len(subset))
        ax.scatter(jx, y_s, alpha=0.15, s=12,
                   c=colors[sponsor], edgecolors="none")

        # OLS regression line
        X = sm.add_constant(x_s)
        model = sm.OLS(y_s, X).fit()
        x_pred = np.linspace(data["start_year"].min(), data["start_year"].max(), 100)
        y_pred = model.predict(sm.add_constant(x_pred))
        pred = model.get_prediction(sm.add_constant(x_pred))
        ci = pred.conf_int(alpha=0.05)

        slope = model.params.iloc[1]
        p = model.pvalues.iloc[1]
        p_str = "p<0.001" if p < 0.001 else f"p={p:.3f}"
        label = f"{sponsor}: {slope:+.2f} d/yr ({p_str})"

        ax.plot(x_pred, y_pred, "-", color=colors[sponsor], linewidth=2.5, label=label)
        ax.fill_between(x_pred, ci[:, 0], ci[:, 1], alpha=0.1, color=colors[sponsor])

        # Yearly medians
        yearly = subset.groupby("start_year")["intervention_12_months"].median()
        ax.plot(yearly.index, yearly.values, "o-", color=colors[sponsor],
                markersize=5, linewidth=1, alpha=0.6)

    ax.set_xlabel("Trial Start Year")
    ax.set_ylabel("Healthcare Contact Days at 12 Months")
    ax.set_title("Temporal Trend in Time Toxicity by Sponsorship")
    ax.legend(loc="upper left", fontsize=10)
    ax.set_xlim(data["start_year"].min() - 0.5, data["start_year"].max() + 0.5)
    ax.set_ylim(bottom=0)

    fig.tight_layout()
    save_fig(fig, "fig9_industry_temporal_trend.pdf")


def fig10_front_loading(arms):
    """Paired bar chart: early vs late accumulation rate by treatment modality + trajectory."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    data = arms.dropna(subset=["3_months", "12_months"]).copy()
    data = data[data["12_months"] > 0]
    data["early_rate"] = data["3_months"] / 3.0
    data["late_rate"] = (data["12_months"] - data["3_months"]) / 9.0

    # Left panel: by treatment modality
    mod_summary = data.groupby("treatment_modality").agg(
        early_rate=("early_rate", "median"),
        late_rate=("late_rate", "median"),
        n=("early_rate", "count"),
    ).reset_index()
    mod_summary = mod_summary[mod_summary["n"] >= MIN_GROUP_SIZE]
    mod_summary = mod_summary.sort_values("early_rate", ascending=True)

    y_pos = np.arange(len(mod_summary))
    width = 0.35
    colors = sns.color_palette("colorblind", 2)

    axes[0].barh(y_pos - width / 2, mod_summary["early_rate"], width,
                  color=colors[0], label="Early (0-3 mo)")
    axes[0].barh(y_pos + width / 2, mod_summary["late_rate"], width,
                  color=colors[1], label="Late (3-12 mo)")
    axes[0].set_yticks(y_pos)
    axes[0].set_yticklabels([f"{m} (N={n})" for m, n in
                              zip(mod_summary["treatment_modality"], mod_summary["n"])])
    axes[0].set_xlabel("Median Days per Month")
    axes[0].set_title("TT Accumulation Rate by Treatment Modality")
    axes[0].legend(loc="lower right")

    # Right panel: trajectory curves by modality
    tp_months = [0, 1, 3, 6, 9, 12]
    tp_cols = ["screening", "1_month", "3_months", "6_months", "9_months", "12_months"]
    palette = sns.color_palette("colorblind", len(mod_summary))

    for idx, mod in enumerate(mod_summary["treatment_modality"]):
        subset = data[data["treatment_modality"] == mod]
        medians = [subset[col].median() for col in tp_cols]
        axes[1].plot(tp_months, medians, "o-", label=mod, linewidth=2, markersize=5,
                     color=palette[idx])

    axes[1].set_xlabel("Months")
    axes[1].set_ylabel("Cumulative Healthcare Contact Days (Median)")
    axes[1].set_title("TT Trajectory by Treatment Modality")
    axes[1].legend(loc="upper left", fontsize=8)
    axes[1].set_xlim(-0.5, 12.5)
    axes[1].set_ylim(bottom=0)

    fig.tight_layout()
    save_fig(fig, "fig10_front_loading.pdf")


def fig11_threshold_analysis(trials, arms):
    """Grouped bar chart showing % of arms exceeding TT thresholds."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    thresholds = [30, 60, 90]
    colors = sns.color_palette("colorblind", 3)

    # Use primary arms only
    primary_arms = arms[arms["pos_idx"] == 0]
    interv = primary_arms[primary_arms["intervention_type"] == "intervention"]["12_months"].dropna()
    ctrl = primary_arms[primary_arms["intervention_type"] == "control"]["12_months"].dropna()

    x = np.arange(len(thresholds))
    width = 0.35

    interv_pcts = [100 * (interv > t).mean() for t in thresholds]
    ctrl_pcts = [100 * (ctrl > t).mean() for t in thresholds]

    bars1 = axes[0].bar(x - width / 2, interv_pcts, width, label="Intervention", color=colors[0])
    bars2 = axes[0].bar(x + width / 2, ctrl_pcts, width, label="Control", color=colors[1])
    axes[0].set_xticks(x)
    axes[0].set_xticklabels([f">{t} days" for t in thresholds])
    axes[0].set_ylabel("% of Arms Exceeding Threshold")
    axes[0].set_title("Extreme TT: Primary Arm-Level Thresholds")
    axes[0].legend()

    # Annotate percentages
    for i, (iv, cv) in enumerate(zip(interv_pcts, ctrl_pcts)):
        axes[0].annotate(f"{iv:.1f}%", xy=(i - width / 2, iv + 0.5),
                          ha="center", fontsize=9)
        axes[0].annotate(f"{cv:.1f}%", xy=(i + width / 2, cv + 0.5),
                          ha="center", fontsize=9)

    # Right panel: delta thresholds
    delta = trials["delta_12_months"].dropna()
    delta_pcts_pos = [100 * (delta > t).mean() for t in thresholds]
    delta_pcts_neg = [100 * (delta < -t).mean() for t in thresholds]

    bars3 = axes[1].bar(x - width / 2, delta_pcts_pos, width,
                         label="Delta > threshold (interv. more toxic)", color=colors[0])
    bars4 = axes[1].bar(x + width / 2, delta_pcts_neg, width,
                         label="Delta < -threshold (ctrl. more toxic)", color=colors[2])
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([f"|Delta| > {t}" for t in thresholds])
    axes[1].set_ylabel("% of Trials")
    axes[1].set_title("Extreme Incremental TT (Delta)")
    axes[1].legend(fontsize=8)

    for i, (dp, dn) in enumerate(zip(delta_pcts_pos, delta_pcts_neg)):
        axes[1].annotate(f"{dp:.1f}%", xy=(i - width / 2, dp + 0.2),
                          ha="center", fontsize=9)
        axes[1].annotate(f"{dn:.1f}%", xy=(i + width / 2, dn + 0.2),
                          ha="center", fontsize=9)

    fig.tight_layout()
    save_fig(fig, "fig11_threshold_analysis.pdf")


def fig12_iqr_comparison():
    """Forest-style plot showing median + IQR by subgroup."""
    iqr_df = pd.read_csv(os.path.join(TABLES_DIR, "table_iqr_comparison.csv"))

    fig, ax = plt.subplots(figsize=(10, max(8, len(iqr_df) * 0.45)))

    y_positions = list(range(len(iqr_df)))
    y_positions.reverse()

    colors_map = {"Sponsor": sns.color_palette("colorblind")[0],
                  "Site": sns.color_palette("colorblind")[1],
                  "Modality": sns.color_palette("colorblind")[2]}

    for i, (_, row) in enumerate(iqr_df.iterrows()):
        y = y_positions[i]
        category = row["Group"].split(":")[0]
        color = colors_map.get(category, "gray")

        ax.plot(row["Median"], y, "D", color=color, markersize=8, zorder=5)
        ax.plot([row["Q1"], row["Q3"]], [y, y], "-", color=color, linewidth=3, zorder=4)
        ax.annotate(f"IQR={row['IQR']:.0f}", xy=(row["Q3"] + 1.5, y),
                     fontsize=8, va="center")

    ax.set_yticks(y_positions)
    ax.set_yticklabels([f"{row['Group']} (N={int(row['N'])})"
                         for _, row in iqr_df.iterrows()], fontsize=9)
    ax.set_xlabel("Healthcare Contact Days at 12 Months")
    ax.set_title("Variability in Time Toxicity by Subgroup\n(Median with IQR)")

    # Overall median reference line
    overall_median = 19.0  # from descriptive stats
    ax.axvline(x=overall_median, color="red", linestyle="--", alpha=0.5, label=f"Overall median ({overall_median:.0f}d)")
    ax.legend(loc="lower right")
    ax.set_xlim(left=0)

    fig.tight_layout()
    save_fig(fig, "fig12_iqr_comparison.pdf")


def fig13_adjusted_temporal_trend(trials):
    """Adjusted vs raw temporal trend: scatter + two regression lines."""
    from statsmodels.formula.api import ols as ols_formula

    fig, ax = plt.subplots(figsize=(10, 6))

    data = trials.dropna(subset=["intervention_12_months", "start_year",
                                  "disease_site", "treatment_modality"]).copy()
    # Filter to valid groups
    site_cts = data["disease_site"].value_counts()
    valid_sites = site_cts[site_cts >= MIN_GROUP_SIZE].index
    data = data[data["disease_site"].isin(valid_sites)]
    mod_cts = data["treatment_modality"].value_counts()
    valid_mods = mod_cts[mod_cts >= MIN_GROUP_SIZE].index
    data = data[data["treatment_modality"].isin(valid_mods)]

    most_common_site = data["disease_site"].value_counts().idxmax()

    # Scatter with jitter
    jitter_x = data["start_year"] + np.random.normal(0, 0.15, len(data))
    ax.scatter(jitter_x, data["intervention_12_months"], alpha=0.12, s=12,
              c="gray", edgecolors="none", zorder=1)

    # Yearly medians
    yearly = data.groupby("start_year")["intervention_12_months"].agg(["median", "count"])
    ax.plot(yearly.index, yearly["median"], "ko", markersize=5, zorder=6,
            label="Yearly Median", alpha=0.7)

    x_pred = np.linspace(data["start_year"].min(), data["start_year"].max(), 100)

    # Raw OLS
    X_raw = sm.add_constant(data["start_year"])
    model_raw = sm.OLS(data["intervention_12_months"], X_raw).fit()
    X_raw_pred = sm.add_constant(x_pred)
    y_raw_pred = model_raw.predict(X_raw_pred)
    pred_raw = model_raw.get_prediction(X_raw_pred)
    ci_raw = pred_raw.conf_int(alpha=0.05)

    raw_slope = model_raw.params.iloc[1]
    raw_p = model_raw.pvalues.iloc[1]

    ax.plot(x_pred, y_raw_pred, color=sns.color_palette("colorblind")[0],
            linestyle="--", linewidth=2,
            label=f"Raw: {raw_slope:+.2f} d/yr (p={raw_p:.3f})", zorder=4)
    ax.fill_between(x_pred, ci_raw[:, 0], ci_raw[:, 1], alpha=0.10,
                    color=sns.color_palette("colorblind")[0])

    # Adjusted OLS — partial effect of start_year
    adj_formula = (
        f'intervention_12_months ~ start_year + '
        f'C(disease_site, Treatment("{most_common_site}")) + '
        f'C(treatment_modality, Treatment("Chemotherapy"))'
    )
    model_adj = ols_formula(adj_formula, data=data).fit()
    adj_slope = model_adj.params["start_year"]
    adj_p = model_adj.pvalues["start_year"]
    adj_intercept = model_adj.params["Intercept"]

    # Plot the partial effect line (other covariates at reference level)
    y_adj_pred = adj_intercept + adj_slope * x_pred

    # For CI: create prediction data at reference categories
    pred_data = pd.DataFrame({"start_year": x_pred})
    pred_data["disease_site"] = most_common_site
    pred_data["treatment_modality"] = "Chemotherapy"
    y_adj_full = model_adj.predict(pred_data)
    pred_adj = model_adj.get_prediction(pred_data)
    ci_adj = pred_adj.conf_int(alpha=0.05)

    ax.plot(x_pred, y_adj_full, color=sns.color_palette("colorblind")[3],
            linestyle="-", linewidth=2.5,
            label=f"Adjusted: {adj_slope:+.2f} d/yr (p={adj_p:.3f})", zorder=5)
    ax.fill_between(x_pred, ci_adj[:, 0], ci_adj[:, 1], alpha=0.10,
                    color=sns.color_palette("colorblind")[3])

    # Annotation
    delta = adj_slope - raw_slope
    ax.annotate(
        f"Adjustment {'attenuates' if delta < 0 else 'strengthens'} by {abs(delta):.2f} d/yr",
        xy=(0.03, 0.95), xycoords="axes fraction",
        fontsize=10, fontstyle="italic", color="gray",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
    )

    ax.set_xlabel("Trial Start Year")
    ax.set_ylabel("Healthcare Contact Days at 12 Months")
    ax.set_title("Temporal Trend: Raw vs Adjusted for Disease Site & Treatment Modality")
    ax.legend(loc="upper left", fontsize=9)
    ax.set_xlim(data["start_year"].min() - 0.5, data["start_year"].max() + 0.5)

    fig.tight_layout()
    save_fig(fig, "fig13_adjusted_temporal_trend.pdf")


def fig14_within_site_temporal(trials):
    """Small multiples: temporal trend per disease site."""
    data = trials.dropna(subset=["intervention_12_months", "start_year", "disease_site"]).copy()

    # Get qualifying sites
    site_cts = data["disease_site"].value_counts()
    valid_sites = sorted(site_cts[site_cts >= MIN_GROUP_SIZE].index)
    n_sites = len(valid_sites)

    ncols = 3
    nrows = (n_sites + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(16, 4.5 * nrows), sharex=True)
    axes = axes.flatten()

    # Consistent y-axis
    y_max = data["intervention_12_months"].quantile(0.98)

    colors = sns.color_palette("colorblind", n_sites)

    for i, site in enumerate(valid_sites):
        ax = axes[i]
        subset = data[data["disease_site"] == site]
        n = len(subset)

        # Scatter
        jitter_x = subset["start_year"] + np.random.normal(0, 0.2, n)
        ax.scatter(jitter_x, subset["intervention_12_months"],
                  alpha=0.25, s=12, c=[colors[i]], edgecolors="none")

        # OLS regression
        X = sm.add_constant(subset["start_year"])
        model = sm.OLS(subset["intervention_12_months"], X).fit()
        slope = model.params.iloc[1]
        p_val = model.pvalues.iloc[1]

        x_pred = np.linspace(subset["start_year"].min(), subset["start_year"].max(), 50)
        X_pred = sm.add_constant(x_pred)
        y_pred = model.predict(X_pred)
        pred = model.get_prediction(X_pred)
        ci = pred.conf_int(alpha=0.05)

        line_color = "red" if p_val < 0.05 else colors[i]
        line_style = "-" if p_val < 0.05 else "--"
        ax.plot(x_pred, y_pred, color=line_color, linestyle=line_style, linewidth=2)
        ax.fill_between(x_pred, ci[:, 0], ci[:, 1], alpha=0.12, color=line_color)

        # Title with stats
        sig = " **" if p_val < 0.05 else ""
        ax.set_title(f"{site} (N={n})\nSlope: {slope:+.2f} d/yr, p={p_val:.3f}{sig}",
                     fontsize=10, fontweight="bold" if p_val < 0.05 else "normal")
        ax.set_ylim(-2, y_max)
        ax.set_xlim(data["start_year"].min() - 0.5, data["start_year"].max() + 0.5)

        if i % ncols == 0:
            ax.set_ylabel("TT (days)")
        if i >= (nrows - 1) * ncols:
            ax.set_xlabel("Trial Start Year")

    # Hide empty subplots
    for j in range(n_sites, len(axes)):
        axes[j].set_visible(False)

    fig.suptitle("Within-Disease-Site Temporal Trends in Time Toxicity",
                 fontsize=14, fontweight="bold", y=1.01)
    fig.tight_layout()
    save_fig(fig, "fig14_within_site_temporal.pdf")


def fig15_heatmap_disease_timepoint(arms):
    """Heatmap: disease site (rows) x timepoint (columns), two panels for intervention/control."""
    tp_cols = ["1_month", "3_months", "6_months", "9_months", "12_months"]
    tp_labels = ["1 mo", "3 mo", "6 mo", "9 mo", "12 mo"]

    # Primary arms only
    data = arms[(arms["pos_idx"] == 0) & arms["disease_site"].notna()].copy()

    arm_types = [("intervention", "Intervention"), ("control", "Control")]

    # Sort sites by 12-month intervention median TT descending
    interv_data = data[data["intervention_type"] == "intervention"]
    site_cts = interv_data["disease_site"].value_counts()
    valid_sites = site_cts[site_cts >= MIN_GROUP_SIZE].index
    site_medians_12 = interv_data[interv_data["disease_site"].isin(valid_sites)].groupby("disease_site")["12_months"].median()
    sorted_sites = site_medians_12.sort_values(ascending=False).index.tolist()

    # Build matrices for both panels and find global vmin/vmax
    matrices = {}
    n_labels = {}
    for arm_type, arm_label in arm_types:
        subset = data[data["intervention_type"] == arm_type]
        matrix = []
        labels = []
        for site in sorted_sites:
            site_data = subset[subset["disease_site"] == site]
            row = [site_data[col].median() for col in tp_cols]
            matrix.append(row)
            labels.append(f"{site} (N={len(site_data)})")
        matrices[arm_type] = np.array(matrix, dtype=float)
        n_labels[arm_type] = labels

    all_vals = np.concatenate([m.ravel() for m in matrices.values()])
    all_vals = all_vals[~np.isnan(all_vals)]
    vmin, vmax = all_vals.min(), all_vals.max()

    fig, axes = plt.subplots(1, 2, figsize=(14, 7))
    cmap = "YlOrRd"

    for panel_idx, (arm_type, arm_label) in enumerate(arm_types):
        ax = axes[panel_idx]
        matrix = matrices[arm_type]

        im = ax.imshow(matrix, cmap=cmap, aspect="auto", vmin=vmin, vmax=vmax)

        # Annotate cells with median values
        for i in range(matrix.shape[0]):
            for j in range(matrix.shape[1]):
                val = matrix[i, j]
                if not np.isnan(val):
                    text_color = "white" if val > (vmin + vmax) / 2 else "black"
                    ax.text(j, i, f"{val:.0f}", ha="center", va="center",
                            fontsize=9, fontweight="bold", color=text_color)

        ax.set_xticks(range(len(tp_labels)))
        ax.set_xticklabels(tp_labels, fontsize=10)
        ax.set_yticks(range(len(sorted_sites)))
        if panel_idx == 0:
            ax.set_yticklabels(n_labels[arm_type], fontsize=9)
        else:
            ax.set_yticklabels(n_labels[arm_type], fontsize=9)
        ax.set_title(f"{arm_label} Arms", fontsize=12, fontweight="bold")

    cbar = fig.colorbar(im, ax=axes, shrink=0.6, pad=0.02)
    cbar.set_label("Median Healthcare Contact Days", fontsize=10)

    fig.suptitle("Time Toxicity Landscape: Disease Site × Timepoint",
                 fontsize=14, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 0.92, 0.95])
    save_fig(fig, "fig15_heatmap_disease_timepoint.pdf")


def fig16_slope_chart_accumulation(arms):
    """Slope chart: accumulation rate (days/month) across intervals, by disease site and treatment modality."""
    # Primary intervention arms only
    data = arms[(arms["pos_idx"] == 0) &
                (arms["intervention_type"] == "intervention") &
                arms["disease_site"].notna() &
                arms["treatment_modality"].notna()].copy()
    data = data.dropna(subset=["screening", "1_month", "3_months", "6_months", "9_months", "12_months"])
    data = data[data["12_months"] > 0]

    intervals = [
        ("Scr\u21921mo", "1_month", "screening", 1),
        ("1\u21923mo", "3_months", "1_month", 2),
        ("3\u21926mo", "6_months", "3_months", 3),
        ("6\u21929mo", "9_months", "6_months", 3),
        ("9\u219212mo", "12_months", "9_months", 3),
    ]

    interval_labels = [iv[0] for iv in intervals]

    # Compute per-arm rates
    for label, end_col, start_col, months in intervals:
        col_name = f"rate_{end_col}"
        data[col_name] = (data[end_col] - data[start_col]) / months

    rate_cols = [f"rate_{iv[1]}" for iv in intervals]

    fig, axes = plt.subplots(1, 2, figsize=(16, 7), sharey=True)

    # Left panel: by disease site
    ax = axes[0]
    site_cts = data["disease_site"].value_counts()
    valid_sites = site_cts[site_cts >= MIN_GROUP_SIZE].index
    palette = sns.color_palette("colorblind", len(valid_sites))

    for idx, site in enumerate(sorted(valid_sites)):
        site_data = data[data["disease_site"] == site]
        median_rates = [site_data[col].median() for col in rate_cols]
        ax.plot(range(len(interval_labels)), median_rates, "o-",
                label=f"{site} (N={len(site_data)})",
                linewidth=2, markersize=6, color=palette[idx])

    ax.set_xticks(range(len(interval_labels)))
    ax.set_xticklabels(interval_labels, fontsize=10)
    ax.set_ylabel("Median Accumulation Rate (days/month)", fontsize=11)
    ax.set_title("By Disease Site", fontsize=12, fontweight="bold")
    ax.legend(fontsize=8, loc="upper right")
    ax.set_ylim(bottom=0)
    ax.grid(True, alpha=0.2)

    # Right panel: by treatment modality
    ax = axes[1]
    mod_cts = data["treatment_modality"].value_counts()
    valid_mods = mod_cts[mod_cts >= MIN_GROUP_SIZE].index
    palette2 = sns.color_palette("Set2", len(valid_mods))

    for idx, mod in enumerate(sorted(valid_mods)):
        mod_data = data[data["treatment_modality"] == mod]
        median_rates = [mod_data[col].median() for col in rate_cols]
        ax.plot(range(len(interval_labels)), median_rates, "s-",
                label=f"{mod} (N={len(mod_data)})",
                linewidth=2, markersize=6, color=palette2[idx])

    ax.set_xticks(range(len(interval_labels)))
    ax.set_xticklabels(interval_labels, fontsize=10)
    ax.set_title("By Treatment Modality", fontsize=12, fontweight="bold")
    ax.legend(fontsize=8, loc="upper right")
    ax.set_ylim(bottom=0)
    ax.grid(True, alpha=0.2)

    fig.suptitle("TT Accumulation Rate Across Intervals (Intervention Arms)",
                 fontsize=14, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    save_fig(fig, "fig16_slope_chart_accumulation.pdf")


def main():
    print("=" * 60)
    print("STEP 7: Generating Publication-Quality Figures")
    print("=" * 60)

    # Load data
    trials = pd.read_csv(os.path.join(DATA_DIR, "enriched_trials.csv"))
    arms = pd.read_csv(os.path.join(DATA_DIR, "enriched_arms.csv"))

    print("\n--- Figure 1: TT Distribution ---")
    fig1_tt_distribution(arms)

    print("--- Figure 2: Delta TT Distribution ---")
    fig2_delta_tt(trials)

    print("--- Figure 3: Sponsorship Comparison ---")
    fig3_sponsorship(trials)

    print("--- Figure 4: Disease Site Comparison ---")
    fig4_disease_site(trials)

    print("--- Figure 5: Treatment Type Comparison ---")
    fig5_treatment_type(trials)

    print("--- Figure 6: Temporal Trend ---")
    fig6_temporal_trend(trials)

    print("--- Figure 7: Component Breakdown ---")
    fig7_component_breakdown(TABLES_DIR)

    print("--- Figure 8: Forest Plot ---")
    fig8_forest_plot()

    print("--- Figure 9: Industry Temporal Trend ---")
    fig9_industry_temporal_trend(trials)

    print("--- Figure 10: Front-Loading Analysis ---")
    fig10_front_loading(arms)

    print("--- Figure 11: Threshold Analysis ---")
    fig11_threshold_analysis(trials, arms)

    print("--- Figure 12: IQR Comparison ---")
    fig12_iqr_comparison()

    print("--- Figure 13: Adjusted Temporal Trend ---")
    fig13_adjusted_temporal_trend(trials)

    print("--- Figure 14: Within-Site Temporal Trends ---")
    fig14_within_site_temporal(trials)

    print("--- Figure 15: Heatmap Disease Site × Timepoint ---")
    fig15_heatmap_disease_timepoint(arms)

    print("--- Figure 16: Slope Chart Accumulation Rate ---")
    fig16_slope_chart_accumulation(arms)

    print("\n" + "=" * 60)
    print("STEP 7 COMPLETE — All 16 figures generated")
    print("=" * 60)


if __name__ == "__main__":
    main()
