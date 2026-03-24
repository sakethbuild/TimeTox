#!/usr/bin/env python3
"""
Step 5: Component Analysis — Understanding the composition of Time Toxicity.

Analyzes category breakdown (core_treatment, imaging_diagnostics, labs, clinic_visits)
to identify drivers of burden and opportunities for reduction.
"""

import os
import sys
import warnings
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import DATA_DIR, TABLES_DIR, FIGURES_DIR, CATEGORIES, TIMEPOINTS, MIN_GROUP_SIZE

warnings.filterwarnings("ignore", category=FutureWarning)


def main():
    print("=" * 60)
    print("STEP 5: Component Analysis")
    print("=" * 60)

    # Load category breakdown consensus
    cat_df = pd.read_csv(os.path.join(DATA_DIR, "category_breakdown_consensus.csv"))
    enriched_arms = pd.read_csv(os.path.join(DATA_DIR, "enriched_arms.csv"))

    print(f"  Category breakdown arms: {len(cat_df)}")
    print(f"  Enriched arms: {len(enriched_arms)}")

    # Merge category data with enriched metadata
    # Match on (filename, intervention_type, pos_idx)
    merged = cat_df.merge(
        enriched_arms[["filename", "intervention_type", "pos_idx",
                        "sponsor_binary", "disease_site", "treatment_modality", "start_year"]],
        on=["filename", "intervention_type", "pos_idx"],
        how="left"
    )
    print(f"  Merged dataset: {len(merged)} arms")
    print(f"  With metadata: {merged['disease_site'].notna().sum()}")

    # ==========================================
    # COMPUTE PERCENTAGES AT 12 MONTHS
    # ==========================================
    print("\n" + "=" * 50)
    print("CATEGORY COMPOSITION AT 12 MONTHS")
    print("=" * 50)

    for cat in CATEGORIES:
        merged[f"pct_{cat}"] = merged[f"{cat}_12_months"] / merged["total_12_months"] * 100
    merged["pct_research"] = merged["pct_imaging_diagnostics"] + merged["pct_labs"]

    # Handle division by zero (total=0)
    for cat in CATEGORIES:
        merged.loc[merged["total_12_months"] == 0, f"pct_{cat}"] = 0
    merged.loc[merged["total_12_months"] == 0, "pct_research"] = 0

    # ==========================================
    # OVERALL BREAKDOWN
    # ==========================================
    print("\n--- Overall (All Arms) ---")
    all_arms = merged[merged["total_12_months"] > 0]
    print(f"  N = {len(all_arms)} arms with TT > 0")
    print()
    print(f"  {'Category':<25} {'Mean %':<12} {'Median %':<12} {'Mean Days':<12}")
    print(f"  {'-'*60}")
    for cat in CATEGORIES:
        mean_pct = all_arms[f"pct_{cat}"].mean()
        med_pct = all_arms[f"pct_{cat}"].median()
        mean_days = all_arms[f"{cat}_12_months"].mean()
        label = cat.replace("_", " ").title()
        print(f"  {label:<25} {mean_pct:>8.1f}%    {med_pct:>8.1f}%    {mean_days:>8.1f}")

    mean_research = all_arms["pct_research"].mean()
    med_research = all_arms["pct_research"].median()
    print(f"  {'─'*60}")
    print(f"  {'Research-Specific*':<25} {mean_research:>8.1f}%    {med_research:>8.1f}%")
    print(f"\n  *Research-Specific = Imaging/Diagnostics + Labs")

    # ==========================================
    # BREAKDOWN BY INTERVENTION TYPE
    # ==========================================
    print("\n--- By Arm Type ---")
    for arm_type in ["intervention", "control"]:
        subset = all_arms[all_arms["intervention_type"] == arm_type]
        print(f"\n  {arm_type.upper()} arms (N={len(subset)}):")
        for cat in CATEGORIES:
            label = cat.replace("_", " ").title()
            mean_pct = subset[f"pct_{cat}"].mean()
            mean_days = subset[f"{cat}_12_months"].mean()
            print(f"    {label:<25} {mean_pct:>6.1f}%  ({mean_days:.1f} days)")
        print(f"    {'Research-Specific':<25} {subset['pct_research'].mean():>6.1f}%")

    # ==========================================
    # BREAKDOWN BY DISEASE SITE
    # ==========================================
    print("\n" + "=" * 50)
    print("CATEGORY COMPOSITION BY DISEASE SITE")
    print("=" * 50)

    interv = all_arms[all_arms["intervention_type"] == "intervention"]
    site_summary = []

    for site, grp in interv.groupby("disease_site"):
        if len(grp) < MIN_GROUP_SIZE:
            continue
        row = {"Disease Site": site, "N": len(grp)}
        row["Median TT"] = grp["total_12_months"].median()
        for cat in CATEGORIES:
            row[f"Mean % {cat}"] = grp[f"pct_{cat}"].mean()
            row[f"Mean Days {cat}"] = grp[f"{cat}_12_months"].mean()
        row["Mean % Research"] = grp["pct_research"].mean()
        site_summary.append(row)

    site_df = pd.DataFrame(site_summary).sort_values("Median TT", ascending=False)

    print(f"\n  {'Site':<12} {'N':>4} {'Med TT':>8} {'Treatment':>10} {'Imaging':>10} {'Labs':>10} {'Clinic':>10} {'Research':>10}")
    print(f"  {'─'*80}")
    for _, row in site_df.iterrows():
        print(f"  {row['Disease Site']:<12} {row['N']:>4} {row['Median TT']:>8.0f} "
              f"{row['Mean % core_treatment']:>9.1f}% {row['Mean % imaging_diagnostics']:>9.1f}% "
              f"{row['Mean % labs']:>9.1f}% {row['Mean % clinic_visits']:>9.1f}% "
              f"{row['Mean % Research']:>9.1f}%")

    # ==========================================
    # BREAKDOWN BY TREATMENT MODALITY
    # ==========================================
    print("\n" + "=" * 50)
    print("CATEGORY COMPOSITION BY TREATMENT MODALITY")
    print("=" * 50)

    mod_summary = []
    for mod, grp in interv.groupby("treatment_modality"):
        if len(grp) < MIN_GROUP_SIZE:
            continue
        row = {"Treatment Modality": mod, "N": len(grp)}
        row["Median TT"] = grp["total_12_months"].median()
        for cat in CATEGORIES:
            row[f"Mean % {cat}"] = grp[f"pct_{cat}"].mean()
            row[f"Mean Days {cat}"] = grp[f"{cat}_12_months"].mean()
        row["Mean % Research"] = grp["pct_research"].mean()
        mod_summary.append(row)

    mod_df = pd.DataFrame(mod_summary).sort_values("Median TT", ascending=False)

    print(f"\n  {'Modality':<18} {'N':>4} {'Med TT':>8} {'Treatment':>10} {'Imaging':>10} {'Labs':>10} {'Clinic':>10} {'Research':>10}")
    print(f"  {'─'*90}")
    for _, row in mod_df.iterrows():
        print(f"  {row['Treatment Modality']:<18} {row['N']:>4} {row['Median TT']:>8.0f} "
              f"{row['Mean % core_treatment']:>9.1f}% {row['Mean % imaging_diagnostics']:>9.1f}% "
              f"{row['Mean % labs']:>9.1f}% {row['Mean % clinic_visits']:>9.1f}% "
              f"{row['Mean % Research']:>9.1f}%")

    # ==========================================
    # ACTIONABLE INSIGHTS
    # ==========================================
    print("\n" + "=" * 50)
    print("ACTIONABLE INSIGHTS")
    print("=" * 50)

    overall_mean = {cat: all_arms[f"pct_{cat}"].mean() for cat in CATEGORIES}
    dominant = max(overall_mean, key=overall_mean.get)
    print(f"\n  Overall dominant driver: {dominant.replace('_', ' ').title()} ({overall_mean[dominant]:.1f}%)")
    print(f"  Research-specific burden (imaging + labs): {all_arms['pct_research'].mean():.1f}%")

    # Identify sites where research burden is highest
    if len(site_df) > 0:
        high_research = site_df.nlargest(3, "Mean % Research")
        print(f"\n  Top 3 disease sites by research-specific burden:")
        for _, row in high_research.iterrows():
            print(f"    {row['Disease Site']}: {row['Mean % Research']:.1f}% research-driven")

    # Identify modalities where labs dominate
    if len(mod_df) > 0:
        print(f"\n  Lab-heavy modalities (potential DCT candidates):")
        for _, row in mod_df.iterrows():
            if row["Mean % labs"] > 30:
                print(f"    {row['Treatment Modality']}: {row['Mean % labs']:.1f}% labs")

    # ==========================================
    # SAVE
    # ==========================================
    print("\n--- Saving component analysis results ---")
    component_all = pd.DataFrame([{
        "Scope": "Overall",
        "N": len(all_arms),
        **{f"Mean_pct_{cat}": all_arms[f"pct_{cat}"].mean() for cat in CATEGORIES},
        "Mean_pct_research": all_arms["pct_research"].mean(),
    }])

    site_df.to_csv(os.path.join(TABLES_DIR, "component_by_disease_site.csv"), index=False)
    mod_df.to_csv(os.path.join(TABLES_DIR, "component_by_modality.csv"), index=False)
    component_all.to_csv(os.path.join(TABLES_DIR, "component_summary.csv"), index=False)

    # Save the full merged dataset for figure generation
    merged.to_csv(os.path.join(DATA_DIR, "component_analysis_full.csv"), index=False)

    print(f"  Saved: tables/component_by_disease_site.csv")
    print(f"  Saved: tables/component_by_modality.csv")
    print(f"  Saved: tables/component_summary.csv")
    print(f"  Saved: data/component_analysis_full.csv")

    print("\n" + "=" * 60)
    print("STEP 5 COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
