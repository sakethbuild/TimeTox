#!/usr/bin/env python3
"""
Phase 1.6: Reconcile pipeline / CT.gov / PubMed into a final gold-standard label
per arm. Produce the final discrepancy report and the human-review file.

Rules (user-approved):
- Trials where pipeline & CT.gov AGREE (413): final = pipeline label.
- Trials needing arbitration (231): PubMed arbitrates.
    * PubMed resolved -> final = PubMed designation.
    * PubMed unresolved -> final = pipeline original (working fallback) + needs_human_review.
- Everything contested or unresolved is written to human_review.csv.
"""
import os, json, glob, math, warnings
warnings.filterwarnings("ignore")
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
TABLES = os.path.join(BASE, "tables")
BATCHDIR = os.path.join(BASE, "pubmed_batches")


def wilson(k, n, z=1.96):
    if n == 0: return (float("nan"), float("nan"))
    p = k/n; d = 1+z*z/n
    c = (p+z*z/(2*n))/d; h = (z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)))/d
    return (max(0,c-h), min(1,c+h))


def load_pubmed():
    """Return dict (filename, arm_name) -> (designation, evidence). Remediation overrides first pass."""
    des = {}
    for f in sorted(glob.glob(os.path.join(BATCHDIR, "result_*.json"))):
        for r in json.load(open(f)):
            for a in r["arms"]:
                des[(r["filename"], a["arm_name"])] = (a["designation"], a.get("evidence",""))
    # remediation overrides (only where it resolved something)
    for f in sorted(glob.glob(os.path.join(BATCHDIR, "remediation_result_*.json"))):
        for r in json.load(open(f)):
            for a in r["arms"]:
                key = (r["filename"], a["arm_name"])
                prev = des.get(key, ("unresolved",""))
                # take remediation if it resolves, or if no prior
                if a["designation"] != "unresolved" or key not in des:
                    des[key] = (a["designation"], a.get("evidence",""))
                elif prev[0] == "unresolved":
                    des[key] = (a["designation"], a.get("evidence",""))
    return des


