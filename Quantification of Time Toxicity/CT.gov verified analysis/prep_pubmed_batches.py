#!/usr/bin/env python3
"""Prepare per-trial input for subagent abstract extraction; split into batches."""
import os, json, warnings
warnings.filterwarnings("ignore")
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
PMCACHE = os.path.join(BASE, "pubmed_cache")
BATCHDIR = os.path.join(BASE, "pubmed_batches")
os.makedirs(BATCHDIR, exist_ok=True)

N_BATCHES = 8


def main():
    ab = pd.read_csv(os.path.join(PMCACHE, "abstracts.csv"))
    arms = pd.read_csv(os.path.join(DATA, "consensus_arms.csv"))
    arms_by_fn = arms.groupby("filename")["arm_name"].apply(list).to_dict()

    records = []
    for _, r in ab.iterrows():
        fn = r["filename"]
        records.append({
            "filename": fn,
            "nct": str(r["nct"]),
            "pmid": str(r["pmid"]),
            "arm_names": arms_by_fn.get(fn, []),
            "abstract": str(r["abstract"])[:6000],
        })

    # split into N batches
    per = (len(records) + N_BATCHES - 1) // N_BATCHES
    for b in range(N_BATCHES):
        chunk = records[b*per:(b+1)*per]
        if not chunk:
            continue
        with open(os.path.join(BATCHDIR, f"batch_{b:02d}.json"), "w") as f:
            json.dump(chunk, f, indent=1)
    print(f"Wrote {N_BATCHES} batches (~{per} trials each) for {len(records)} trials to {BATCHDIR}")


if __name__ == "__main__":
    main()
