# PR: CT.gov + PubMed arm-label verification; fix active_comparator normalization

**Branch:** `ctgov-pubmed-arm-verification` → `main`
**Open at:** https://github.com/sakethbuild/TimeToxSV/pull/new/ctgov-pubmed-arm-verification

---

## Summary

Robustness update to the TimeToxSV pipeline. Adds an external, three-source verification of intervention-vs-control arm labeling (ClinicalTrials.gov registry + PubMed abstracts) and corrects the arm-type normalization rule. **All headline results are materially unchanged** — the verification strengthens, rather than revises, the dataset.

## Motivation

The consensus builder normalized `active_comparator → intervention`, which is backwards: active-comparator arms are the control / standard-of-care condition by convention. This PR corrects the rule and adds a scalable verification step to confirm arm labels against external sources.

## What changed

- **Bug fix** — `01_build_consensus.py`: `active_comparator → control` (both the CSV and JSON normalization paths).
- **New `CT.gov verified analysis/`** — a self-contained verification + re-analysis package:
  - `fetch_ctgov.py`, `ctgov_match.py` — fetch CT.gov v2 API arm types for all 644 NCTs; match to extracted arms by drug-content similarity (weighted Jaccard + brand→generic aliases; Hungarian assignment for multi-arm trials).
  - `fetch_pubmed.py`, `reconcile_labels.py` — fetch PubMed abstracts for the 231 trials where pipeline and registry disagreed/were ambiguous; reconcile via abstract arbitration.
  - `apply_human_decisions.py`, `rederive.py` — apply reconciled labels, re-derive consensus + trial-level data, exclude mis-linked protocols.
  - Vendored `02`–`08` + `config.py`, re-run into an isolated `data/`, `tables/`, `figures/`.
  - Reports: `METHODOLOGY_LOG.md`, `DISCREPANCY_REPORT.md`, `HEADLINE_COMPARISON.md`; audit tables (`final_labels_reconciled.csv`, `per_trial_change_log.csv`, etc.); reproducibility caches (644 CT.gov JSON + 231 PubMed abstracts).

## Method (three-source verification)

1. **CT.gov** registry arm types (`EXPERIMENTAL`, `ACTIVE_COMPARATOR`, `PLACEBO_COMPARATOR`, …) for all 644 protocols, matched to extracted arms by drug content.
2. **PubMed** abstract adjudication for the 231 conflict/ambiguous trials, with verbatim supporting quotes; the 413 pipeline=registry agreements were retained.
3. **Human review** of the residual unresolved cases.

## Results

- Pipeline arm labels concordant for **98% of verifiable arms (1,383 / 1,413)**.
- On the 181 contested arms, the abstract confirmed the **pipeline in 167 (92%)** — most apparent registry discrepancies were registry coding errors, not extraction errors.
- **2 mis-linked-protocol trials** (extracted content ≠ registered intervention) identified and excluded → **verified cohort of 642 protocols (1,462 arms)**.
- Full `02`–`08` re-analysis on the verified cohort: median 12-month TT 18.0, intensity 1.50 d/mo, 67% identical scheduling, and subgroup ordering all **unchanged** vs the original (see `HEADLINE_COMPARISON.md`).

## Reproducibility

All CT.gov / PubMed responses are cached; every step is scripted; audit tables and a full methodology log are included. Re-runnable offline from cache.

## Not included in this PR (intentionally)

- The updated methods-paper `.tex` (submitted separately to arXiv).
- Private/source materials kept out of the repo: co-author review comments, correspondence, and the raw source dataset (consistent with the existing `.gitignore`).

## Test plan

- `02`–`08` re-run cleanly in the vendored verified folder.
- `tables/headline_comparison.csv` shows parity between the original and verified cohorts.
- Spot-checked corrections against CT.gov + abstracts (e.g., NeoALTTO trastuzumab → control).
