#!/usr/bin/env python3
"""
Step 1: Build consensus dataset from 3 vanilla pipeline runs.

Uses position-based matching within (filename, intervention_type) groups
to handle arm name instability across runs.
"""

import os
import sys
import json
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    CSV_RUNS, JSON_RUNS, PROTOCOL_METADATA,
    DATA_DIR, TIMEPOINTS, CATEGORIES
)


def load_csv_runs():
    """Load all 3 CSV runs and tag with run_id."""
    frames = []
    for i, path in enumerate(CSV_RUNS):
        df = pd.read_csv(path)
        df["run_id"] = f"run{i+1}"
        frames.append(df)
        print(f"  Run {i+1}: {len(df)} rows from {os.path.basename(path)}")
    return pd.concat(frames, ignore_index=True)


def normalize_intervention_type(df):
    """Normalize intervention_type: placebo→control, active_comparator→intervention."""
    df["intervention_type"] = df["intervention_type"].str.lower().str.strip()
    df.loc[df["intervention_type"] == "placebo", "intervention_type"] = "control"
    df.loc[df["intervention_type"] == "active_comparator", "intervention_type"] = "intervention"
    return df


def assign_position_index(df):
    """Assign positional index within (filename, run_id, intervention_type) sorted by 12_months."""
    df = df.sort_values(["filename", "run_id", "intervention_type", "12_months"])
    df["pos_idx"] = df.groupby(["filename", "run_id", "intervention_type"]).cumcount()
    return df


def build_arm_consensus(df):
    """Build consensus arm-level data by taking median across runs."""
    numeric_cols = TIMEPOINTS + ["cycle_length"]

    agg_dict = {col: "median" for col in numeric_cols}
    agg_dict["run_id"] = "count"  # n_runs
    agg_dict["arm_name"] = "first"  # representative name

    consensus = (
        df.groupby(["filename", "intervention_type", "pos_idx"])
        .agg(agg_dict)
        .reset_index()
    )
    consensus.rename(columns={"run_id": "n_runs"}, inplace=True)

    # Derived metrics
    consensus["intensity_score"] = consensus["12_months"] / 12.0

    print(f"\n  Consensus arms: {len(consensus)}")
    print(f"  Unique trials: {consensus['filename'].nunique()}")
    print(f"  Arms with 3 runs: {(consensus['n_runs'] == 3).sum()}")
    print(f"  Arms with 2 runs: {(consensus['n_runs'] == 2).sum()}")
    print(f"  Arms with 1 run: {(consensus['n_runs'] == 1).sum()}")

    return consensus


def build_trial_level(consensus, metadata):
    """Build trial-level dataset with delta TT."""
    # Get primary intervention arm (pos_idx=0)
    intervention = consensus[
        (consensus["intervention_type"] == "intervention") & (consensus["pos_idx"] == 0)
    ][["filename"] + TIMEPOINTS + ["intensity_score", "cycle_length"]].copy()
    intervention.columns = ["filename"] + [f"intervention_{c}" for c in TIMEPOINTS] + [
        "intervention_intensity", "intervention_cycle_length"
    ]

    # Get primary control arm (pos_idx=0)
    control = consensus[
        (consensus["intervention_type"] == "control") & (consensus["pos_idx"] == 0)
    ][["filename"] + TIMEPOINTS + ["intensity_score", "cycle_length"]].copy()
    control.columns = ["filename"] + [f"control_{c}" for c in TIMEPOINTS] + [
        "control_intensity", "control_cycle_length"
    ]

    # Merge
    trials = intervention.merge(control, on="filename", how="outer")

    # Delta TT at each timepoint
    for tp in TIMEPOINTS:
        trials[f"delta_{tp}"] = trials[f"intervention_{tp}"] - trials[f"control_{tp}"]

    # Delta intensity
    trials["delta_intensity"] = trials["intervention_intensity"] - trials["control_intensity"]

    # Join publication year from metadata
    meta = pd.read_csv(metadata)
    trials = trials.merge(
        meta[["filename", "pmid", "publication_year"]],
        on="filename",
        how="left"
    )

    n_both = trials.dropna(subset=["intervention_12_months", "control_12_months"]).shape[0]
    n_interv_only = trials[trials["control_12_months"].isna()].shape[0]
    n_control_only = trials[trials["intervention_12_months"].isna()].shape[0]

    print(f"\n  Trial-level dataset: {len(trials)} trials")
    print(f"  Trials with both arms: {n_both}")
    print(f"  Trials with intervention only: {n_interv_only}")
    print(f"  Trials with control only: {n_control_only}")
    print(f"  Median delta TT (12mo): {trials['delta_12_months'].median():.1f} days")

    return trials


