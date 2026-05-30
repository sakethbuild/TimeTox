#!/usr/bin/env python3
"""
Apply human decisions (from the edited unresolved CSV) + the 2 content-mismatch
exclusions into a final reconciled label table: final_labels_reconciled.csv.

final_source values: agreement(pipeline=ctgov) | pubmed | human_review | excluded_content_mismatch
"""
import os, warnings
warnings.filterwarnings("ignore")
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
TABLES = os.path.join(BASE, "tables")

HUMAN_FILE = os.path.join(
    TABLES,
    "unresolved_review_with_abstracts - unresolved_review_with_abstracts_after_human_decision.csv.csv")
DEC_COL = "HUMAN_DECISION (intervention/control/exclude)"

EXCLUDE_NCTS = {"NCT01519700", "NCT02101021"}  # content-mismatch (mis-linked protocols)


def main():
    fin = pd.read_csv(os.path.join(TABLES, "final_labels.csv"))
    hum = pd.read_csv(HUMAN_FILE)

    # normalize decisions
    hum["dec"] = (hum[DEC_COL].astype(str).str.strip().str.lower()
                  .replace({"inervention": "intervention", "nan": ""}))
    # map (nct, arm_name) -> decision (drop blanks; dedupe keeping a non-blank)
    hum_dec = (hum[hum["dec"].isin(["intervention", "control", "exclude"])]
               .drop_duplicates(["nct", "arm_name"])
               .set_index(["nct", "arm_name"])["dec"].to_dict())

    fin["final_label_reconciled"] = fin["final_label"]
    fin["final_source_reconciled"] = fin["final_source"]
    fin["excluded"] = False

    n_human = n_excl = 0
    for i, r in fin.iterrows():
        key = (r["nct"], r["arm_name"])
        if r["nct"] in EXCLUDE_NCTS:
            fin.at[i, "excluded"] = True
            fin.at[i, "final_source_reconciled"] = "excluded_content_mismatch"
            n_excl += 1
        elif key in hum_dec:
            dec = hum_dec[key]
            if dec == "exclude":
                fin.at[i, "excluded"] = True
                fin.at[i, "final_source_reconciled"] = "excluded_human"
            else:
                fin.at[i, "final_label_reconciled"] = dec
                fin.at[i, "final_source_reconciled"] = "human_review"
            n_human += 1

    fin.to_csv(os.path.join(TABLES, "final_labels_reconciled.csv"), index=False)

    # report
    changed = fin[(fin["final_label_reconciled"] != fin["final_label"]) & (~fin["excluded"])]
    print(f"Applied {n_human} human arm-decisions; excluded {n_excl} arms (2 content-mismatch trials).")
    print(f"\nArms whose label CHANGED vs prior fallback: {len(changed)}")
    for _, r in changed.iterrows():
        print(f"  {r['nct']:12s} {r['arm_name'][:46]:46s} {r['final_label']:12s} -> {r['final_label_reconciled']}")

    print("\nFinal reconciled source breakdown:")
    print(fin["final_source_reconciled"].value_counts().to_string())

    # verified cohort size
    excl_trials = fin[fin["excluded"]]["nct"].nunique()
    print(f"\nExcluded trials: {excl_trials}  ->  verified cohort = {fin['nct'].nunique() - excl_trials} trials")

    # any trial left with unresolved/fallback?
    leftover = fin[fin["final_source_reconciled"].str.contains("fallback")]
    print(f"Arms still on pipeline-fallback (unresolved, no human decision): {len(leftover)}")
    if len(leftover):
        print(leftover[["nct","arm_name","final_label_reconciled"]].to_string(index=False))


if __name__ == "__main__":
    main()
