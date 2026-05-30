#!/usr/bin/env python3
"""
Phase 1, Step 3: Match CT.gov arms to pipeline arms by drug content, derive
the CT.gov "gold-standard" intervention/control label per pipeline arm.

Outputs tables/ctgov_arm_matches.csv (one row per pipeline arm) with the
original label, the CT.gov-derived label, match confidence, and match_status.

Does NOT modify consensus_arms.csv (that happens in Phase 2 only).
"""

import os
import sys
import json
import re
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
TABLES = os.path.join(BASE, "tables")
CACHE = os.path.join(BASE, "ctgov_cache")
INPUT_ROOT = "/Users/sakethvinjamuri/Documents/TimeToxSV/Quantification of Time Toxicity"

sys.path.insert(0, INPUT_ROOT)
from config import DRUG_CLASSES  # 222 drug→class entries

# CT.gov arm type -> binary label
TYPE_MAP = {
    "EXPERIMENTAL": "intervention",
    "ACTIVE_COMPARATOR": "control",
    "PLACEBO_COMPARATOR": "control",
    "NO_INTERVENTION": "control",
    "SHAM_COMPARATOR": "control",
    # OTHER handled separately (resolve by drug content + flag)
}

CONF_THRESHOLD = 0.45

# Brand -> generic alias map (seeded; extends DRUG_CLASSES vocabulary)
ALIASES = {
    "xofigo": "radium-223", "radium 223": "radium-223", "radium-223 dichloride": "radium-223",
    "herceptin": "trastuzumab", "keytruda": "pembrolizumab", "opdivo": "nivolumab",
    "tecentriq": "atezolizumab", "imfinzi": "durvalumab", "yervoy": "ipilimumab",
    "nolvadex": "tamoxifen", "arimidex": "anastrozole", "femara": "letrozole",
    "aromasin": "exemestane", "zoladex": "goserelin", "lupron": "leuprolide",
    "velcade": "bortezomib", "revlimid": "lenalidomide", "thalomid": "thalidomide",
    "taxotere": "docetaxel", "taxol": "paclitaxel", "gemzar": "gemcitabine",
    "eloxatin": "oxaliplatin", "avastin": "bevacizumab", "erbitux": "cetuximab",
    "tarceva": "erlotinib", "iressa": "gefitinib", "sutent": "sunitinib",
    "nexavar": "sorafenib", "afinitor": "everolimus", "zaltrap": "aflibercept",
    "zytiga": "abiraterone", "xtandi": "enzalutamide", "zometa": "zoledronic",
    "zoledronate": "zoledronic", "decadron": "dexamethasone", "dtic": "dacarbazine",
    "5-fu": "fluorouracil", "5 fu": "fluorouracil", "ac regimen": "doxorubicin cyclophosphamide",
    "g-csf": "filgrastim", "neulasta": "pegfilgrastim",
}

STOPWORDS = {
    "alone", "monotherapy", "group", "arm", "cohort", "standard", "care", "soc", "of", "the",
    "dose", "mg", "plus", "treatment", "experimental", "comparator", "placebo-controlled",
    "with", "and", "or", "vs", "versus", "only", "regimen", "therapy", "iv", "oral", "daily",
    "weekly", "study", "control", "active", "high", "low", "a", "b", "c", "d", "i", "ii", "iii",
    "1", "2", "3", "4", "5", "6", "patients", "receive", "received", "every", "weeks", "days",
}

KNOWN_DRUGS = set(DRUG_CLASSES.keys()) | set(ALIASES.values())


def canon(tok):
    tok = tok.strip().lower()
    return ALIASES.get(tok, tok)


def tokenize(text):
    """Return (drug_tokens:set, has_placebo:bool, raw_token_set:set)."""
    if not text or (isinstance(text, float) and np.isnan(text)):
        return set(), False, set()
    s = str(text).lower()
    # strip wrappers: "Arm X (...)", "Group N (...)", and intervention-type prefixes
    s = re.sub(r"\b(drug|biological|radiation|procedure|other|device|genetic|behavioral|"
               r"dietary supplement|diagnostic test|combination product):\s*", " ", s)
    has_placebo = "placebo" in s
    # apply multi-word aliases first
    for alias, generic in ALIASES.items():
        if alias in s:
            s = s.replace(alias, " " + generic + " ")
    # split on separators
    parts = re.split(r"[\+\/,&\(\)\|\-]|\s+|plus\b|and\b", s)
    toks = set()
    for p in parts:
        p = canon(p)
        if not p or p in STOPWORDS or len(p) < 3:
            continue
        if not re.search(r"[a-z]", p):
            continue
        toks.add(p)
    drug_toks = {t for t in toks if t in KNOWN_DRUGS}
    return drug_toks, has_placebo, toks


def weighted_jaccard(a_drug, a_all, a_pl, b_drug, b_all, b_pl):
    """Weighted token similarity; recognized drugs 3x, placebo symmetric sentinel."""
    # union/intersection with weights
    all_toks = a_all | b_all
    if not all_toks and not (a_pl or b_pl):
        return 0.0
    inter = 0.0
    union = 0.0
    for t in all_toks:
        w = 3.0 if t in KNOWN_DRUGS else 1.0
        in_a = t in a_all
        in_b = t in b_all
        union += w
        if in_a and in_b:
            inter += w
    # placebo sentinel
    if a_pl or b_pl:
        union += 2.0
        if a_pl and b_pl:
            inter += 2.0
    return inter / union if union > 0 else 0.0


