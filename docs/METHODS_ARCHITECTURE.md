# TimeTox: Automated Extraction of Healthcare Contact Days from Clinical Trial Protocols

## Methods

### Overview

We developed TimeTox, an automated pipeline for quantifying cumulative healthcare contact days ("time toxicity") from clinical trial protocol documents. The system processes full protocol PDFs obtained from ClinicalTrials.gov (via NCT identifiers) through a multi-stage large language model (LLM) architecture (Figure 1).

### Pipeline Architecture

The pipeline consists of two main components operating in sequence:

#### Component 1: Schedule of Activities Detection

The first component receives the complete clinical trial protocol PDF and identifies pages containing the Schedule of Activities (SoA), also known as the Schedule of Events or Time and Events Table. This LLM-based detector:

1. **Locates the SoA table(s)** within the multi-page protocol document
2. **Extracts protocol metadata** relevant to downstream extraction, including:
   - Disease indication
   - Treatment arms and intervention types
   - Overall treatment duration
   - Study phase and design characteristics
3. **Outputs a focused document** containing only the SoA pages and associated metadata

This filtering step reduces noise from unrelated protocol sections (e.g., statistical considerations, regulatory language) and enables more accurate downstream extraction.

#### Component 2: Two-Stage Healthcare Contact Day Extraction

The focused SoA document is then processed by a two-stage LLM extraction pipeline:

**Stage 1: Structure Extraction**

The first LLM call parses the SoA document to extract structural parameters that define the visit schedule:

- **Cycle structure**: Length of treatment cycles (e.g., 21 or 28 days)
- **Visit pattern per cycle**: Days within each cycle requiring healthcare contact (e.g., Days 1, 8, 15)
- **Treatment duration**: Total planned treatment period in months
- **Arm-specific schedules**: Differential visit requirements for experimental versus control arms
- **Special visits**: Screening visits, end-of-treatment assessments, and follow-up appointments

Output: A structured JSON representation of protocol parameters.

**Stage 2: Visit Count Extraction**

The second LLM call receives both the original SoA document and the structured output from Stage 1. Given explicit calculation rules in the prompt (e.g., cycle-to-calendar-day mapping, cumulative counting logic), the model extracts:

1. Total treatment cycles based on duration and cycle length
2. Calendar days requiring healthcare contact across all cycles
3. Cumulative visit counts at predefined time windows
4. Special visit contributions (screening, end-of-treatment, follow-up)

Output: Cumulative healthcare contact days per treatment arm at standardized intervals (screening, 1 month, 3 months, 6 months, 9 months, 12 months).

### Rationale for Two-Stage Design

Decomposing extraction into structure parsing and visit counting provides several advantages:

1. **Separation of concerns**: Stage 1 focuses on document comprehension and structure identification; Stage 2 focuses on applying that structure to count visits
2. **Auditability**: Intermediate structural output enables human verification of extracted parameters
3. **Error localization**: Failures can be attributed to either structure extraction or visit counting
4. **Consistency**: Providing the extracted structure as context to Stage 2 ensures the model applies consistent parameters across all time windows

### Definition of Healthcare Contact Day

A healthcare contact day is defined as any calendar day requiring physical interaction with the healthcare system, including clinic visits, laboratory assessments, imaging studies, infusions, and procedures. Multiple assessments occurring on the same calendar day count as a single healthcare contact day.

### Time Windows

Healthcare contact days are reported cumulatively at six standardized intervals:

| Window | Definition |
|--------|------------|
| Screening | All pre-treatment visits prior to Day 1 |
| 1 month | Screening + Day 1 through Day 30 |
| 3 months | Screening + Day 1 through Day 90 |
| 6 months | Screening + Day 1 through Day 180 |
| 9 months | Screening + Day 1 through Day 270 |
| 12 months | Screening + Day 1 through Day 365 |

### Implementation

The pipeline was implemented using Google's Gemini 3 Flash model with temperature set to 0.1 for reproducibility. Each extraction stage includes retry logic with exponential backoff to handle API rate limits.

---

## Figure 1: TimeTox Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    INPUT: Full Protocol PDF (via NCT ID)                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│              COMPONENT 1: SCHEDULE OF ACTIVITIES DETECTION (LLM)            │
│                                                                             │
│   • Identify SoA table pages within full protocol                           │
│   • Extract protocol metadata (disease, arms, duration)                     │
│   • Filter to relevant content for downstream processing                    │
│                                                                             │
│   Output: Focused SoA document + metadata                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│              COMPONENT 2: TWO-STAGE TIMETOX EXTRACTION                      │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  STAGE 1: STRUCTURE EXTRACTION (LLM)                                  │  │
│  │                                                                       │  │
│  │  • Parse cycle length and visit days per cycle                        │  │
│  │  • Identify treatment duration                                        │  │
│  │  • Capture arm-specific visit patterns                                │  │
│  │  • Note screening, EOT, and follow-up visits                          │  │
│  │                                                                       │  │
│  │  Output: Structured JSON with protocol parameters                     │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                      │                                      │
│                                      ▼                                      │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  STAGE 2: VISIT COUNT EXTRACTION (LLM)                                │  │
│  │                                                                       │  │
│  │  Input: SoA document + Stage 1 structure + calculation rules          │  │
│  │                                                                       │  │
│  │  • Extract total cycles from duration and cycle length                │  │
│  │  • Map visit pattern to calendar days                                 │  │
│  │  • Count cumulative visits per time window                            │  │
│  │  • Add special visits at appropriate intervals                        │  │
│  │                                                                       │  │
│  │  Output: Healthcare contact days per arm per time window              │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                               OUTPUT                                        │
│                                                                             │
│   Per-arm cumulative healthcare contact days at:                            │
│   screening, 1 month, 3 months, 6 months, 9 months, 12 months              │
│                                                                             │
│   Example:                                                                  │
│   Arm A (Experimental): 2, 5, 11, 21, 32, 40 days                          │
│   Arm B (Control):      2, 4,  9, 17, 25, 32 days                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Validation

The pipeline was validated on a set of 20 synthetic Schedule of Assessments documents with known ground truth values spanning simple (single-arm, standard dosing), moderate (two-arm, minor differences), and complex (two-arm with different visit schedules, loading doses, multiple phases) trial designs.

### Performance Metrics

| Metric | Definition |
|--------|------------|
| Exact Match Accuracy | Percentage of extracted values matching ground truth exactly |
| Clinical Accuracy | Percentage of values within ±3 days of ground truth |
| Mean Absolute Error (MAE) | Average absolute difference from ground truth in days |


