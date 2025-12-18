# Session Log - December 18, 2025

## Overview

This session focused on implementing and evaluating multiple extraction pipeline architectures for the TimeTox project, which extracts "time-toxic days" (healthcare contact days) from clinical trial Schedule of Assessments (SoA) documents.

---

## Experiments Conducted

### 1. Multi-Agent Prompt Optimization Comparison

Implemented and tested 5 different extraction strategies:

| Agent | Architecture | Exact Accuracy | Clinical Accuracy (±3 days) | MAE | API Calls |
|-------|-------------|----------------|----------------------------|-----|-----------|
| **Baseline** | Single-pass standard prompt | 43.3% | 88.3% | 1.67 | 5 |
| **Split Windows** | Early + Late window separation | **51.7%** | **90.0%** | **1.23** | 10 |
| **Probabilistic** | Multi-sample (n=5) median aggregation | 25.0% | 90.0% | 1.73 | 25 |
| **Chain-of-Thought** | Explicit cycle enumeration | 21.7% | 71.7% | 3.68 | 5 |
| **Bidirectional** | Forward + Backward reconciliation | 25.0% | 90.0% | 1.47 | 10 |

**Key Finding**: Split Windows approach achieved the best exact accuracy (51.7%) with good clinical accuracy (90.0%) at modest API cost (2 calls per PDF).

### 2. Three-Stage Pipeline with Judge

Implemented a multi-stage architecture:

1. **Stage 1**: Structure extraction (legend, cycle info)
2. **Stage 2**: Calculate visit counts using extracted structure
3. **Stage 3**: Judge validates and corrects if needed (with PDF access)

Location: `core/pipeline_with_judge.py`

### 3. Temperature Sweep Experiments

Tested extraction across temperature range 0.0-0.5:

- Lower temperatures (0.0-0.2): More consistent but potentially less accurate
- Higher temperatures (0.3-0.5): More variance but sometimes better on specific windows
- **Optimal range**: 0.1-0.2 for balanced accuracy/consistency

### 4. Performance Optimization

Implemented parallelization for temperature sweeps:
- Before: ~250-300 seconds (4-5 minutes) sequential
- After: ~35-55 seconds (<1 minute) with ThreadPoolExecutor
- **Speedup**: 5-8x faster

Location: `experiments/temp_sweep_varied_optimized.py`

---

## Pipeline Architectures Tested

### Architecture 1: Vanilla Extraction (`core/test_extraction.py`)
```
PDF → Single Gemini Call → Structured JSON Output
```
- Simple, single-pass approach
- Comprehensive prompt with definitions and examples
- Good baseline for comparison

### Architecture 2: Split Windows (`experiments/agent_comparison.py`)
```
PDF → Early Windows (screening, 1m, 3m) → 
PDF → Late Windows (6m, 9m, 12m) →
Merge Results
```
- Reduces cognitive load per call
- Best exact accuracy achieved

### Architecture 3: Multi-Stage with Judge (`core/pipeline_with_judge.py`)
```
PDF → Stage 1 (Extract Structure) →
Stage 2 (Calculate from Structure) →
Stage 3 (Judge Validates with PDF) →
Final Results
```
- Most sophisticated approach
- Judge can correct errors with original PDF access

### Architecture 4: Probabilistic Aggregation
```
PDF → N Samples (temp=0.4) → Statistical Aggregation (median, IQR)
```
- Trades accuracy for robustness
- Useful for confidence estimation

---

## Files Created/Modified

### New Files
- `experiments/agent_comparison.py` - Multi-agent comparison framework
- `experiments/temp_sweep*.py` - Temperature sweep experiments
- `experiments/analyze_temp_sweep.py` - Results analysis
- `experiments/stage1_only_comparison.py` - Stage 1 baseline
- `core/pipeline_with_judge.py` - Three-stage pipeline

### Results Generated
- `results/agent_comparison_results.json` - Comparison metrics
- `results/temp_sweep_*.json` - Temperature sweep results
- `results/validation_report.md` - Extraction validation

---

## Technical Notes

### Model Used
- **gemini-3-flash-preview** (Gemini 3 Flash with advanced reasoning)

### Key Prompt Optimizations
1. Emphasize LEGEND section - contains authoritative visit patterns
2. Explicit cycle-to-day mapping instructions
3. Cumulative counting verification
4. Include all visit types (screening, treatment, EOT, follow-up)

### Ground Truth Dataset
- 20 synthetic Schedule of Assessments PDFs
- Varied complexity: 5 simple, 10 moderate, 5 complex
- All two-arm trials across multiple oncology disease types
- Known ground truth for validation

---

## Next Steps

See `TODO.md` for pending tasks.