def load_ctgov_arms(nct):
    """Return list of dicts {label, type, drug_toks, all_toks, has_placebo} or None."""
    path = os.path.join(CACHE, f"{nct}.json")
    if not os.path.exists(path):
        return None
    try:
        d = json.load(open(path))
    except Exception:
        return None
    ai = d.get("protocolSection", {}).get("armsInterventionsModule", {})
    groups = ai.get("armGroups", []) or []
    if not groups:
        return []
    arms = []
    for g in groups:
        label = g.get("label", "")
        ints = g.get("interventionNames", []) or []
        text = label + " | " + " | ".join(ints)
        dt, pl, at = tokenize(text)
        arms.append({"label": label, "type": g.get("type", "OTHER"),
                     "drug_toks": dt, "all_toks": at, "has_placebo": pl,
                     "intervention_names": ints})
    return arms


def ctgov_label(arm_type, drug_toks, exp_drug_union):
    """Map a CT.gov type to binary; OTHER resolved by drug content."""
    if arm_type in TYPE_MAP:
        return TYPE_MAP[arm_type], False
    # OTHER: if it shares an experimental drug, call it intervention; else control. Flag uncertain.
    if drug_toks & exp_drug_union:
        return "intervention", True
    return "control", True


def main():
    arms_df = pd.read_csv(os.path.join(DATA, "consensus_arms.csv"))
    trials = pd.read_csv(os.path.join(DATA, "enriched_trials.csv"))
    fn_to_nct = dict(zip(trials["filename"], trials["NCT Number"].astype(str).str.strip()))

    out_rows = []
    for fn, g in arms_df.groupby("filename"):
        nct = fn_to_nct.get(fn, None)
        pipe = g.reset_index(drop=True)
        n_pipe = len(pipe)

        ct_arms = load_ctgov_arms(nct) if nct and nct != "nan" else None

        # Pipeline arm token sets
        pipe_tok = [tokenize(r["arm_name"]) for _, r in pipe.iterrows()]

        if ct_arms is None:
            status = "ctgov_404" if nct else "no_nct"
            for i, (_, r) in enumerate(pipe.iterrows()):
                out_rows.append(_row(fn, nct, r, r["intervention_type"], None, 0.0, status, n_pipe, 0))
            continue
        if len(ct_arms) == 0:
            for i, (_, r) in enumerate(pipe.iterrows()):
                out_rows.append(_row(fn, nct, r, r["intervention_type"], None, 0.0, "ctgov_no_armgroups", n_pipe, 0))
            continue

        n_ct = len(ct_arms)
        # experimental drug union (for OTHER resolution)
        exp_drug_union = set()
        for a in ct_arms:
            if a["type"] == "EXPERIMENTAL":
                exp_drug_union |= a["drug_toks"]

        # similarity matrix pipe x ctgov
        sim = np.zeros((n_pipe, n_ct))
        for i, (pd_, ppl, pall) in enumerate(pipe_tok):
            for j, a in enumerate(ct_arms):
                sim[i, j] = weighted_jaccard(pd_, pall, ppl, a["drug_toks"], a["all_toks"], a["has_placebo"])

        # Hungarian assignment on min(n_pipe, n_ct)
        cost = 1.0 - sim
        row_ind, col_ind = linear_sum_assignment(cost)
        assign = {int(r): int(c) for r, c in zip(row_ind, col_ind)}

        count_mismatch = (n_pipe != n_ct)

        for i, (_, r) in enumerate(pipe.iterrows()):
            orig = r["intervention_type"]
            if i in assign:
                j = assign[i]
                a = ct_arms[j]
                ct_lab, other_flag = ctgov_label(a["type"], a["drug_toks"], exp_drug_union)
                s = sim[i, j]
                # confidence adjustments
                conf = float(s)
                pd_i = pipe_tok[i][0]
                if not pd_i and not a["drug_toks"]:
                    conf -= 0.30  # both generic
                if other_flag:
                    conf -= 0.25
                if count_mismatch:
                    conf -= 0.20
                conf = max(0.0, min(1.0, conf))

                if n_pipe == 2 and n_ct == 2:
                    # 2-arm: trust CT.gov type by elimination even if drug-sim low
                    status = "confident_2arm"
                    if conf < CONF_THRESHOLD:
                        conf = max(conf, 0.50)  # elimination is reliable for 2-arm
                elif conf >= CONF_THRESHOLD and not other_flag:
                    status = "confident"
                else:
                    status = "uncertain"
                if count_mismatch:
                    status = "count_mismatch"
                out_rows.append(_row(fn, nct, r, orig, ct_lab, conf, status, n_pipe, n_ct,
                                     ct_type=a["type"], ct_label_text=a["label"]))
            else:
                # leftover pipeline arm (count mismatch, no CT.gov match) -> keep original
                out_rows.append(_row(fn, nct, r, orig, orig, 0.0, "count_mismatch_leftover", n_pipe, n_ct))

    out = pd.DataFrame(out_rows)
    os.makedirs(TABLES, exist_ok=True)
    out.to_csv(os.path.join(TABLES, "ctgov_arm_matches.csv"), index=False)
    print(f"Wrote {len(out)} arm match rows to tables/ctgov_arm_matches.csv")
    print("\nmatch_status distribution:")
    print(out["match_status"].value_counts().to_string())


def _row(fn, nct, r, orig, ct_lab, conf, status, n_pipe, n_ct, ct_type=None, ct_label_text=None):
    return {
        "filename": fn, "nct": nct, "pos_idx": r["pos_idx"], "arm_name": r["arm_name"],
        "tt_12mo": r["12_months"],
        "original_label": orig, "ctgov_label": ct_lab,
        "ctgov_type": ct_type, "ctgov_label_text": ct_label_text,
        "confidence": round(conf, 3), "match_status": status,
        "n_pipeline_arms": n_pipe, "n_ctgov_arms": n_ct,
        "label_flipped": (ct_lab is not None and ct_lab != orig),
    }


if __name__ == "__main__":
    main()
