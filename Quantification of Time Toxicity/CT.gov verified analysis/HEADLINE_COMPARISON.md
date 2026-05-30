# Headline Comparison — Original vs CT.gov+PubMed-Corrected

|                        | ORIGINAL (644)   | CORRECTED (642)   | SENSITIVITY (excl 25 flagged → 617)   |
|:-----------------------|:-----------------|:------------------|:--------------------------------------|
| n_trials               | 644              | 642               | 617                                   |
| median_iv_TT           | 18.0 (14.0-28.0) | 18.0 (14.0-28.0)  | 18.0 (14.0-28.0)                      |
| median_ct_TT           | 18.0 (14.0-29.0) | 18.0 (14.0-30.0)  | 18.0 (14.0-30.0)                      |
| intensity_iv           | 1.50             | 1.50              | 1.50                                  |
| n_matched_pairs        | 638              | 642               | 617                                   |
| pct_identical_schedule | 67.6%            | 67.3%             | 67.9%                                 |
| median_delta_nonzero   | 2.0              | 2.0               | 2.0                                   |
| pct_gt30d              | 22.4%            | 22.1%             | 21.7%                                 |
| med_CNS                | 41.0 (n=13)      | 41.0 (n=13)       | 45.5 (n=12)                           |
| med_Breast             | 16.0 (n=99)      | 16.0 (n=98)       | 16.0 (n=93)                           |
| med_Chemotherapy       | 32.0 (n=84)      | 31.0 (n=83)       | 29.5 (n=78)                           |
| med_Immunotherapy      | 21.0 (n=137)     | 21.0 (n=137)      | 21.0 (n=130)                          |
| med_Targeted Therapy   | 19.0 (n=283)     | 19.0 (n=283)      | 19.0 (n=276)                          |

**Sensitivity** excludes trials whose labels came from human review or pipeline fallback (25 trials), retaining only pipeline=CT.gov agreement + PubMed-confident labels.

## Interpretation
The corrected cohort excludes 2 mis-linked-protocol trials (644→642). Differences between ORIGINAL and CORRECTED reflect the ~30 arm-label corrections; because the pipeline was right 92% of the time it disagreed with CT.gov, headline medians move minimally.