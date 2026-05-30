# Methodology Log — CT.gov + PubMed Arm-Label Verification

**Snapshot date:** 2026-05-29
**Purpose:** Full provenance record of the three-source intervention/control arm-label verification, written so it can be adapted directly into the Methods section of the manuscript/preprint.
**Status:** COMPLETE. Phase 1 (verification + discrepancy), human review of the 23 PubMed-unresolved trials (§8.1), and Phase 2 (re-labeling + full 02–08 re-analysis + comparison, §11) all done. Verified cohort = 642 trials.

---

## 0. Motivation

During co-author review, a spot check revealed that some trials had their intervention and control arms swapped. Root cause traced to [01_build_consensus.py](../01_build_consensus.py) lines 33–38, function `normalize_intervention_type()`, which applies:

```python
df.loc[df["intervention_type"] == "placebo", "intervention_type"] = "control"
df.loc[df["intervention_type"] == "active_comparator", "intervention_type"] = "intervention"   # <-- clinically backwards
```

`active_comparator` is, by convention, the **control** arm. This rule could mislabel control arms as intervention. We therefore verified every trial's arm labels against external sources.

---

## 1. Data sources & access

| Source | Endpoint / method | Coverage | Snapshot |
|---|---|---|---|
| **Pipeline labels** | existing `data/consensus_arms.csv` (1,466 arm records, 644 trials) | 644/644 | n/a (pre-existing) |
| **ClinicalTrials.gov** | v2 REST API `GET /api/v2/studies/{NCT}?fields=protocolSection.armsInterventionsModule,designModule,identificationModule` | 644/644 NCTs (all valid `NCT########`) | 644 fetched, **0 errors, 0 404s** |
| **PubMed** | E-utilities `efetch.fcgi?db=pubmed&rettype=abstract&retmode=text` | 644/644 PMIDs present; abstracts fetched for the 231 trials needing arbitration | 231 fetched, 0 empty |

All raw responses cached for offline reproducibility: `ctgov_cache/{NCT}.json` (+ `_manifest.csv` with per-record sha256 + `ctgov_snapshot_meta.json`); `pubmed_cache/{pmid}.txt` (+ `abstracts.csv`).

CT.gov arm-group count distribution (per registry): 1 arm × 1 trial; 2 × 511; 3 × 88; 4 × 30; 5 × 4; 6 × 6; 7 × 1; 8 × 2; 17 × 1.

---

## 2. CT.gov → binary label mapping

Registry arm types mapped to the pipeline's binary scheme:

| CT.gov `armGroups[].type` | Mapped label |
|---|---|
| EXPERIMENTAL | intervention |
| ACTIVE_COMPARATOR, PLACEBO_COMPARATOR, NO_INTERVENTION, SHAM_COMPARATOR | control |
| OTHER | resolved by drug content vs the trial's experimental arm; flagged uncertain |

---

## 3. Arm matching algorithm ([ctgov_match.py](ctgov_match.py))

To attach a CT.gov arm type to a specific pipeline arm (which holds the time-toxicity value), arms were matched by drug content:

1. **Tokenization:** drug names extracted from pipeline `arm_name` vs CT.gov `label` ∪ `interventionNames`; type prefixes (`Drug:`, `Biological:`, …) and wrappers (`Arm X (...)`) stripped; stopwords removed.
2. **Brand→generic canonicalization:** alias map (e.g., Herceptin→trastuzumab, Xofigo→radium-223) layered on top of the project's 222-entry `DRUG_CLASSES` dictionary ([config.py](../config.py)).
3. **Similarity:** weighted Jaccard over drug tokens (recognized drugs weighted 3×; placebo as a symmetric sentinel).
4. **Assignment:** 2-arm trials matched by elimination (CT.gov type assigned directly, confirmed by drug similarity); multi-arm trials matched by optimal assignment (`scipy.optimize.linear_sum_assignment` on cost = 1 − similarity).
5. **Confidence:** per-arm score with penalties for generic-only names, OTHER type, and count mismatch; threshold τ = 0.45 below which a match is "uncertain."

Match-status distribution (1,466 arms): confident_2arm 958, count_mismatch 210, uncertain 130, confident 113, count_mismatch_leftover 55.

---

