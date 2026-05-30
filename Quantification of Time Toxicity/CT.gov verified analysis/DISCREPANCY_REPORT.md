# CT.gov + PubMed Verification — Phase 1 Discrepancy Report

**Snapshot:** CT.gov v2 API (644 NCTs, 0 errors) + PubMed E-utilities (231 abstracts); raw JSON/text cached for reproducibility.

## What we did

Three independent signals for each arm's intervention/control role:
1. **Pipeline** — LLM-extracted label from the protocol Schedule of Assessments (existing data).
2. **CT.gov** — registrant arm-type (`EXPERIMENTAL` / `ACTIVE_COMPARATOR` / `PLACEBO_COMPARATOR` / etc.) for all 644 NCTs.
3. **PubMed** — LLM extraction of arm roles from the published abstract, run on the 231 trials where pipeline and CT.gov disagreed or were ambiguous (the other 413 already had two concordant sources).

PubMed arbitrates conflicts; unresolved cases go to a human-review file.

## Key finding: CT.gov alone is NOT a clean gold standard

On the **181 contested arms** (pipeline ≠ CT.gov), the published abstract sided with:
- **the PIPELINE: 167 (92%)**
- CT.gov: 14 (8%)

CT.gov frequently codes placebo / standard-of-care arms as `EXPERIMENTAL`. Blindly applying raw CT.gov type would have *introduced* ~167 new errors while fixing 14. The PubMed cross-check prevented this.

## Headline discrepancy numbers

| Metric | Raw CT.gov-based | **3-way reconciled (true)** |
|---|---|---|
| Arm-level discrepancy | 110/1071 = 10.3% | **30/1413 = 2.1%** (95% CI 1.5–3.0%) |
| Trial-level relabel rate | 23.3% | **27/644 = 4.2%** |
| Headline-impact (delta12 changes) | 18.6% | **9/644 = 1.4%** |

**The pipeline's true intervention/control error rate is ~2%, not ~10%.** The original `active_comparator → intervention` bug accounts for most of it (26 of 30 errors are pipeline=intervention → gold=control).

## Data-integrity counts

| Item | Count |
|---|---|
| Count-mismatch trials (CT.gov arm count ≠ pipeline) | **89** |
| Genuine pipeline label corrections (to apply) | 30 arms / 27 trials |
| PubMed-unresolved (head-to-head or arm not in abstract) | 41 arms / 23 trials |
| **Wrong-PMID trials** (dataset PMID → unrelated paper) | 12 arms / 4 trials |

## Human-review file

`tables/human_review.csv` — 83 arms / 52 trials, reason codes:
- `CORRECTION_APPLIED` (30 arms / 27 trials) — pipeline label overridden by PubMed gold; verify.
- `PUBMED_UNRESOLVED` (41 arms / 23 trials) — kept pipeline label as fallback; needs human eyes.
- `PMID_MISMATCH` (12 arms / 4 trials) — dataset PMID is wrong (e.g., arms say radiosurgery but the abstract is a filgrastim-biosimilar trial); find correct PMID or exclude.

## Final label provenance (1,466 arms)

- 845 from pipeline = CT.gov agreement
- 568 from PubMed arbitration
- 53 pipeline fallback (PubMed unresolved → human review)

## Impact preview

Only **9 trials** have a changed 12-month delta after correction. Because ~62% of trials have identical intervention/control TT (delta = 0) and the pipeline was right 92% of the time it disagreed with CT.gov, the headline medians and the 67.6% identical-scheduling figure are expected to move negligibly. Phase 2 will quantify this exactly.
