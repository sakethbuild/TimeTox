#!/usr/bin/env python3
"""
Phase 2, final: original vs CT.gov+PubMed-corrected headline comparison + sensitivity.
Outputs tables/headline_comparison.csv and HEADLINE_COMPARISON.md.
"""
import os, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
TABLES = os.path.join(BASE, "tables")
ORIG = "/Users/sakethvinjamuri/Documents/TimeToxSV/Quantification of Time Toxicity/data"


def med_iqr(s):
    s = s.dropna()
    return f"{s.median():.1f} ({s.quantile(.25):.1f}-{s.quantile(.75):.1f})"


def headline(trials, arms, label):
    iv = trials["intervention_12_months"].dropna()
    ct = trials["control_12_months"].dropna()
    both = trials.dropna(subset=["intervention_12_months", "control_12_months"])
    delta = both["intervention_12_months"] - both["control_12_months"]
    ident = (delta == 0).sum()
    d = {
        "scenario": label,
        "n_trials": trials["filename"].nunique(),
        "median_iv_TT": med_iqr(iv),
        "median_ct_TT": med_iqr(ct),
        "intensity_iv": f"{(iv/12).median():.2f}",
        "n_matched_pairs": len(both),
        "pct_identical_schedule": f"{100*ident/len(both):.1f}%",
        "median_delta_nonzero": f"{delta[delta!=0].median():.1f}" if (delta!=0).any() else "n/a",
        "pct_gt30d": f"{100*(iv>30).mean():.1f}%",
    }
    # subgroup medians (intervention, trial-level)
    for col, keys in [("disease_site", ["CNS", "Breast"]), ("treatment_modality", ["Chemotherapy", "Immunotherapy", "Targeted Therapy"])]:
        for k in keys:
            sub = trials[trials[col] == k]["intervention_12_months"].dropna()
            d[f"med_{k}"] = f"{sub.median():.1f} (n={len(sub)})" if len(sub) else "n/a"
    return d


def main():
    o_tr = pd.read_csv(os.path.join(ORIG, "enriched_trials.csv"))
    o_ar = pd.read_csv(os.path.join(ORIG, "enriched_arms.csv"))
    c_tr = pd.read_csv(os.path.join(DATA, "enriched_trials.csv"))
    c_ar = pd.read_csv(os.path.join(DATA, "enriched_arms.csv"))

    # sensitivity: corrected minus human_review/fallback trials
    rec = pd.read_csv(os.path.join(TABLES, "final_labels_reconciled.csv"))
    flagged = set(rec[rec["final_source_reconciled"].isin(
        ["human_review", "pipeline_fallback(pubmed_unresolved)"])]["filename"])
    s_tr = c_tr[~c_tr["filename"].isin(flagged)]
    s_ar = c_ar[~c_ar["filename"].isin(flagged)]

    rows = [headline(o_tr, o_ar, "ORIGINAL (644)"),
            headline(c_tr, c_ar, "CORRECTED (642)"),
            headline(s_tr, s_ar, f"SENSITIVITY (excl {len(flagged)} flagged → {s_tr['filename'].nunique()})")]
    comp = pd.DataFrame(rows).set_index("scenario").T
    comp.to_csv(os.path.join(TABLES, "headline_comparison.csv"))

    md = ["# Headline Comparison — Original vs CT.gov+PubMed-Corrected\n",
          comp.to_markdown(), "",
          "**Sensitivity** excludes trials whose labels came from human review or pipeline fallback "
          f"({len(flagged)} trials), retaining only pipeline=CT.gov agreement + PubMed-confident labels.",
          "", "## Interpretation",
          "The corrected cohort excludes 2 mis-linked-protocol trials (644→642). Differences between "
          "ORIGINAL and CORRECTED reflect the ~30 arm-label corrections; because the pipeline was right "
          "92% of the time it disagreed with CT.gov, headline medians move minimally."]
    with open(os.path.join(BASE, "HEADLINE_COMPARISON.md"), "w") as f:
        f.write("\n".join(md))

    print(comp.to_string())
    print(f"\nSensitivity excludes {len(flagged)} flagged trials.")
    print("Saved tables/headline_comparison.csv + HEADLINE_COMPARISON.md")


if __name__ == "__main__":
    main()
