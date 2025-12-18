# Synthetic Schedule of Assessments Generator

## Project Background

### Context
We are building a validation dataset for an LLM-based pipeline that extracts "time-toxic days" from phase 3 oncology clinical trial protocols. Time-toxic days represent any day a patient must physically interact with the healthcare system (clinic visits, labs, imaging, infusions, etc.).

### The Problem
Real clinical trial protocols contain ambiguous schedules that lead to inconsistent extraction. To validate our pipeline, we need synthetic schedules of assessments with KNOWN ground truth values.

### Goal
Generate 20 synthetic schedule-of-assessment PDFs that mimic real protocol formatting. Each synthetic schedule will have a documented ground truth for time-toxic days at standard intervals (screening, 1 month, 3 months, 6 months, 9 months, 12 months).

---

## What is a Schedule of Assessments?

A schedule of assessments (also called "schedule of events" or "time and events table") is a table embedded in clinical trial protocols that specifies:

- **Rows**: Assessment types (labs, imaging, physical exams, ECGs, questionnaires, drug administration, etc.)
- **Columns**: Timepoints (screening, cycle 1 day 1, cycle 1 day 8, cycle 2 day 1, etc.)
- **Cells**: "X" or checkmark indicating the assessment occurs at that timepoint

### Key Features to Replicate

1. **Cycle-based structure**: Many oncology trials use cycles (e.g., 21-day cycles, 28-day cycles)
2. **Multiple visit types**: 
   - Screening (pre-treatment)
   - Treatment visits (infusion days)
   - Assessment-only visits (labs, scans without treatment)
   - End of treatment visit
   - Follow-up visits
3. **Footnotes**: Often contain critical timing information (e.g., "±3 days", "within 72 hours of dosing")
4. **Multiple arms**: Some tables show different schedules for Arm A vs Arm B

### Common Assessment Types

- Complete blood count (CBC)
- Comprehensive metabolic panel (CMP)
- Urinalysis
- CT scan (chest/abdomen/pelvis)
- MRI
- PET scan
- ECG/EKG
- Echocardiogram (ECHO)
- Physical examination
- Vital signs
- ECOG performance status
- Adverse event assessment
- Concomitant medications review
- Quality of life questionnaires (EORTC QLQ-C30, EQ-5D, etc.)
- Tumor marker labs (CEA, CA-125, PSA, etc.)
- Pharmacokinetic (PK) sampling
- Drug administration/infusion

---

## Input Specification

### Input Format
Audio transcription or brief text description containing:

1. **Trial type**: Disease site, treatment type (chemo, immunotherapy, targeted)
2. **Number of arms**: Single arm or two-arm (experimental vs control)
3. **Cycle structure**: Cycle length in days, dosing schedule
4. **Visit schedule**: When patients come in and what happens
5. **Imaging frequency**: How often scans occur
6. **Lab frequency**: How often labs are drawn
7. **Any unique assessments**: PK sampling, special monitoring, etc.

### Example Input

> "This is a two-arm breast cancer trial comparing weekly paclitaxel plus pembrolizumab versus weekly paclitaxel alone. 28-day cycles. Arm A gets pembro day 1, paclitaxel days 1, 8, 15. Arm B gets paclitaxel days 1, 8, 15. Labs every week on dosing days. CT scans every 8 weeks. Physical exam and vitals every visit. ECG at screening and cycle 3 day 1 only. Treatment continues until progression, estimate 6 cycles for this schedule."

---

## Output Specification

### Output Format
PDF document containing:

1. **Title**: "Schedule of Assessments" or "Schedule of Events"
2. **Table**: Properly formatted assessment grid
3. **Footnotes**: Timing windows and clarifications
4. **Ground truth section** (needs to be in a separate csv file where the row is the ID of the trial and each row is an arm each column is a particular time frame):
   - Time-toxic days at screening
   - Time-toxic days at 1 month
   - Time-toxic days at 3 months
   - Time-toxic days at 6 months
   - Time-toxic days at 9 months
   - Time-toxic days at 12 months
   - Per arm if applicable