def load_json_runs():
    """Load JSON runs 1-2 for category breakdown."""
    all_arms = []
    for i, path in enumerate(JSON_RUNS):
        with open(path, "r") as f:
            data = json.load(f)

        run_id = f"run{i+1}"
        for entry in data:
            if entry.get("error"):
                continue
            filename = entry["filename"]
            for arm in entry.get("arms", []):
                arm_type = arm.get("intervention_type", "").lower().strip()
                if arm_type == "placebo":
                    arm_type = "control"
                elif arm_type == "active_comparator":
                    arm_type = "intervention"

                hcd = arm.get("healthcare_contact_days", {})
                cb = arm.get("category_breakdown", {})

                row = {
                    "filename": filename,
                    "run_id": run_id,
                    "intervention_type": arm_type,
                    "arm_name": arm.get("arm_name", ""),
                }
                # Total healthcare contact days
                for tp in TIMEPOINTS:
                    row[f"total_{tp}"] = hcd.get(tp, 0)
                # Category breakdown
                for cat in CATEGORIES:
                    cat_data = cb.get(cat, {})
                    for tp in TIMEPOINTS:
                        row[f"{cat}_{tp}"] = cat_data.get(tp, 0)

                all_arms.append(row)

        print(f"  JSON Run {i+1}: {len([e for e in data if not e.get('error')])} protocols")

    return pd.DataFrame(all_arms)


def build_category_consensus(json_df):
    """Build consensus category breakdown from JSON runs 1-2."""
    # Assign position index (same strategy as CSV)
    json_df = json_df.sort_values(["filename", "run_id", "intervention_type", "total_12_months"])
    json_df["pos_idx"] = json_df.groupby(["filename", "run_id", "intervention_type"]).cumcount()

    # Columns to aggregate
    cat_cols = []
    for cat in CATEGORIES:
        for tp in TIMEPOINTS:
            cat_cols.append(f"{cat}_{tp}")
    total_cols = [f"total_{tp}" for tp in TIMEPOINTS]
    all_numeric = cat_cols + total_cols

    agg_dict = {col: "median" for col in all_numeric}
    agg_dict["run_id"] = "count"

    consensus = (
        json_df.groupby(["filename", "intervention_type", "pos_idx"])
        .agg(agg_dict)
        .reset_index()
    )
    consensus.rename(columns={"run_id": "n_runs"}, inplace=True)

    # Validation: check sum of categories ≈ total
    discrepancies = 0
    for _, row in consensus.iterrows():
        cat_sum = sum(row[f"{cat}_12_months"] for cat in CATEGORIES)
        total = row["total_12_months"]
        if total > 0 and abs(cat_sum - total) > 1:
            discrepancies += 1

    pct_valid = (1 - discrepancies / len(consensus)) * 100
    print(f"\n  Category consensus arms: {len(consensus)}")
    print(f"  Category sum validation: {pct_valid:.1f}% arms within 1 day of total")
    if discrepancies > 0:
        print(f"  WARNING: {discrepancies} arms have category sum discrepancy >1 day")

    return consensus


def main():
    print("=" * 60)
    print("STEP 1: Building Consensus Dataset")
    print("=" * 60)

    # --- CSV Consensus ---
    print("\n--- Loading CSV Runs ---")
    all_runs = load_csv_runs()

    print("\n--- Normalizing intervention types ---")
    all_runs = normalize_intervention_type(all_runs)

    # Drop error rows and null 12_months
    before = len(all_runs)
    all_runs = all_runs[all_runs["error"].isna() | (all_runs["error"] == "")]
    all_runs["12_months"] = pd.to_numeric(all_runs["12_months"], errors="coerce")
    all_runs = all_runs.dropna(subset=["12_months"])
    print(f"  Dropped {before - len(all_runs)} rows with errors/null values")

    # Convert all timepoint columns to numeric
    for tp in TIMEPOINTS:
        all_runs[tp] = pd.to_numeric(all_runs[tp], errors="coerce")
    all_runs["cycle_length"] = pd.to_numeric(all_runs["cycle_length"], errors="coerce")

    print("\n--- Assigning position indices ---")
    all_runs = assign_position_index(all_runs)

    print("\n--- Building arm-level consensus ---")
    consensus_arms = build_arm_consensus(all_runs)

    print("\n--- Building trial-level dataset ---")
    metadata = pd.read_csv(PROTOCOL_METADATA)
    consensus_trials = build_trial_level(consensus_arms, PROTOCOL_METADATA)

    # --- JSON Category Consensus ---
    print("\n--- Loading JSON Runs (1-2) for category breakdown ---")
    json_df = load_json_runs()

    print("\n--- Building category breakdown consensus ---")
    category_consensus = build_category_consensus(json_df)

    # --- Save outputs ---
    print("\n--- Saving outputs ---")
    consensus_arms.to_csv(os.path.join(DATA_DIR, "consensus_arms.csv"), index=False)
    consensus_trials.to_csv(os.path.join(DATA_DIR, "consensus_trials.csv"), index=False)
    category_consensus.to_csv(os.path.join(DATA_DIR, "category_breakdown_consensus.csv"), index=False)

    print(f"\n  Saved: data/consensus_arms.csv ({len(consensus_arms)} rows)")
    print(f"  Saved: data/consensus_trials.csv ({len(consensus_trials)} rows)")
    print(f"  Saved: data/category_breakdown_consensus.csv ({len(category_consensus)} rows)")

    # --- Summary statistics ---
    print("\n--- Quick Summary ---")
    print(f"  Median 12-month TT (intervention): {consensus_arms[consensus_arms['intervention_type']=='intervention']['12_months'].median():.1f} days")
    print(f"  Median 12-month TT (control): {consensus_arms[consensus_arms['intervention_type']=='control']['12_months'].median():.1f} days")
    print(f"  Median intensity score (intervention): {consensus_arms[consensus_arms['intervention_type']=='intervention']['intensity_score'].median():.2f} days/month")

    print("\n" + "=" * 60)
    print("STEP 1 COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
