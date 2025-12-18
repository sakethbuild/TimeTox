# Split Window Experiments Summary

## Overview

Two split window approaches have been tested for extracting healthcare contact days from clinical trial Schedule of Assessments (SoA) documents.

---

## Approach 1: Independent Split Windows

**Location:** `experiments/agent_comparison.py` (function `agent_split_windows`)

**Architecture:**
```
PDF → Early Windows (screening, 1m, 3m) → 
PDF → Late Windows (6m, 9m, 12m) →
Merge Results
```

**Method:**
- Two independent Gemini calls
- Each call extracts its subset of windows without context from the other
- Results merged by matching arm names

**Results (5 PDFs, 60 comparisons):**

| Metric | Value |
|--------|-------|
| Exact Match Accuracy | **51.7%** |
| Clinical Accuracy (±3 days) | **90.0%** |
| Mean Absolute Error | **1.23 days** |
| API Calls | 10 (2 per PDF) |

**This was the BEST performing approach** in the multi-agent comparison.

---

## Approach 2: Chained Split Windows (Context Passing)

**Location:** `experiments/split_window/chained_split_window.py`

**Architecture:**
```
PDF → First Window (up to 3m) → [extract structure + counts]
PDF + First Output → Second Window (6m-12m) → [with context from first]
Merge Results
```

**Method:**
- First call: Extract early windows (screening, 1_month, 3_months)
- Second call: Pass PDF + first call output as context, extract late windows
- Hypothesis: Providing first output helps maintain consistency (arm names, cycle lengths)

**Results (5 PDFs, 60 comparisons):**

| Metric | Value |
|--------|-------|
| Exact Match Accuracy | **33.3%** |
| Clinical Accuracy (±3 days) | **90.0%** |
| Mean Absolute Error | **1.67 days** |
| API Calls | 10 (2 per PDF) |

**Per-Window Performance:**

| Window | Exact | ±3 Days |
|--------|-------|---------|
| screening | 40% | 100% |
| 1_month | **100%** | 100% |
| 3_months | 60% | 100% |
| 6_months | 0% | 80% |
| 9_months | 0% | 80% |
| 12_months | 0% | 80% |

**Issue:** Late windows (6m+) have 0% exact accuracy despite having context.

---

## Comparison

| Approach | Exact Acc | Clinical Acc | MAE | Notes |
|----------|-----------|--------------|-----|-------|
| Independent Split | **51.7%** | 90.0% | **1.23** | Best overall |
| Chained Split | 33.3% | 90.0% | 1.67 | Context passing hurt accuracy |
| Baseline (single call) | 43.3% | 88.3% | 1.67 | Reference |

---

## Key Findings

1. **Independent calls outperform chained calls** - Passing the first output as context to the second call actually decreased accuracy

2. **Early windows benefit from chaining** - 1_month achieved 100% exact accuracy in chained approach

3. **Late windows suffer in chained approach** - 0% exact accuracy for 6/9/12 months suggests the context may be confusing the model

4. **Clinical accuracy is preserved** - Both approaches achieve 90% ±3 day accuracy

---

## Possible Explanations

1. **Context pollution**: The first output may anchor the second call to incorrect assumptions
2. **Cumulative error**: Errors in first window structure interpretation propagate to late windows
3. **Redundant information**: The PDF already contains all the structure; adding extracted text may create conflicts

---

## Files

- `experiments/agent_comparison.py` - Original independent split windows
- `experiments/split_window/chained_split_window.py` - Chained split window experiment
- `results/agent_comparison_results.json` - Original comparison results
- `results/chained_split_window_results_2025-12-18_132843.json` - Chained results

---

## Recommendation

**Use the independent split window approach** (`agent_split_windows` in `agent_comparison.py`) as it achieved the best exact accuracy (51.7%) while maintaining high clinical accuracy (90%).

The chained/context-passing approach does not improve results and may actually hurt late window extraction.

