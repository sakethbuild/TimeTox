#!/usr/bin/env python3
"""
Three-Stage Extraction Pipeline with Judge

Stage 1: Extract structure (legend, cycle info)
Stage 2: Calculate visit counts using extracted structure  
Stage 3: Judge validates and corrects if needed

Usage: python3 pipeline_with_judge.py
"""

import os
import json
import re
import time
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

MODEL = "gemini-3-flash-preview"
WINDOWS = ['screening', '1_month', '3_months', '6_months', '9_months', '12_months']

# Ground truth for validation (by schedule ID)
GT_ALL = {
    '01': {
        'A': {'screening': 2, '1_month': 4, '3_months': 11, '6_months': 22, '9_months': 33, '12_months': 43},
        'B': {'screening': 2, '1_month': 3, '3_months': 8, '6_months': 15, '9_months': 23, '12_months': 30}
    },
    '07': {
        'A': {'screening': 2, '1_month': 4, '3_months': 11, '6_months': 22, '9_months': 33, '12_months': 43},
        'B': {'screening': 2, '1_month': 3, '3_months': 8, '6_months': 15, '9_months': 23, '12_months': 30}
    },
    '14': {
        'A': {'screening': 2, '1_month': 3, '3_months': 7, '6_months': 14, '9_months': 22, '12_months': 23},
        'B': {'screening': 2, '1_month': 2, '3_months': 4, '6_months': 8, '9_months': 12, '12_months': 13}
    }
}
GT = GT_ALL.get('01')  # Default

# ============================================================================
# STAGE 1: STRUCTURE EXTRACTION
# ============================================================================

PROMPT_STAGE1 = """
Extract the STRUCTURE from this Schedule of Assessments. Focus on the LEGEND section.

Return ONLY this JSON structure:
{
  "protocol_info": {
    "disease": "<disease name>",
    "treatment_duration_months": <integer>
  },
  "arms": [
    {
      "arm_name": "Arm A (Treatment Name)",
      "intervention_type": "intervention",
      "cycle_length_days": <integer>,
      "visit_days_per_cycle": [1, 8, 15],  // List of days within each cycle
      "visits_per_cycle": <integer>,
      "legend_text": "<exact quote from legend>"
    },
    {
      "arm_name": "Arm B (Control Name)",
      "intervention_type": "control",
      "cycle_length_days": <integer>,
      "visit_days_per_cycle": [1, 15],
      "visits_per_cycle": <integer>,
      "legend_text": "<exact quote from legend>"
    }
  ],
  "special_visits": {
    "screening_days": <integer>,  // Usually 1-2
    "eot_visit": true,
    "m9_followup": true,
    "m12_followup": true
  }
}

IMPORTANT: Read the LEGEND carefully - it tells you exactly which days each arm visits.
"""


# ============================================================================
# STAGE 2: CALCULATION
# ============================================================================

PROMPT_STAGE2_TEMPLATE = """
Calculate healthcare contact days using this extracted structure:

{structure}

## CALCULATION RULES

1. Total cycles = floor(treatment_duration_months × 30 / cycle_length_days)

2. For each arm, calculate treatment visits:
   - Map each cycle to calendar days
   - C1 starts at Day 1, C2 starts at Day (cycle_length + 1), etc.
   - Apply visit_days_per_cycle pattern to each cycle
   
3. Count CUMULATIVE visits per window:
   - screening: screening_days only
   - 1_month: screening + visits from Day 1-30
   - 3_months: screening + visits from Day 1-90
   - 6_months: screening + visits from Day 1-180
   - 9_months: screening + visits from Day 1-270 + EOT if applicable
   - 12_months: ALL visits (screening + treatment + EOT + M9 FU + M12 FU)

4. Add special visits at appropriate windows:
   - EOT visit: Add 1 at the window where treatment ends
   - M9 FU: Add 1 to 9_months and 12_months
   - M12 FU: Add 1 to 12_months only

Return ONLY JSON:
[
  {{
    "arm_name": "...",
    "healthcare_contact_days": {{
      "screening": <int>,
      "1_month": <int>,
      "3_months": <int>,
      "6_months": <int>,
      "9_months": <int>,
      "12_months": <int>
    }},
    "calculation_breakdown": {{
      "total_cycles": <int>,
      "treatment_visits": <int>,
      "screening_visits": <int>,
      "eot_visits": <int>,
      "followup_visits": <int>,
      "total_visits": <int>
    }}
  }}
]
"""


# ============================================================================
# STAGE 3: JUDGE
# ============================================================================

