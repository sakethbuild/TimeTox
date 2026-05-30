#!/usr/bin/env python3
"""
Phase 2, Step 1: Apply the reconciled gold-standard labels to the consensus arm
data, then re-derive pos_idx + trial-level + category-breakdown consensus files.

Mirrors 01_build_consensus.py's assign_position_index + build_trial_level logic,
but operates on the already-consensus'd arms (extraction is NOT re-run) and
SKIPS normalize_intervention_type (which contained the active_comparator bug).

Reads original consensus files (seeded into data/), writes corrected versions
to data/ in the verified folder. Excludes the 2 content-mismatch trials.
"""
import os, sys, warnings
warnings.filterwarnings("ignore")
import pandas as pd
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
TABLES = os.path.join(BASE, "tables")
ORIG_DATA = "/Users/sakethvinjamuri/Documents/TimeToxSV/Quantification of Time Toxicity/data"
TIMEPOINTS = ["screening", "1_month", "3_months", "6_months", "9_months", "12_months"]
CATEGORIES = ["core_treatment", "imaging_diagnostics", "labs", "clinic_visits"]


def main():
    rec = pd.read_csv(os.path.join(TABLES, "final_labels_reconciled.csv"))
    # correction map: (filename, original_label, pos_idx) -> (new_label, excluded)
    cmap, excl = {}, {}
    for _, r in rec.iterrows():
        key = (r["filename"], r["pipeline_label"], int(r["pos_idx"]))
        cmap[key] = r["final_label_reconciled"]
        excl[key] = bool(r["excluded"])
    excluded_trials = sorted(rec[rec["excluded"]]["filename"].unique())
    print(f"Correction map: {len(cmap)} arms. Excluded trials: {len(excluded_trials)}")

    # ---------- consensus_arms ----------
    arms = pd.read_csv(os.path.join(ORIG_DATA, "consensus_arms.csv"))
    def relabel(r):
        return cmap.get((r["filename"], r["intervention_type"], int(r["pos_idx"])), r["intervention_type"])
    def is_excl(r):
        return excl.get((r["filename"], r["intervention_type"], int(r["pos_idx"])), False)
    arms["intervention_type"] = arms.apply(relabel, axis=1)
    arms["_excl"] = arms.apply(is_excl, axis=1)
    n_before = len(arms)
    arms = arms[~arms["_excl"]].drop(columns="_excl")
    print(f"consensus_arms: {n_before} -> {len(arms)} arms after excluding content-mismatch")

    # re-assign pos_idx within (filename, NEW intervention_type) by 12_months
    arms = arms.sort_values(["filename", "intervention_type", "12_months"])
    arms["pos_idx"] = arms.groupby(["filename", "intervention_type"]).cumcount()
    arms["intensity_score"] = arms["12_months"] / 12.0
    arms.to_csv(os.path.join(DATA, "consensus_arms.csv"), index=False)
    print(f"  wrote corrected consensus_arms.csv ({len(arms)} rows, "
          f"{arms['filename'].nunique()} trials)")

    # ---------- trial-level (mirror build_trial_level) ----------
    iv = arms[(arms.intervention_type == "intervention") & (arms.pos_idx == 0)][
        ["filename"] + TIMEPOINTS + ["intensity_score", "cycle_length"]].copy()
    iv.columns = ["filename"] + [f"intervention_{c}" for c in TIMEPOINTS] + [
        "intervention_intensity", "intervention_cycle_length"]
    ct = arms[(arms.intervention_type == "control") & (arms.pos_idx == 0)][
        ["filename"] + TIMEPOINTS + ["intensity_score", "cycle_length"]].copy()
    ct.columns = ["filename"] + [f"control_{c}" for c in TIMEPOINTS] + [
        "control_intensity", "control_cycle_length"]
    trials = iv.merge(ct, on="filename", how="outer")
    for tp in TIMEPOINTS:
        trials[f"delta_{tp}"] = trials[f"intervention_{tp}"] - trials[f"control_{tp}"]
    trials["delta_intensity"] = trials["intervention_intensity"] - trials["control_intensity"]
    # join pmid + publication_year from original consensus_trials
    orig_tr = pd.read_csv(os.path.join(ORIG_DATA, "consensus_trials.csv"))
    trials = trials.merge(orig_tr[["filename", "pmid", "publication_year"]], on="filename", how="left")
    trials.to_csv(os.path.join(DATA, "consensus_trials.csv"), index=False)
    nb = trials.dropna(subset=["intervention_12_months", "control_12_months"]).shape[0]
    print(f"  wrote consensus_trials.csv ({len(trials)} trials; both arms: {nb}; "
          f"median delta12 = {trials['delta_12_months'].median():.1f})")

    # ---------- category breakdown ----------
    cat = pd.read_csv(os.path.join(ORIG_DATA, "category_breakdown_consensus.csv"))
    cat["intervention_type"] = cat.apply(relabel, axis=1)
    cat["_excl"] = cat.apply(is_excl, axis=1)
    cat = cat[~cat["_excl"]].drop(columns="_excl")
    cat = cat.sort_values(["filename", "intervention_type", "total_12_months"])
    cat["pos_idx"] = cat.groupby(["filename", "intervention_type"]).cumcount()
    cat.to_csv(os.path.join(DATA, "category_breakdown_consensus.csv"), index=False)
    print(f"  wrote corrected category_breakdown_consensus.csv ({len(cat)} rows)")

    # summary
    print(f"\nVerified-cohort quick check:")
    print(f"  Median 12mo TT intervention: "
          f"{arms[arms.intervention_type=='intervention']['12_months'].median():.1f}")
    print(f"  Median 12mo TT control:      "
          f"{arms[arms.intervention_type=='control']['12_months'].median():.1f}")


if __name__ == "__main__":
    main()
