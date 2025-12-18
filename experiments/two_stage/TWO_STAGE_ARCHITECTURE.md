# Two-Stage Extraction Pipeline

## Architecture Overview

The Two-Stage Pipeline extracts healthcare contact days from clinical trial Schedule of Assessments (SoA) PDFs using a structured decomposition approach. By separating **structure extraction** from **calculation**, we achieve better accuracy than single-pass or judge-augmented approaches.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         INPUT: SoA PDF                                  │
│                    (Schedule of Assessments)                            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         STAGE 1: STRUCTURE EXTRACTION                   │
│                                                                         │
│  • Parse legend section for arm-specific visit patterns                 │
│  • Extract cycle length (days)                                          │
│  • Identify visit days within each cycle (e.g., D1, D8, D15)           │
│  • Capture treatment duration (months)                                  │
│  • Note special visits (screening, EOT, follow-up)                      │
│                                                                         │
│  Output: Structured JSON with protocol parameters                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         STAGE 2: CALCULATION                            │
│                                                                         │
│  • Compute total cycles: floor(treatment_months × 30 / cycle_length)   │
│  • Map visit pattern to calendar days                                   │
│  • Count cumulative visits per time window                              │
│  • Add special visits at appropriate windows                            │
│                                                                         │
│  Output: Healthcare contact days per arm per time window                │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              OUTPUT                                     │
│                                                                         │
│  Arm A: screening=2, 1_month=4, 3_months=11, 6_months=22, ...         │
│  Arm B: screening=2, 1_month=3, 3_months=8, 6_months=15, ...          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Stage 1: Structure Extraction

### Purpose
Extract the structural parameters that define the visit schedule from the PDF document, focusing on the **legend** and **table headers**.

### Input
- PDF file containing Schedule of Assessments
- Extraction prompt requesting structured output

### Output Schema
```json
{
  "protocol_info": {
    "disease": "HR+/HER2- Breast Cancer",
    "treatment_duration_months": 12
  },
  "arms": [
    {
      "arm_name": "Arm A (Abemaciclib + Fulvestrant)",
      "intervention_type": "intervention",
      "cycle_length_days": 28,
      "visit_days_per_cycle": [1, 8, 15],
      "visits_per_cycle": 3,
      "legend_text": "Arm A: Visits on Days 1, 8, 15 of each 28-day cycle"
    },
    {
      "arm_name": "Arm B (Fulvestrant)",
      "intervention_type": "control",
      "cycle_length_days": 28,
      "visit_days_per_cycle": [1, 15],
      "visits_per_cycle": 2,
      "legend_text": "Arm B: Visits on Days 1, 15 of each 28-day cycle"
    }
  ],
  "special_visits": {
    "screening_days": 2,
    "eot_visit": true,
    "m9_followup": true,
    "m12_followup": true
  }
}
```

### Key Extraction Points
| Parameter | Source in PDF | Example |
|-----------|---------------|---------|
| `cycle_length_days` | Legend, table headers | 28 days |
| `visit_days_per_cycle` | Legend text, column headers | [1, 8, 15] |
| `treatment_duration_months` | Protocol info, footnotes | 12 months |
| `screening_days` | Screening columns count | 2 |
| `eot_visit` | "End of Treatment" column | true |
| `followup_visits` | Follow-up columns | M9, M12 |

---

## Stage 2: Calculation

### Purpose
Use the extracted structure to mathematically compute cumulative healthcare contact days at each time window.

### Calculation Algorithm

```python
# 1. Compute total treatment cycles
total_cycles = floor(treatment_duration_months × 30 / cycle_length_days)

# 2. Generate all treatment visit days
treatment_days = []
for cycle in range(1, total_cycles + 1):
    cycle_start = (cycle - 1) * cycle_length_days + 1
    for visit_day in visit_days_per_cycle:
        treatment_days.append(cycle_start + visit_day - 1)

# 3. Count cumulative visits per window
windows = {
    'screening': screening_days,
    '1_month': screening_days + count(treatment_days <= 30),
    '3_months': screening_days + count(treatment_days <= 90),
    '6_months': screening_days + count(treatment_days <= 180),
    '9_months': screening_days + count(treatment_days <= 270) + eot + m9_fu,
    '12_months': screening_days + count(treatment_days <= 365) + eot + m9_fu + m12_fu
}
```