PROMPT_JUDGE_TEMPLATE = """
You are a STRICT JUDGE validating extraction results. You have access to the ORIGINAL PDF document.

Your job:
1. VERIFY the extracted structure against the actual PDF (legend, table)
2. VERIFY the calculated results are mathematically correct
3. CORRECT any errors by recalculating from the PDF

## EXTRACTED STRUCTURE (from Stage 1):
{structure}

## CALCULATED RESULTS (from Stage 2):
{results}

## VALIDATION PROCESS:

First, CHECK THE PDF to verify:
- Is the treatment_duration_months correct?
- Are the visit_days_per_cycle correct for each arm?
- Are the special visits (screening, EOT, follow-up) correctly identified?

Then, VERIFY THE MATH:

### 1. CYCLE COUNT VERIFICATION
- Use the ACTUAL treatment_duration_months from the structure (could be 6, 9, or 12 months)
- Treatment days = treatment_duration_months × 30
- Total treatment cycles = floor(treatment_days / cycle_length_days)
- Example: 9-month treatment with 28-day cycles: floor(270/28) = 9 cycles
- Example: 12-month treatment with 28-day cycles: floor(360/28) = 12-13 cycles

### 2. TREATMENT VISITS
- Treatment visits = total_treatment_cycles × visits_per_cycle
- For 9-month treatment: 9 cycles × 2 visits = 18 treatment visits
- For 12-month treatment: 13 cycles × 3 visits = 39 treatment visits

### 3. TOTAL 12_MONTHS CALCULATION
12_months = screening + treatment_visits + EOT + M9_FU + M12_FU
- If treatment ends at 9 months: treatment visits stop at cycle 9, then add EOT + follow-ups
- 9-month example: screening(2) + treatment(18) + EOT(1) + M9(1) + M12(1) = 23

### 4. CUMULATIVE PROPERTY
12_months >= 9_months >= 6_months >= 3_months >= 1_month >= screening

### 5. WINDOW BOUNDARIES (for 28-day cycles)
Count visits where calendar_day falls within window:
- 1_month (Day 1-30): C1 visits only (Days 1, 8, 15 for Arm A)
- 3_months (Day 1-90): C1-C3 visits (Days 1-84 complete, partial C4)
- 6_months (Day 1-180): C1-C6 complete + partial C7
- 9_months (Day 1-270): C1-C9 complete + partial C10
- 12_months (Day 1-365): All cycles + EOT + follow-ups

## YOUR TASK:

Recalculate each value. If ANY number differs from the correct calculation, return FAIL with corrections.

If ALL numbers match your calculation:
{{
  "validation": "PASS",
  "verification": {{
    "total_cycles": <your calculated cycles>,
    "arm_a_treatment_visits": <your calculation>,
    "arm_b_treatment_visits": <your calculation>
  }},
  "results": <the original results>
}}

If ANY numbers are wrong:
{{
  "validation": "FAIL",
  "issues": ["<specific issue 1>", "<specific issue 2>"],
  "corrected_results": [
    {{
      "arm_name": "...",
      "healthcare_contact_days": {{
        "screening": <corrected>,
        "1_month": <corrected>,
        "3_months": <corrected>,
        "6_months": <corrected>,
        "9_months": <corrected>,
        "12_months": <corrected>
      }},
      "correction_notes": "<what was wrong: e.g., 'Used 12 cycles instead of 13'>"
    }}
  ]
}}
"""


def call_api(client, uploaded_file, prompt, temp=0.1):
    """Make API call with retry."""
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=[types.Content(role="user", parts=[
                    types.Part.from_uri(file_uri=uploaded_file.uri, mime_type="application/pdf"),
                    types.Part.from_text(text=prompt)
                ])],
                config=types.GenerateContentConfig(temperature=temp)
            )
            return response.text
        except Exception as e:
            print(f"  Retry {attempt+1}: {e}")
            time.sleep(2 ** attempt)
    return None


def call_api_text_only(client, prompt, temp=0.1):
    """Make API call without file (for judge)."""
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=[types.Content(role="user", parts=[
                    types.Part.from_text(text=prompt)
                ])],
                config=types.GenerateContentConfig(temperature=temp)
            )
            return response.text
        except Exception as e:
            print(f"  Retry {attempt+1}: {e}")
            time.sleep(2 ** attempt)
    return None


def parse_json(text):
    """Extract JSON from response."""
    # Try code block first
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            pass
    
    # Try raw JSON
    match = re.search(r'[\[\{][\s\S]*[\]\}]', text)
    if match:
        try:
            return json.loads(match.group(0))
        except:
            pass
    return None


