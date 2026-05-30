#!/usr/bin/env python3
"""
Build a self-contained review CSV for the 23 PUBMED_UNRESOLVED trials:
one row per arm, with the full (cleaned) PubMed abstract alongside each arm's
three-source labels + evidence + a blank human_decision column.
Output: tables/unresolved_review_with_abstracts.csv
"""
import os, glob, json, importlib.util, warnings
warnings.filterwarnings("ignore")
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
TABLES = os.path.join(BASE, "tables")
PMCACHE = os.path.join(BASE, "pubmed_cache")

# reuse clean_abstract() from prep_remediation.py
spec = importlib.util.spec_from_file_location("prep_remediation", os.path.join(BASE, "prep_remediation.py"))
pr = importlib.util.module_from_spec(spec); spec.loader.exec_module(pr)

fin = pd.read_csv(os.path.join(TABLES, "final_labels.csv"))
ws = pd.read_csv(os.path.join(TABLES, "human_review_worksheet.csv"))
trials = pd.read_csv(os.path.join(DATA, "enriched_trials.csv"))[["filename", "pmid"]]
pmid_map = dict(zip(trials["filename"], trials["pmid"].astype(str).str.replace(r"\.0$", "", regex=True)))

unres_ncts = ws[ws.trial_reason == "PUBMED_UNRESOLVED"]["nct"].unique()

# design summaries
summ = {}
for f in glob.glob(os.path.join(BASE, "pubmed_batches", "result_*.json")) + \
         glob.glob(os.path.join(BASE, "pubmed_batches", "remediation_result_*.json")):
    for r in json.load(open(f)):
        summ[r["filename"]] = str(r.get("trial_design_summary", ""))


def category(g):
    pm = g["pubmed_designation"]
    n_un = (pm == "unresolved").sum()
    if n_un == len(g):
        return "A: head-to-head (no control in abstract)"
    if (pm == "intervention").sum() >= 1 and (pm == "control").sum() >= 1:
        return "B: primary resolved; secondary arm not in abstract"
    return "C: partial/different objective reported"


rows = []
for nct in unres_ncts:
    g = fin[fin.nct == nct].copy()
    fn = g["filename"].iloc[0]
    pmid = pmid_map.get(fn, "")
    cat = category(g)
    # cleaned abstract
    raw_path = os.path.join(PMCACHE, f"{pmid}.txt")
    abstract = pr.clean_abstract(open(raw_path).read()) if os.path.exists(raw_path) else "(abstract not cached)"
    ds = summ.get(fn, "")
    for i, (_, r) in enumerate(g.sort_values(["pubmed_designation", "pos_idx"]).iterrows()):
        rows.append({
            "category": cat,
            "nct": nct,
            "pmid": pmid,
            "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}",
            "ctgov_url": f"https://clinicaltrials.gov/study/{nct}",
            "design_summary": ds,
            "arm_name": r["arm_name"],
            "tt_12mo": r["tt_12mo"],
            "pipeline_label": r["pipeline_label"],
            "ctgov_type": r["ctgov_type"],
            "ctgov_label": r["ctgov_label"],
            "pubmed_designation": r["pubmed_designation"],
            "pubmed_evidence": r["pubmed_evidence"],
            "current_final_label": r["final_label"],
            "this_arm_unresolved": (r["pubmed_designation"] == "unresolved"),
            "HUMAN_DECISION (intervention/control/exclude)": "",
            "HUMAN_NOTES": "",
            # full abstract on every row for side-by-side reading
            "abstract_full": abstract,
        })

out = pd.DataFrame(rows)
# order: category, nct, then unresolved arms first within trial
out = out.sort_values(["category", "nct", "this_arm_unresolved"], ascending=[True, True, False])
out.to_csv(os.path.join(TABLES, "unresolved_review_with_abstracts.csv"), index=False)

print(f"Wrote tables/unresolved_review_with_abstracts.csv")
print(f"  {len(out)} arm rows across {out['nct'].nunique()} trials")
print(f"  unresolved arms (decision needed): {out['this_arm_unresolved'].sum()}")
print("\nBy category:")
print(out.drop_duplicates('nct')['category'].value_counts().to_string())
print(f"\nMean abstract length included: {int(out['abstract_full'].str.len().mean())} chars")