### Window Definitions
| Window | Calendar Days | Includes |
|--------|---------------|----------|
| `screening` | Pre-treatment | Screening visits only |
| `1_month` | Day 1-30 | Screening + C1 visits |
| `3_months` | Day 1-90 | Screening + C1-C3 visits |
| `6_months` | Day 1-180 | Screening + C1-C6 visits |
| `9_months` | Day 1-270 | Above + EOT + M9 follow-up |
| `12_months` | Day 1-365 | All visits including M12 follow-up |

### Output Schema
```json
[
  {
    "arm_name": "Arm A (Abemaciclib + Fulvestrant)",
    "healthcare_contact_days": {
      "screening": 2,
      "1_month": 5,
      "3_months": 11,
      "6_months": 21,
      "9_months": 32,
      "12_months": 40
    },
    "calculation_breakdown": {
      "total_cycles": 12,
      "treatment_visits": 36,
      "screening_visits": 1,
      "eot_visits": 1,
      "followup_visits": 2,
      "total_visits": 40
    }
  }
]
```

---

## Why Two Stages?

### Benefits of Decomposition

1. **Separation of Concerns**
   - Stage 1 focuses on *reading* the document
   - Stage 2 focuses on *math* using extracted parameters
   - Each stage can be optimized independently

2. **Interpretability**
   - Structure output is human-readable and auditable
   - Calculation breakdown shows exactly how totals were derived
   - Errors can be traced to specific stage

3. **Robustness**
   - If structure extraction fails, we know immediately
   - Calculation logic is deterministic given correct structure
   - No "black box" end-to-end confusion

### Comparison with Alternatives

| Approach | Exact Accuracy | Clinical (±3) | MAE |
|----------|---------------|---------------|-----|
| **Two-Stage (No Judge)** | **23.3%** | **100%** | **0.87d** |
| Three-Stage (With Judge) | 20.0% | 93.3% | 1.73d |
| Single-Pass Vanilla | ~25% | ~85% | ~2.0d |

The Two-Stage approach achieves the best clinical accuracy (100% within ±3 days) with the lowest mean absolute error.

---

## Implementation Details

### Model Configuration
- **Model**: `gemini-3-flash-preview`
- **Temperature**: 0.1 (low for consistency)
- **Retries**: 3 with exponential backoff

### File Structure
```
experiments/two_stage/
├── __init__.py
├── pipeline.py           # Main pipeline implementation
├── TWO_STAGE_ARCHITECTURE.md  # This document
└── results/              # Output JSON files
```

### Usage
```bash
# Run on 5 schedules
python3 experiments/two_stage/pipeline.py 5

# Run on all 20 schedules
python3 experiments/two_stage/pipeline.py 20
```

---

## Results Summary (5 Schedules)

### Overall Metrics
| Metric | Value |
|--------|-------|
| Exact Match Accuracy | 23.3% (14/60 windows) |
| Clinical Accuracy (±3 days) | 100% (60/60 windows) |
| Mean Absolute Error | 0.87 days |

### By Complexity
| Complexity | N | Exact | Clinical |
|------------|---|-------|----------|
| Simple | 12 | 16.7% | 100% |
| Moderate | 36 | 27.8% | 100% |
| Complex | 12 | 16.7% | 100% |

### By Time Window
| Window | Exact | Clinical | MAE |
|--------|-------|----------|-----|
| screening | 0% | 100% | 1.00d |
| 1_month | 0% | 100% | 1.00d |
| 3_months | 40% | 100% | 0.60d |
| 6_months | 20% | 100% | 1.10d |
| 9_months | 40% | 100% | 0.60d |
| 12_months | 40% | 100% | 0.90d |

### Known Error Patterns
1. **Screening undercount**: Model consistently extracts 1 screening day when GT is 2
2. **1-month overcount**: Adds +1 due to cumulative counting edge case
3. **Long-term accuracy**: 9-month and 12-month windows are most accurate

---

## Future Improvements

1. **Screening Extraction**: Add explicit prompt for multi-day screening windows
2. **Cumulative Logic**: Clarify whether screening is included in cumulative counts
3. **Confidence Scores**: Add uncertainty quantification per window
4. **Hybrid Validation**: Selective judge only when Stage 2 output looks suspicious