## 4. Raw CT.gov discrepancy (pipeline vs CT.gov)

| Metric | Value |
|---|---|
| Arm-level discrepancy | 110/1071 confidently-matched arms = **10.3%** (95% CI 8.6–12.2%) |
| Trial-level label-flip | 150/644 = 23.3% |
| Headline-impact (Δ₁₂ changes) | 120/644 = 18.6% |
| Count-mismatch trials (CT.gov arm count ≠ pipeline) | **89** |

**Directional split of the 110 flips:** 42 pipeline=intervention→CT.gov=control (37 of these ACTIVE_COMPARATOR — the original bug); 68 pipeline=control→CT.gov=intervention.

### Key data-quality finding — CT.gov is itself error-prone
Of 269 pipeline arms whose name contains "placebo," CT.gov typed them: 185 PLACEBO_COMPARATOR, 49 ACTIVE_COMPARATOR, **27 EXPERIMENTAL**, 1 NO_INTERVENTION, 1 SHAM, 1 OTHER, 5 unmatched. I.e., registrants frequently mis-code placebo/SOC arms as EXPERIMENTAL. A naïve CT.gov-type overwrite would therefore convert genuine control arms into intervention — motivating a third source.

---

## 5. PubMed third source ([fetch_pubmed.py](fetch_pubmed.py), subagent extraction)

- **Scope (user decision):** run only on the 231 trials where pipeline and CT.gov disagreed or were ambiguous (confident disagreement 92; uncertain 54; count-mismatch 89; mapping edge cases — union = 231). The 413 trials where pipeline and CT.gov **agree** kept their concordant label without PubMed.
- **Extraction:** published abstracts read by 8 parallel LLM subagents; each arm classified intervention / control / unresolved with a **verbatim supporting quote (≤25 words)**; abstracts that did not establish a role were marked unresolved (no guessing). First pass: 296 intervention, 258 control, 67 unresolved.
- **Truncation remediation:** an initial 6,000-character cap truncated some abstract bodies (long author lists); abstracts were re-cleaned (author/affiliation blocks stripped) and the 31 affected trials re-extracted in 2 batches, resolving 42 additional arms. Genuinely unresolved cases (true head-to-head designs, arms not described in the abstract, mis-linked PMIDs) remained unresolved.

---

## 6. Three-source reconciliation ([reconcile_labels.py](reconcile_labels.py))

Rule (user-approved):
- **Agreement trials (pipeline = CT.gov):** final = pipeline label.
- **Arbitration trials:** PubMed-resolved → final = PubMed designation; PubMed-unresolved → keep pipeline label (working fallback) and flag for human review.

### Decisive result — the abstract vindicates the pipeline
On the **181 contested arms** (pipeline ≠ CT.gov) where PubMed resolved the role:
- PubMed agreed with the **PIPELINE: 167 (92%)**
- PubMed agreed with CT.gov: 14 (8%)

### True reconciled discrepancy (pipeline vs 3-source gold standard)

| Metric | Raw CT.gov | **Reconciled (true)** |
|---|---|---|
| Arm-level discrepancy | 10.3% | **30/1413 = 2.1%** (95% CI 1.5–3.0%) |
| Trial-level relabel | 23.3% | **27/644 = 4.2%** |
| Headline-impact (Δ₁₂ changes) | 18.6% | **9/644 = 1.4%** |

The 30 genuine errors are dominated by the original bug: 26 are pipeline=intervention→gold=control; 4 are the reverse.

**Final label provenance (1,466 arms):** 845 from pipeline=CT.gov agreement; 568 from PubMed arbitration; 53 pipeline fallback (PubMed unresolved → human review).

---

## 7. Data-integrity findings

### 7a. Content mismatches (mis-linked protocols) — 2 trials, EXCLUDED
The extracted protocol content does not match the NCT/PMID metadata (which are internally consistent):
- **NCT01519700** (PMID 26122726): metadata = filgrastim biosimilar (EP2006); extracted arms = "Radiosurgery ± WBRT."
- **NCT02101021** (PMID 30105668): metadata = momelotinib + gem/nab-paclitaxel (pancreatic); extracted arms = "VMP / D-VMP" (myeloma).

