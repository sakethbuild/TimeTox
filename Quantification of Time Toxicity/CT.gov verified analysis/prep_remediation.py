#!/usr/bin/env python3
"""Re-prep trials with unresolved arms, using author-stripped abstracts."""
import os, json, re, glob, warnings
warnings.filterwarnings("ignore")
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
PMCACHE = os.path.join(BASE, "pubmed_cache")
BATCHDIR = os.path.join(BASE, "pubmed_batches")


def clean_abstract(text):
    """Strip the author/affiliation/collaborator block; keep title + abstract body."""
    lines = text.split("\n")
    # find title: first non-empty line after the journal/doi header (line starting with 'N. Journal')
    # Heuristic: drop the 'Author information:' block and 'Collaborators:' block and the
    # author-name block (between title and 'Author information:').
    out = []
    # Join, then remove known boilerplate sections
    txt = text
    # Remove "Author information:" up to the next blank-blank or 'Erratum'/abstract start
    txt = re.sub(r"Author information:.*?(?:\n\n)", "\n\n", txt, flags=re.S)
    txt = re.sub(r"Collaborators:.*?(?:\n\n)", "\n\n", txt, flags=re.S)
    txt = re.sub(r"Erratum in.*?(?:\n\n)", "\n\n", txt, flags=re.S)
    txt = re.sub(r"Comment in.*?(?:\n\n)", "\n\n", txt, flags=re.S)
    txt = re.sub(r"Update of.*?(?:\n\n)", "\n\n", txt, flags=re.S)
    # Remove the footer (DOI:, PMID:, PMCID:, Copyright)
    txt = re.sub(r"\n(DOI|PMID|PMCID|Copyright|©).*$", "", txt, flags=re.S)
    # Collapse the author-name block: lines of "Surname AB, Surname CD, ..." right after the title.
    # Drop lines that are >60% commas+names with no sentence period structure and contain many commas.
    kept = []
    for ln in txt.split("\n"):
        s = ln.strip()
        # author-list line heuristic: many commas, ends with comma or has (1)(2) markers, no normal sentence
        if s.count(",") >= 4 and not re.search(r"\b(was|were|with|versus|received|randomi|patients|group|arm|median|hazard|survival)\b", s, re.I):
            continue
        kept.append(ln)
    txt = "\n".join(kept)
    txt = re.sub(r"\n{3,}", "\n\n", txt).strip()
    return txt[:8000]


def main():
    # find trials with unresolved arms
    results = []
    for f in sorted(glob.glob(os.path.join(BATCHDIR, "result_*.json"))):
        results.extend(json.load(open(f)))
    unresolved_fns = set()
    for r in results:
        if any(a["designation"] == "unresolved" for a in r.get("arms", [])):
            unresolved_fns.add(r["filename"])

    ab = pd.read_csv(os.path.join(PMCACHE, "abstracts.csv"))
    arms = pd.read_csv(os.path.join(DATA, "consensus_arms.csv"))
    arms_by_fn = arms.groupby("filename")["arm_name"].apply(list).to_dict()

    recs = []
    for _, r in ab.iterrows():
        if r["filename"] not in unresolved_fns:
            continue
        p = os.path.join(PMCACHE, f"{r['pmid']}.txt")
        raw = open(p).read() if os.path.exists(p) else ""
        recs.append({"filename": r["filename"], "nct": str(r["nct"]), "pmid": str(r["pmid"]),
                     "arm_names": arms_by_fn.get(r["filename"], []),
                     "abstract_cleaned": clean_abstract(raw)})
    # split into 2 batches
    half = (len(recs)+1)//2
    for b, chunk in enumerate([recs[:half], recs[half:]]):
        with open(os.path.join(BATCHDIR, f"remediation_{b:02d}.json"), "w") as f:
            json.dump(chunk, f, indent=1)
    print(f"Re-prepped {len(recs)} trials with unresolved arms into 2 remediation batches")
    # show a cleaned sample length
    if recs:
        print(f"Sample cleaned abstract length: {len(recs[0]['abstract_cleaned'])} (was capped at 6000 before)")


if __name__ == "__main__":
    main()
