# Stage2_Bestperformer: Two-Stage LLM Pipeline

**100% Clinical Accuracy (±3 days) on 20 Synthetic Schedules**

## Overview

This is the best-performing pipeline for extracting "time-toxic days" (healthcare contact days) from clinical trial Schedules of Assessments (SoA).

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PDF Schedule of Assessments              │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  STAGE 1: Structure Extraction                              │
│  ─────────────────────────────                              │
│  • Extract cycle length, visit days, treatment duration     │
│  • Parse legend for arm-specific patterns                   │
│  • Identify screening days, EOT, follow-up visits           │
│  • Output: Structured JSON                                  │
│  • Forced JSON output via response_mime_type                │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  STAGE 2: Visit Count Calculation                           │
│  ────────────────────────────────                           │
│  • Input: Stage 1 structure + PDF (for verification)        │
│  • Calculate cumulative visits per time window              │
│  • Apply cycle-to-calendar mapping                          │
│  • Add special visits (EOT, follow-ups)                     │
│  • Output: Healthcare contact days per arm per window       │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  OUTPUT                                                     │
│  ──────                                                     │
│  {                                                          │
│    "Arm A": { "screening": 2, "1_month": 5, ... },         │
│    "Arm B": { "screening": 2, "1_month": 3, ... }          │
│  }                                                          │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Two Stages, Not Three
Originally tested a 3-stage pipeline with a "judge" to validate results. Found that:
- Stage 2 implicitly acts as a judge (has PDF + structure)
- Explicit Stage 3 judge actually *decreased* accuracy
- Simpler is better

### 2. Forced JSON Output
Using `response_mime_type = "application/json"` instead of just asking for JSON in the prompt:
- Guarantees valid JSON (no markdown code blocks)
- More reliable parsing
- Cleaner output

### 3. Robust Arm Matching
Fixed a bug where treatment names containing 'B' (e.g., "Bevacizumab") were misclassified:
```python
# Wrong: if 'A' in name and 'B' not in name
# Correct: if 'Arm A' in name and 'Arm B' not in name
```

### 4. Screening Days Clarification
Added explicit prompt instruction to prevent confusion:
```
screening_days is the NUMBER OF SCREENING VISIT DAYS (typically 1-2), 
NOT the cycle length. Even if cycle_length_days is 7, screening_days 
is still typically 1 or 2.
```

## Performance

| Metric | Value |
|--------|-------|
| **Clinical Accuracy (±3 days)** | **100.0%** |
| Exact Match Accuracy | 29.2% |
| Mean Absolute Error | 0.81 days |
| Schedules Tested | 20 |
| Total Comparisons | 240 |

### By Cycle Length

| Cycle | Schedules | Clinical Accuracy |
|-------|-----------|-------------------|
| 7-day | 5 | 100% |
| 21-day | 3 | 100% |
| 28-day | 11 | 100% |
| 35-day | 1 | 100% |

## Usage

```bash
# Run on all 20 schedules
python3 Stage2_Bestperformer/pipeline.py 20

# Run on first 5 schedules
python3 Stage2_Bestperformer/pipeline.py 5

# Run on single schedule
python3 Stage2_Bestperformer/pipeline.py 1
```

## Requirements

- Python 3.8+
- `google-genai` (Gemini API)
- `python-dotenv`
- Valid `GEMINI_API_KEY` in `.env` file

## Files

- `pipeline.py` - Main pipeline implementation
- `README.md` - This file

## Output Format

Results are saved as JSON with:
- Per-schedule extracted values and metrics
- Summary statistics
- Structure information from Stage 1
- Calculation breakdowns from Stage 2

## Citation

If you use this pipeline, please cite the TimeTox project.