def main():
    import sys
    
    # Get PDF from command line or default
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = "synthetic_schedules/synthetic_schedule_01_complex_two.pdf"
    
    # Extract schedule ID from filename
    import re
    match = re.search(r'schedule_(\d+)', pdf_path)
    schedule_id = match.group(1) if match else '01'
    
    global GT
    GT = GT_ALL.get(schedule_id, GT_ALL.get('01'))
    
    print("=" * 70)
    print(f"THREE-STAGE PIPELINE: Schedule {schedule_id}")
    print("=" * 70)
    
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    print(f"\nUploading {pdf_path}...")
    uploaded = client.files.upload(file=pdf_path)
    print(f"Uploaded: {uploaded.uri}")
    
    # =========== STAGE 1: Extract Structure ===========
    print("\n" + "=" * 50)
    print("STAGE 1: Extracting Structure from Legend")
    print("=" * 50)
    
    stage1_response = call_api(client, uploaded, PROMPT_STAGE1)
    structure = parse_json(stage1_response)
    
    if structure:
        print("\nExtracted Structure:")
        print(json.dumps(structure, indent=2))
    else:
        print("Failed to parse structure!")
        print("Raw response:", stage1_response[:500])
        return
    
    time.sleep(1)
    
    # =========== STAGE 2: Calculate Counts ===========
    print("\n" + "=" * 50)
    print("STAGE 2: Calculating Visit Counts")
    print("=" * 50)
    
    prompt_stage2 = PROMPT_STAGE2_TEMPLATE.format(structure=json.dumps(structure, indent=2))
    stage2_response = call_api(client, uploaded, prompt_stage2)
    results = parse_json(stage2_response)
    
    if results:
        print("\nCalculated Results:")
        for arm in results:
            print(f"\n{arm.get('arm_name', 'Unknown')}:")
            days = arm.get('healthcare_contact_days', {})
            for w in WINDOWS:
                print(f"  {w}: {days.get(w, '?')}")
            if 'calculation_breakdown' in arm:
                print(f"  Breakdown: {arm['calculation_breakdown']}")
    else:
        print("Failed to parse results!")
        print("Raw response:", stage2_response[:500])
        return
    
    time.sleep(1)
    
    # =========== STAGE 3: Judge ===========
    print("\n" + "=" * 50)
    print("STAGE 3: Judge Validation (with PDF access)")
    print("=" * 50)
    
    prompt_judge = PROMPT_JUDGE_TEMPLATE.format(
        structure=json.dumps(structure, indent=2),
        results=json.dumps(results, indent=2)
    )
    # Judge gets the PDF too so it can verify against the actual document
    judge_response = call_api(client, uploaded, prompt_judge)
    judgment = parse_json(judge_response)
    
    if judgment:
        validation = judgment.get('validation', 'UNKNOWN')
        print(f"\nJudge Verdict: {validation}")
        
        if validation == 'PASS':
            final_results = judgment.get('results', results)
            print("Results validated - no corrections needed.")
        else:
            issues = judgment.get('issues', [])
            print(f"Issues found: {issues}")
            final_results = judgment.get('corrected_results', results)
            print("\nCorrected Results:")
            for arm in final_results:
                print(f"\n{arm.get('arm_name', 'Unknown')}:")
                days = arm.get('healthcare_contact_days', {})
                for w in WINDOWS:
                    print(f"  {w}: {days.get(w, '?')}")
                if 'correction_notes' in arm:
                    print(f"  Notes: {arm['correction_notes']}")
    else:
        print("Failed to parse judgment!")
        print("Raw response:", judge_response[:500] if judge_response else "None")
        final_results = results
    
    # =========== FINAL COMPARISON ===========
    print("\n" + "=" * 50)
    print("FINAL COMPARISON vs GROUND TRUTH")
    print("=" * 50)
    
    print(f"\n{'Window':<12} {'GT_A':>6} {'Ext_A':>6} {'Diff':>6} | {'GT_B':>6} {'Ext_B':>6} {'Diff':>6}")
    print("-" * 60)
    
    ext_a = {}
    ext_b = {}
    for arm in final_results:
        name = arm.get('arm_name', '')
        days = arm.get('healthcare_contact_days', {})
        if 'Abemaciclib' in name or ('A' in name and 'B' not in name):
            ext_a = days
        else:
            ext_b = days
    
    for w in WINDOWS:
        gt_a = GT['A'].get(w, 0)
        gt_b = GT['B'].get(w, 0)
        ea = ext_a.get(w, 0)
        eb = ext_b.get(w, 0)
        diff_a = ea - gt_a
        diff_b = eb - gt_b
        print(f"{w:<12} {gt_a:>6} {ea:>6} {diff_a:>+6} | {gt_b:>6} {eb:>6} {diff_b:>+6}")


if __name__ == "__main__":
    main()

