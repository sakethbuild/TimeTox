#!/usr/bin/env python3
"""
Build a human-review package for the 52 flagged trials:
  tables/human_review_worksheet.csv  — one row per ARM (all arms of each flagged trial),
      with clickable URLs, the 3 sources, abstract evidence, and blank decision columns.
  HUMAN_REVIEW.md — readable digest grouped by reason, one block per trial.
"""
import os, warnings
warnings.filterwarnings("ignore")
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
TABLES = os.path.join(BASE, "tables")

fin = pd.read_csv(os.path.join(TABLES, "final_labels.csv"))
hr = pd.read_csv(os.path.join(TABLES, "human_review.csv"))

# trial -> dominant reason (PMID_MISMATCH > PUBMED_UNRESOLVED > CORRECTION_APPLIED)
prio = {"PMID_MISMATCH": 0, "PUBMED_UNRESOLVED": 1, "CORRECTION_APPLIED": 2}
trial_reason = (hr.groupby("filename")["review_reason"]
                .apply(lambda s: sorted(s, key=lambda r: prio[r])[0]).to_dict())
flagged = list(trial_reason.keys())

# all arms of flagged trials, with per-arm reason where applicable
arm_reason = {(r.filename, r.arm_name, r.pos_idx): r.review_reason for r in hr.itertuples()}

sub = fin[fin["filename"].isin(flagged)].copy()
sub["trial_reason"] = sub["filename"].map(trial_reason)
sub["arm_flag"] = [arm_reason.get((r.filename, r.arm_name, r.pos_idx), "") for r in sub.itertuples()]
sub["nct_url"] = "https://clinicaltrials.gov/study/" + sub["nct"].astype(str)
sub["pubmed_url"] = "https://pubmed.ncbi.nlm.nih.gov/" + fin["filename"].map(
    fin.drop_duplicates("filename").set_index("filename")["nct"].to_dict()).fillna("")  # placeholder; fix below

# pmid from filename mapping
# (final_labels lacks pmid; pull from trials_needing_pubmed + enriched)
trials = pd.read_csv(os.path.join(BASE, "data", "enriched_trials.csv"))[["filename", "pmid"]]
pmid_map = dict(zip(trials["filename"], trials["pmid"].astype(str).str.replace(r"\.0$", "", regex=True)))
sub["pmid"] = sub["filename"].map(pmid_map)
sub["pubmed_url"] = "https://pubmed.ncbi.nlm.nih.gov/" + sub["pmid"].astype(str)

# order trials by reason then filename, arms by pos within
sub["_p"] = sub["trial_reason"].map(prio)
sub = sub.sort_values(["_p", "filename", "pipeline_label", "pos_idx"])

# worksheet columns
ws = sub[["trial_reason", "nct", "nct_url", "pmid", "pubmed_url", "arm_name", "tt_12mo",
          "pipeline_label", "ctgov_label", "ctgov_type", "pubmed_designation",
          "pubmed_evidence", "final_label", "arm_flag"]].copy()
ws["human_decision (intervention/control/exclude)"] = ""
ws["human_notes"] = ""
ws.to_csv(os.path.join(TABLES, "human_review_worksheet.csv"), index=False)

# ---- readable markdown digest ----
md = ["# Human Review — 52 Flagged Trials\n",
      "Review the three sources and record your call in `human_review_worksheet.csv` "
      "(columns `human_decision` / `human_notes`). Reason groups below.\n",
      "Legend: **pipe**=pipeline label · **CT.gov**=registrant type · **PubMed**=abstract extraction.\n"]

reason_titles = {
    "PMID_MISMATCH": "## 1. WRONG PMID (4 trials) — dataset PMID points to an unrelated paper; find correct PMID or exclude",
    "PUBMED_UNRESOLVED": "## 2. PUBMED UNRESOLVED — abstract doesn't establish the arm role (head-to-head, or arm not described); currently keeping pipeline label",
    "CORRECTION_APPLIED": "## 3. CORRECTION APPLIED — pipeline label was overridden by the PubMed-arbitrated gold standard; verify",
}
for reason in ["PMID_MISMATCH", "PUBMED_UNRESOLVED", "CORRECTION_APPLIED"]:
    md.append(reason_titles[reason])
    rt = sub[sub["trial_reason"] == reason]
    for fn, g in rt.groupby("filename"):
        nct = g["nct"].iloc[0]; pmid = g["pmid"].iloc[0]
        md.append(f"\n### {nct} (PMID {pmid})")
        md.append(f"- CT.gov: https://clinicaltrials.gov/study/{nct}  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/{pmid}")
        for r in g.itertuples():
            ev = f' — _"{r.pubmed_evidence}"_' if isinstance(r.pubmed_evidence, str) and r.pubmed_evidence else ""
            star = " ⬅FLAGGED" if r.arm_flag else ""
            md.append(f"  - **{r.arm_name}** (TT={r.tt_12mo}d): pipe=`{r.pipeline_label}` · "
                      f"CT.gov=`{r.ctgov_label}`({r.ctgov_type}) · PubMed=`{r.pubmed_designation}` → **final=`{r.final_label}`**{star}{ev}")
    md.append("")

with open(os.path.join(BASE, "HUMAN_REVIEW.md"), "w") as f:
    f.write("\n".join(md))

print(f"Worksheet: tables/human_review_worksheet.csv ({len(ws)} arm rows across {len(flagged)} trials)")
print(f"Digest:    HUMAN_REVIEW.md")
print(f"\nTrials by reason:")
for r in ["PMID_MISMATCH","PUBMED_UNRESOLVED","CORRECTION_APPLIED"]:
    n = sum(1 for v in trial_reason.values() if v==r)
    print(f"  {r}: {n} trials")