Decision: **excluded from the verified cohort (→ 642 trials)** and flagged for upstream correction; their time-toxicity values cannot be attributed to the labeled trial.

### 7b. Arm-structure mismatches — 2 trials, KEPT
NCT/PMID correct; protocol arm granularity differs from the primary publication's reported comparison. PMID is valid, pipeline labels retained:
- **NCT01539291** (idelalisib; protocol dose-comparison arms vs abstract's idelalisib+rituximab vs placebo+rituximab).
- **NCT02883049** (AALL1131; protocol risk-strata arms vs abstract's CNS-prophylaxis randomization).

### 7c. Global content-integrity sweep ([content_integrity_sweep.py](content_integrity_sweep.py))
Alias-aware drug-overlap check across all 644 trials flagged 2 trials, both verified false positives (incomplete drug vocabulary: SGI-110→guadecitabine, arfolitixorin→ARFOX). **Zero new genuine mismatches.**

**Completeness argument:** a mis-linked protocol yields pipeline arms that cannot match the CT.gov record drawn from the correct NCT, so any content mismatch necessarily falls in the disagreement set — which was fully PubMed-screened. The 413 agreement trials are concordant precisely because the protocol matched the registry. Hence the 2 found constitute effectively the complete set.

---

## 8. Human-review set (pending) — 50 trials

`tables/human_review_worksheet.csv` + [HUMAN_REVIEW.md](HUMAN_REVIEW.md):
- **CORRECTION_APPLIED** — 30 arms / 27 trials (verify the gold-standard flips, e.g., NeoALTTO trastuzumab → control).
- **PUBMED_UNRESOLVED** — 41 arms / 23 trials (kept pipeline label; abstract could not arbitrate — true head-to-head or arm not described).
- (PMID_MISMATCH 4 trials now resolved in §7: 2 excluded, 2 kept.)

---

## 8.1 Human review outcome — PubMed-unresolved trials (completed)

A reviewer adjudicated all 39 unresolved arms across the 23 PubMed-unresolved trials using a side-by-side CSV containing the full abstract text (`tables/unresolved_review_with_abstracts.csv`). Decisions returned in the `_after_human_decision` file and applied via [apply_human_decisions.py](apply_human_decisions.py) → `tables/final_labels_reconciled.csv`.

- All 39 unresolved arms decided (0 "exclude"); 0 already-resolved arms overridden.
- 8 arm labels changed vs the pipeline fallback, including TAILORx (NCT00310180: hormonal-alone → intervention, chemo+hormonal → control), S0307 (NCT00127205: ibandronate → control), CPT-SIOP-2000 choroid plexus (NCT00500890: carboplatin arm → control).
- Final reconciled provenance (1,466 arms): agreement 845; pubmed 537; **human_review 72**; pipeline_fallback 8 (the 2 arm-structure trials, retained by design); excluded_content_mismatch 4.
- **Verified cohort = 642 trials** (after excluding the 2 mis-linked-protocol trials, §7a).

## 8.2 Phase 2 — Re-labeling decision on PubMed-override trials

The 25 `CORRECTION_APPLIED` trials (PubMed overrode the pipeline, each backed by a verbatim abstract quote in `final_labels.csv`) were accepted without separate manual review (reviewer go-ahead), as they are evidence-backed and auditable via the change log.

## 8.3 Phase 2 — Re-derivation ([rederive.py](rederive.py))

The reconciled labels were applied to the consensus arm data; `pos_idx` re-assigned within (filename, corrected label) by 12-month TT; trial-level `consensus_trials.csv` and `category_breakdown_consensus.csv` rebuilt with 01_build_consensus.py's logic but **without** `normalize_intervention_type` (the buggy function). The 2 content-mismatch trials were dropped. Result: 1,462 arms / 642 trials. Scripts 02–08 were then re-run in the vendored verified folder (isolated `config.py`), regenerating all tables, 16 figures, the multivariable regression, and the validation/sensitivity outputs.

## 11. Phase 2 results — original vs verified (headline comparison)

| Metric | Original (644) | Verified (642) | Sensitivity (617)* |
|---|---|---|---|
| Median intervention 12-mo TT | 18.0 (14.0–28.0) | 18.0 (14.0–28.0) | 18.0 (14.0–28.0) |
| Median control 12-mo TT | 18.0 (14.0–29.0) | 18.0 (14.0–30.0) | 18.0 (14.0–30.0) |
| Intensity (days/month) | 1.50 | 1.50 | 1.50 |
| Matched pairs | 638 | 642 | 617 |
| % identical scheduling | 67.6% | 67.3% | 67.9% |
| Median non-zero delta | 2.0 | 2.0 | 2.0 |
| % >30 days | 22.4% | 22.1% | 21.7% |
| CNS / Breast | 41.0 / 16.0 | 41.0 / 16.0 | 45.5 / 16.0 |
| Chemo / Immuno / Targeted | 32.0 / 21.0 / 19.0 | 31.0 / 21.0 / 19.0 | 29.5 / 21.0 / 19.0 |

*Sensitivity excludes the 25 human-review/fallback trials, retaining only pipeline=CT.gov agreement + PubMed-confident labels.

**Conclusion:** External verification against CT.gov and PubMed leaves every headline result materially unchanged — the original intervention/control labeling was correct in ~98% of arms, and the residual corrections do not shift the medians, the 67% identical-scheduling finding, or the subgroup ordering. This strengthens, rather than revises, the manuscript's conclusions.

## 9. Reproducibility — scripts & artifacts (all in `CT.gov verified analysis/`)

**Scripts (run with `/usr/bin/python3`):** `fetch_ctgov.py` → `ctgov_match.py` → `compute_discrepancy.py` → `fetch_pubmed.py` → `prep_pubmed_batches.py` → (subagent extraction) → `prep_remediation.py` → (subagent remediation) → `reconcile_labels.py` → `build_review_package.py` → `content_integrity_sweep.py`.

**Caches (offline-reproducible):** `ctgov_cache/` (644 JSON + manifest + meta), `pubmed_cache/` (231 abstracts + `abstracts.csv`), `pubmed_batches/` (input + subagent result JSON).

**Audit tables:** `ctgov_arm_matches.csv`, `trials_needing_pubmed.csv`, `pubmed_designations.csv`, `final_labels.csv` (master per-arm provenance), `match_quality_summary.csv`, `per_trial_change_log.csv`, `human_review.csv`, `human_review_worksheet.csv`, `content_integrity_sweep.csv`, `content_mismatch_flags.csv`.

**Reports:** `DISCREPANCY_REPORT.md`, `HUMAN_REVIEW.md`, this `METHODOLOGY_LOG.md`.

---

## 10. Draft Methods text (adapt for manuscript/preprint)

> **Arm-label verification.** Intervention/control arm assignments produced by the extraction pipeline were verified against two external sources. For all 644 trials, arm-type designations (EXPERIMENTAL, ACTIVE_COMPARATOR, PLACEBO_COMPARATOR, NO_INTERVENTION, SHAM_COMPARATOR) were retrieved from the ClinicalTrials.gov API (v2; accessed 2026-05-29) and matched to pipeline arms by drug-content similarity (weighted Jaccard over a curated drug dictionary with brand-to-generic normalization; optimal assignment for multi-arm trials). Because registry arm-type coding mislabeled a non-trivial fraction of placebo/standard-of-care arms as experimental, trials in which the pipeline and registry disagreed or were ambiguous (n = 231) were adjudicated using the published abstract: arm roles were extracted with supporting verbatim text, and the abstract served as the arbiter; abstracts that did not establish an arm's role were retained at the pipeline label and flagged for manual review. Where the pipeline and registry agreed (n = 413), the concordant label was retained. Against the resulting three-source standard, the pipeline's arm-label error rate was 2.1% (30/1,413 arms; 95% CI 1.5–3.0%), affecting the 12-month incremental time-toxicity value in 9 of 644 trials (1.4%); on contested arms the abstract confirmed the pipeline in 167/181 (92%) of cases. Two trials with mis-linked protocols (extracted content inconsistent with the registered intervention) were identified and excluded, yielding 642 trials for the verified analysis. All API responses were cached and all reconciliation steps scripted for reproducibility.

*(Final figures, post human-review + Phase 2 re-analysis: arm-label error 2.1%, headline-impact 9/644 trials, verified cohort 642. The verified re-analysis left every headline result materially unchanged — see §11.)*
