#!/usr/bin/env python3
"""
Global content-integrity sweep: for all 644 trials, compare pipeline arm drugs
vs CT.gov interventions WITH brand->generic alias canonicalization. Flag trials
where both sides have recognized drugs but zero overlap (mis-linked protocol).
Reuses tokenization + ALIASES from ctgov_match.py.
"""
import os, json, warnings, importlib.util
warnings.filterwarnings("ignore")
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
TABLES = os.path.join(BASE, "tables")
CACHE = os.path.join(BASE, "ctgov_cache")

# import tokenize/canon/KNOWN_DRUGS from ctgov_match.py
spec = importlib.util.spec_from_file_location("ctgov_match", os.path.join(BASE, "ctgov_match.py"))
cm = importlib.util.module_from_spec(spec); spec.loader.exec_module(cm)


def drug_set(text):
    dt, pl, at = cm.tokenize(text)
    return dt  # recognized canonical drug tokens


def main():
    arms = pd.read_csv(os.path.join(DATA, "consensus_arms.csv"))
    trials = pd.read_csv(os.path.join(DATA, "enriched_trials.csv"))[["filename", "NCT Number", "pmid"]]
    fn2nct = dict(zip(trials["filename"], trials["NCT Number"].astype(str)))

    rows = []
    for fn, g in arms.groupby("filename"):
        nct = fn2nct.get(fn)
        cache = os.path.join(CACHE, f"{nct}.json")
        if not nct or not os.path.exists(cache):
            continue
        d = json.load(open(cache))
        ai = d.get("protocolSection", {}).get("armsInterventionsModule", {})
        ct = set()
        for iv in ai.get("interventions", []) or []:
            ct |= drug_set(iv.get("name", ""))
        for ag in ai.get("armGroups", []) or []:
            ct |= drug_set(ag.get("label", ""))
        pipe = set()
        for nm in g["arm_name"]:
            pipe |= drug_set(nm)
        overlap = pipe & ct
        rows.append({"filename": fn, "nct": nct,
                     "pipe_drugs": ",".join(sorted(pipe)), "ct_drugs": ",".join(sorted(ct)),
                     "n_pipe": len(pipe), "n_ct": len(ct), "n_overlap": len(overlap),
                     "mismatch": len(pipe) > 0 and len(ct) > 0 and len(overlap) == 0})
    r = pd.DataFrame(rows)
    r.to_csv(os.path.join(TABLES, "content_integrity_sweep.csv"), index=False)
    sus = r[r["mismatch"]]
    print(f"Trials checked (both sides have recognized drugs): {((r.n_pipe>0)&(r.n_ct>0)).sum()}")
    print(f"Content-mismatch flags (zero drug overlap, alias-aware): {len(sus)}")
    print()
    for _, x in sus.iterrows():
        print(f"  {x['nct']:12s} {x['filename'][:42]}")
        print(f"      pipeline drugs: {x['pipe_drugs']}")
        print(f"      CT.gov drugs:   {x['ct_drugs']}")
    pd.set_option("display.max_colwidth", 60)
    sus.to_csv(os.path.join(TABLES, "content_mismatch_flags.csv"), index=False)
    print(f"\nSaved tables/content_mismatch_flags.csv")


if __name__ == "__main__":
    main()