def main():
    m = pd.read_csv(os.path.join(TABLES, "ctgov_arm_matches.csv"))
    need = set(pd.read_csv(os.path.join(TABLES, "trials_needing_pubmed.csv"))["filename"])
    pubmed = load_pubmed()

    rows = []
    for _, r in m.iterrows():
        fn, arm = r["filename"], r["arm_name"]
        pipe = r["original_label"]
        ctg = r["ctgov_label"] if pd.notna(r["ctgov_label"]) else None
        in_need = fn in need

        pm_des, pm_ev = pubmed.get((fn, arm), (None, ""))

        if not in_need:
            final, source, review = pipe, "agreement(pipeline=ctgov)", False
        else:
            if pm_des in ("intervention", "control"):
                final, source, review = pm_des, "pubmed", False
            else:
                final, source, review = pipe, "pipeline_fallback(pubmed_unresolved)", True

        rows.append({
            "filename": fn, "nct": r["nct"], "pos_idx": r["pos_idx"], "arm_name": arm,
            "tt_12mo": r["tt_12mo"],
            "pipeline_label": pipe, "ctgov_label": ctg, "ctgov_type": r["ctgov_type"],
            "pubmed_designation": pm_des, "pubmed_evidence": pm_ev,
            "final_label": final, "final_source": source,
            "needs_human_review": review,
            "match_status": r["match_status"],
            "n_pipeline_arms": r["n_pipeline_arms"], "n_ctgov_arms": r["n_ctgov_arms"],
            "pipeline_vs_final_flip": final != pipe,
        })

    fin = pd.DataFrame(rows)
    fin.to_csv(os.path.join(TABLES, "final_labels.csv"), index=False)

    # ---- FINAL discrepancy: original pipeline vs final gold standard ----
    # resolved arms = final_source in agreement or pubmed (i.e., not human-review fallback)
    resolved = fin[fin["final_source"].isin(["agreement(pipeline=ctgov)", "pubmed"])]
    n_res = len(resolved)
    n_flip = int(resolved["pipeline_vs_final_flip"].sum())
    lo, hi = wilson(n_flip, n_res)

    # among arbitrated (pubmed) arms only
    arb = fin[fin["final_source"] == "pubmed"]
    n_arb = len(arb); n_arb_flip = int(arb["pipeline_vs_final_flip"].sum())

    # who pubmed sided with, on the contested arms
    # contested = arm where pipeline != ctgov and pubmed resolved
    cont = fin[(fin["pipeline_label"] != fin["ctgov_label"]) & (fin["pubmed_designation"].isin(["intervention","control"]))]
    pm_with_pipe = int((cont["pubmed_designation"] == cont["pipeline_label"]).sum())
    pm_with_ctg = int((cont["pubmed_designation"] == cont["ctgov_label"]).sum())

    # ---- human review file ----
    review = fin[fin["needs_human_review"] |
                 ((fin["pipeline_label"] != fin["ctgov_label"]) & (fin["final_source"]=="pubmed"))].copy()
    review = review.sort_values(["needs_human_review","filename"], ascending=[False, True])
    review.to_csv(os.path.join(TABLES, "human_review.csv"), index=False)

    n_review_arms = int(fin["needs_human_review"].sum())
    n_review_trials = fin[fin["needs_human_review"]]["filename"].nunique()

    # trial-level final flip + headline impact recompute
    def derive(g, col):
        out = {}
        for lab in ("intervention","control"):
            s = g[g[col]==lab].sort_values("tt_12mo")
            out[lab] = s["tt_12mo"].iloc[0] if len(s) else float("nan")
        return out["intervention"], out["control"]
    tl = []
    for fn, g in fin.groupby("filename"):
        iv0,ct0 = derive(g,"pipeline_label"); ivf,ctf = derive(g,"final_label")
        d0 = iv0-ct0 if pd.notna(iv0) and pd.notna(ct0) else float("nan")
        df = ivf-ctf if pd.notna(ivf) and pd.notna(ctf) else float("nan")
        if pd.isna(d0) and pd.isna(df): ch=False
        elif pd.isna(d0) or pd.isna(df): ch=True
        else: ch = abs(d0-df)>1e-9
        tl.append({"filename":fn,"any_flip":bool(g["pipeline_vs_final_flip"].any()),
                   "delta_changed":ch,"needs_review":bool(g["needs_human_review"].any())})
    tld = pd.DataFrame(tl)
    n_tflip = int(tld["any_flip"].sum()); n_dchg = int(tld["delta_changed"].sum())

    print("="*66)
    print("FINAL 3-WAY RECONCILED DISCREPANCY (original pipeline vs gold standard)")
    print("="*66)
    print(f"Resolved arms (agreement + pubmed-arbitrated): {n_res}")
    print(f"  Arm-level discrepancy: {n_flip}/{n_res} = {100*n_flip/n_res:.1f}%  (95% CI {100*lo:.1f}-{100*hi:.1f}%)")
    print(f"Trial-level: any-arm relabeled = {n_tflip}/644 = {100*n_tflip/644:.1f}%")
    print(f"Headline-impact (delta12 changed) = {n_dchg}/644 = {100*n_dchg/644:.1f}%")
    print()
    print(f"On the {len(cont)} contested arms (pipeline vs CT.gov disagree) where PubMed resolved:")
    print(f"  PubMed sided with PIPELINE: {pm_with_pipe}")
    print(f"  PubMed sided with CT.gov:   {pm_with_ctg}")
    print()
    print(f"Human-review file: {n_review_arms} arms across {n_review_trials} trials -> tables/human_review.csv")
    print(f"  (PubMed-unresolved fallbacks + contested arbitrations)")
    print()
    print("Final label source breakdown:")
    print(fin["final_source"].value_counts().to_string())


if __name__ == "__main__":
    main()