### Table Structure
```
| Assessment          | Screening | C1D1 | C1D8 | C1D15 | C2D1 | C2D8 | ... |
|---------------------|-----------|------|------|-------|------|------|-----|
| Informed Consent    | X         |      |      |       |      |      |     |
| Medical History     | X         |      |      |       |      |      |     |
| Physical Exam       | X         | X    |      |       | X    |      |     |
| Vital Signs         | X         | X    | X    | X     | X    | X    |     |
| ECOG PS             | X         | X    |      |       | X    |      |     |
| CBC                 | X         | X    | X    | X     | X    | X    |     |
| CMP                 | X         | X    |      |       | X    |      |     |
| CT Scan             | X         |      |      |       |      |      |     |
| ECG                 | X         |      |      |       |      |      |     |
| Drug A Admin        |           | X    | X    | X     | X    | X    |     |
| Drug B Admin        |           | X    |      |       | X    |      |     |
```

### Formatting Requirements

- Use standard table formatting similar to attached example PDFs
- Include header row with timepoints
- Use "X" to indicate assessment occurs
- Group related assessments (all labs together, all imaging together, etc.)
- Include footnotes for timing windows
- Professional appearance matching real protocol documents

---

## Ground Truth Calculation Rules

### Definition of a Time-Toxic Day
Any calendar day requiring physical healthcare system contact counts as ONE time-toxic day, regardless of how many assessments occur that day.

### Calculation Method

1. **Identify all unique visit days** within each interval
2. **Count each unique day once** (multiple assessments same day = 1 time-toxic day)
3. **Include screening visits** in the screening interval only
4. **Standard intervals**:
   - Screening: All pre-treatment visits
   - 1 month: Day 1 through Day 30
   - 3 months: Day 1 through Day 90
   - 6 months: Day 1 through Day 180
   - 9 months: Day 1 through Day 270
   - 12 months: Day 1 through Day 365

### Example Calculation

For a 21-day cycle trial with visits on D1, D8, D15 of each cycle:
- Cycle 1: Days 1, 8, 15 (3 visits)
- Cycle 2: Days 22, 29, 36 (3 visits)
- Cycle 3: Days 43, 50, 57 (3 visits)
- etc.

At 1 month (Day 30): Days 1, 8, 15, 22, 29 = **5 time-toxic days**
At 3 months (Day 90): Approximately 12-13 visits depending on exact cycle timing

---

## Complexity Levels

### Simple (5 schedules)
- Single arm
- 4-6 visits per month
- Standard labs and imaging
- Clear, unambiguous timing

### Moderate (10 schedules)
- Two arms with minor differences
- 6-10 visits per month
- Some conditional assessments
- Footnotes with timing windows

### Complex (5 schedules)
- Two arms with different visit schedules
- 10+ visits per month
- Loading doses, induction/maintenance phases
- Multiple imaging modalities
- PK sampling on subset of visits
- Ambiguous footnotes (to test pipeline handling of ambiguity)

---

## File Naming Convention
```
synthetic_schedule_[number]_[complexity]_[arms].pdf

Examples:
synthetic_schedule_01_simple_single.pdf
synthetic_schedule_07_moderate_two.pdf
synthetic_schedule_18_complex_two.pdf
```

---

## Ground Truth Documentation

Maintain a separate spreadsheet with:

| schedule_id | complexity | arms | screening_days | month1_days | month3_days | month6_days | month9_days | month12_days | notes |
|-------------|------------|------|----------------|-------------|-------------|-------------|-------------|--------------|-------|
| 01 | simple | single | 2 | 4 | 12 | 24 | 36 | 48 | standard chemo |
| 02 | simple | single | 1 | 3 | 9 | 18 | 27 | 36 | q3w dosing |

For two-arm trials, include separate columns:
- month1_days_armA, month1_days_armB, etc.

---

## Reference Materials

Attached example PDFs demonstrate:
1. Standard formatting conventions
2. Common assessment groupings
3. Typical footnote structures
4. Cycle notation styles
5. Multi-arm table layouts

Use these as templates for visual formatting. The synthetic content should be original but stylistically similar.

---

## Quality Checklist

Before finalizing each synthetic schedule:

- [ ] Table is readable and properly formatted
- [ ] All timepoints are clearly labeled
- [ ] Assessment types are realistic for the trial type
- [ ] Footnotes are included where appropriate
- [ ] Ground truth has been calculated and documented
- [ ] Cycle math is correct (no impossible dates)
- [ ] File naming convention followed
- [ ] PDF exports cleanly without formatting errors