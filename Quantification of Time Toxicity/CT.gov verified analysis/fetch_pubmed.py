#!/usr/bin/env python3
"""
Phase 1.5: Fetch PubMed abstracts for the 231 trials needing arbitration.
Batched efetch (rettype=abstract). Cache to pubmed_cache/{pmid}.txt.
Produces pubmed_cache/abstracts.csv (filename, nct, pmid, abstract).
"""
import os, time, warnings
warnings.filterwarnings("ignore")
import pandas as pd
import requests

BASE = os.path.dirname(os.path.abspath(__file__))
TABLES = os.path.join(BASE, "tables")
PMCACHE = os.path.join(BASE, "pubmed_cache")
os.makedirs(PMCACHE, exist_ok=True)
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def fetch_batch(pmids, session):
    ids = ",".join(pmids)
    r = session.get(EFETCH, params={"db": "pubmed", "id": ids,
                                    "rettype": "abstract", "retmode": "text"}, timeout=30)
    r.raise_for_status()
    return r.text


def split_records(text):
    """Split a multi-record abstract text dump into individual records by blank-line/number pattern."""
    # Records are separated by a line starting with a number+period at col 0 after a blank line.
    import re
    # Each record begins with "N. " journal line. Split on lines like "\n\nN. "
    parts = re.split(r"\n\n(?=\d+\.\s)", text.strip())
    return [p.strip() for p in parts if p.strip()]


def main():
    need = pd.read_csv(os.path.join(TABLES, "trials_needing_pubmed.csv"))
    need["pmid"] = need["pmid"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    need = need[need["pmid"].str.match(r"^\d+$", na=False)].copy()
    pmids = need["pmid"].tolist()
    print(f"Fetching {len(pmids)} PubMed abstracts (cache-first)...")

    session = requests.Session()
    session.headers.update({"Accept": "text/plain"})

    # cache-first per pmid; batch the missing
    missing = [p for p in pmids if not os.path.exists(os.path.join(PMCACHE, f"{p}.txt"))]
    print(f"  {len(pmids)-len(missing)} cached, {len(missing)} to fetch")

    BATCH = 20
    for i in range(0, len(missing), BATCH):
        batch = missing[i:i+BATCH]
        try:
            text = fetch_batch(batch, session)
            recs = split_records(text)
            # Best-effort: if record count matches, map in order; else fetch individually
            if len(recs) == len(batch):
                for pmid, rec in zip(batch, recs):
                    with open(os.path.join(PMCACHE, f"{pmid}.txt"), "w") as f:
                        f.write(rec)
            else:
                for pmid in batch:
                    txt = fetch_batch([pmid], session)
                    with open(os.path.join(PMCACHE, f"{pmid}.txt"), "w") as f:
                        f.write(txt.strip())
                    time.sleep(0.35)
        except Exception as e:
            print(f"  batch {i} error: {e}; falling back to singles")
            for pmid in batch:
                try:
                    txt = fetch_batch([pmid], session)
                    with open(os.path.join(PMCACHE, f"{pmid}.txt"), "w") as f:
                        f.write(txt.strip())
                except Exception as e2:
                    print(f"    {pmid} failed: {e2}")
                time.sleep(0.4)
        time.sleep(0.4)
        if (i // BATCH) % 3 == 0:
            print(f"  {min(i+BATCH,len(missing))}/{len(missing)}")

    # assemble abstracts.csv
    rows = []
    for _, r in need.iterrows():
        p = os.path.join(PMCACHE, f"{r['pmid']}.txt")
        ab, ok = ("", False)
        if os.path.exists(p):
            ab, ok = open(p).read(), True
        rows.append({"filename": r["filename"], "nct": r["NCT Number"], "pmid": r["pmid"],
                     "abstract": ab, "fetched": ok, "abstract_len": len(ab, ) if ok else 0})
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(PMCACHE, "abstracts.csv"), index=False)
    print(f"\nAssembled {len(out)} rows; fetched OK: {out['fetched'].sum()}; "
          f"empty/short (<200 chars): {(out['abstract_len']<200).sum()}")


if __name__ == "__main__":
    main()
