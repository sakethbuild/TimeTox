#!/usr/bin/env python3
"""
Judge Pipeline Analysis - Detailed Comparison

Runs the 3-stage judge pipeline and produces detailed metrics:
- Pre-judge vs Post-judge comparison
- Accuracy and Clinical Accuracy metrics
- What the judge changed
- General encounter counts

Usage:
    python3 experiments/judge_analysis.py [num_schedules]
"""

import os
import sys
import csv
import json
import re
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(override=True)

from google import genai
from google.genai import types

# ============================================================================
# CONFIGURATION
# ============================================================================

MODEL = "gemini-3-flash-preview"
WINDOWS = ['screening', '1_month', '3_months', '6_months', '9_months', '12_months']

# ============================================================================
# PROMPTS (from pipeline_with_judge.py)
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
      "visit_days_per_cycle": [1, 8, 15],
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
    "screening_days": <integer>,
    "eot_visit": true,
    "m9_followup": true,
    "m12_followup": true
  }
}

IMPORTANT: Read the LEGEND carefully - it tells you exactly which days each arm visits.
"""

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

### 2. TREATMENT VISITS
- Treatment visits = total_treatment_cycles × visits_per_cycle

### 3. TOTAL 12_MONTHS CALCULATION
12_months = screening + treatment_visits + EOT + M9_FU + M12_FU

### 4. CUMULATIVE PROPERTY
12_months >= 9_months >= 6_months >= 3_months >= 1_month >= screening

### 5. WINDOW BOUNDARIES (for 28-day cycles)
Count visits where calendar_day falls within window:
- 1_month (Day 1-30): C1 visits only
- 3_months (Day 1-90): C1-C3 visits
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
      "correction_notes": "<what was wrong>"
    }}
  ]
}}
"""

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def load_ground_truth() -> Dict:
    """Load ground truth from CSV file."""
    gt_all = {}
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'synthetic_schedules', 'ground_truth.csv')
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            schedule_id = row['schedule_id']
            arm = row['arm']
            
            if schedule_id not in gt_all:
                gt_all[schedule_id] = {'complexity': row['complexity'], 'disease': row['disease']}
            
            gt_all[schedule_id][arm] = {
                'screening': int(row['screening_days']),
                '1_month': int(row['month1_days']),
                '3_months': int(row['month3_days']),
                '6_months': int(row['month6_days']),
                '9_months': int(row['month9_days']),
                '12_months': int(row['month12_days'])
            }
    return gt_all


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


def parse_json(text):
    """Extract JSON from response."""
    if not text:
        return None
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            pass
    match = re.search(r'[\[\{][\s\S]*[\]\}]', text)
    if match:
        try:
            return json.loads(match.group(0))
        except:
            pass
    return None


def extract_arm_results(results: List[Dict]) -> Tuple[Dict, Dict]:
    """Extract arm A and B results from response."""
    ext_a, ext_b = {}, {}
    for arm in results:
        name = arm.get('arm_name', '')
        days = arm.get('healthcare_contact_days', {})
        if 'A' in name and 'B' not in name:
            ext_a = days
        else:
            ext_b = days
    return ext_a, ext_b


def compute_metrics(extracted: Dict, ground_truth: Dict) -> Dict:
    """Compute accuracy metrics for a single arm."""
    metrics = {'windows': {}, 'exact_matches': 0, 'within_3': 0, 'total_error': 0}
    
    for w in WINDOWS:
        gt = ground_truth.get(w, 0)
        ext = extracted.get(w, 0)
        diff = ext - gt
        abs_diff = abs(diff)
        
        metrics['windows'][w] = {
            'gt': gt,
            'extracted': ext,
            'diff': diff,
            'match': diff == 0,
            'within_3': abs_diff <= 3
        }
        
        if diff == 0:
            metrics['exact_matches'] += 1
        if abs_diff <= 3:
            metrics['within_3'] += 1
        metrics['total_error'] += abs_diff
    
    metrics['exact_accuracy'] = metrics['exact_matches'] / len(WINDOWS)
    metrics['clinical_accuracy'] = metrics['within_3'] / len(WINDOWS)
    metrics['mae'] = metrics['total_error'] / len(WINDOWS)
    
    return metrics


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def run_pipeline(client, pdf_path: str, schedule_id: str, gt: Dict) -> Dict:
    """Run full 3-stage pipeline on a single PDF."""
    result = {
        'schedule_id': schedule_id,
        'pdf_path': pdf_path,
        'complexity': gt.get('complexity', 'unknown'),
        'disease': gt.get('disease', 'unknown'),
    }
    
    # Upload PDF
    print(f"\n  Uploading {os.path.basename(pdf_path)}...")
    uploaded = client.files.upload(file=pdf_path)
    
    # ===== STAGE 1: Extract Structure =====
    print("  Stage 1: Extracting structure...")
    stage1_response = call_api(client, uploaded, PROMPT_STAGE1)
    structure = parse_json(stage1_response)
    
    if not structure:
        result['error'] = 'Failed to parse Stage 1'
        return result
    
    result['structure'] = structure
    time.sleep(0.5)
    
    # ===== STAGE 2: Calculate Counts =====
    print("  Stage 2: Calculating counts...")
    prompt_stage2 = PROMPT_STAGE2_TEMPLATE.format(structure=json.dumps(structure, indent=2))
    stage2_response = call_api(client, uploaded, prompt_stage2)
    stage2_results = parse_json(stage2_response)
    
    if not stage2_results:
        result['error'] = 'Failed to parse Stage 2'
        return result
    
    # Store pre-judge results
    ext_a_pre, ext_b_pre = extract_arm_results(stage2_results)
    result['stage2_raw'] = stage2_results
    result['pre_judge'] = {
        'A': ext_a_pre,
        'B': ext_b_pre,
        'A_metrics': compute_metrics(ext_a_pre, gt.get('A', {})),
        'B_metrics': compute_metrics(ext_b_pre, gt.get('B', {})),
    }
    
    # Extract breakdowns
    for arm in stage2_results:
        name = arm.get('arm_name', '')
        breakdown = arm.get('calculation_breakdown', {})
        if 'A' in name and 'B' not in name:
            result['pre_judge']['A_breakdown'] = breakdown
        else:
            result['pre_judge']['B_breakdown'] = breakdown
    
    time.sleep(0.5)
    
    # ===== STAGE 3: Judge =====
    print("  Stage 3: Judge validation...")
    prompt_judge = PROMPT_JUDGE_TEMPLATE.format(
        structure=json.dumps(structure, indent=2),
        results=json.dumps(stage2_results, indent=2)
    )
    judge_response = call_api(client, uploaded, prompt_judge)
    judgment = parse_json(judge_response)
    
    if not judgment:
        result['judge_verdict'] = 'PARSE_ERROR'
        result['post_judge'] = result['pre_judge'].copy()
        return result
    
    result['judge_verdict'] = judgment.get('validation', 'UNKNOWN')
    result['judge_issues'] = judgment.get('issues', [])
    
    # Get final results (corrected or original)
    if result['judge_verdict'] == 'PASS':
        final_results = judgment.get('results', stage2_results)
    else:
        final_results = judgment.get('corrected_results', stage2_results)
    
    ext_a_post, ext_b_post = extract_arm_results(final_results)
    result['post_judge'] = {
        'A': ext_a_post,
        'B': ext_b_post,
        'A_metrics': compute_metrics(ext_a_post, gt.get('A', {})),
        'B_metrics': compute_metrics(ext_b_post, gt.get('B', {})),
    }
    
    # Track what changed
    result['judge_changes'] = {
        'A': {w: ext_a_post.get(w, 0) - ext_a_pre.get(w, 0) for w in WINDOWS},
        'B': {w: ext_b_post.get(w, 0) - ext_b_pre.get(w, 0) for w in WINDOWS},
    }
    
    return result


def print_detailed_results(results: List[Dict]):
    """Print detailed results with all metrics."""
    
    print("\n" + "=" * 90)
    print("DETAILED RESULTS: 3-STAGE JUDGE PIPELINE")
    print("=" * 90)
    
    # Aggregate metrics
    total_windows_pre = 0
    exact_pre = 0
    within_3_pre = 0
    total_error_pre = 0
    
    total_windows_post = 0
    exact_post = 0
    within_3_post = 0
    total_error_post = 0
    
    judge_pass = 0
    judge_fail = 0
    
    for result in results:
        if 'error' in result:
            continue
        
        # Count judge verdicts
        if result.get('judge_verdict') == 'PASS':
            judge_pass += 1
        elif result.get('judge_verdict') == 'FAIL':
            judge_fail += 1
        
        # Aggregate pre-judge metrics
        for arm in ['A', 'B']:
            m = result.get('pre_judge', {}).get(f'{arm}_metrics', {})
            total_windows_pre += len(WINDOWS)
            exact_pre += m.get('exact_matches', 0)
            within_3_pre += m.get('within_3', 0)
            total_error_pre += m.get('total_error', 0)
        
        # Aggregate post-judge metrics
        for arm in ['A', 'B']:
            m = result.get('post_judge', {}).get(f'{arm}_metrics', {})
            total_windows_post += len(WINDOWS)
            exact_post += m.get('exact_matches', 0)
            within_3_post += m.get('within_3', 0)
            total_error_post += m.get('total_error', 0)
    
    # ===== SUMMARY TABLE =====
    print("\n" + "─" * 90)
    print("OVERALL SUMMARY")
    print("─" * 90)
    print(f"{'Metric':<30} {'Pre-Judge':>20} {'Post-Judge':>20} {'Change':>15}")
    print("─" * 90)
    
    acc_pre = exact_pre / total_windows_pre if total_windows_pre > 0 else 0
    acc_post = exact_post / total_windows_post if total_windows_post > 0 else 0
    print(f"{'Exact Match Accuracy':<30} {acc_pre:>19.1%} {acc_post:>19.1%} {acc_post - acc_pre:>+14.1%}")
    
    clin_pre = within_3_pre / total_windows_pre if total_windows_pre > 0 else 0
    clin_post = within_3_post / total_windows_post if total_windows_post > 0 else 0
    print(f"{'Clinical Accuracy (±3)':<30} {clin_pre:>19.1%} {clin_post:>19.1%} {clin_post - clin_pre:>+14.1%}")
    
    mae_pre = total_error_pre / total_windows_pre if total_windows_pre > 0 else 0
    mae_post = total_error_post / total_windows_post if total_windows_post > 0 else 0
    print(f"{'Mean Absolute Error':<30} {mae_pre:>18.2f}d {mae_post:>18.2f}d {mae_post - mae_pre:>+13.2f}d")
    
    print(f"\n{'Judge Verdicts:':<30} PASS: {judge_pass}, FAIL: {judge_fail}")
    
    # ===== PER-SCHEDULE DETAILS =====
    print("\n" + "─" * 90)
    print("PER-SCHEDULE RESULTS")
    print("─" * 90)
    
    for result in results:
        sid = result['schedule_id']
        complexity = result.get('complexity', '?')
        disease = result.get('disease', '?')[:30]
        verdict = result.get('judge_verdict', 'ERROR')
        
        print(f"\n┌─ Schedule {sid} ({complexity}) - {disease}")
        print(f"│  Judge Verdict: {'✅ PASS' if verdict == 'PASS' else '❌ FAIL' if verdict == 'FAIL' else '⚠️ ' + verdict}")
        
        if result.get('judge_issues'):
            print(f"│  Issues: {result['judge_issues'][0][:70]}...")
        
        if 'error' in result:
            print(f"│  ❌ Error: {result['error']}")
            continue
        
        # Show structure info
        structure = result.get('structure', {})
        arms = structure.get('arms', [])
        if arms:
            arm_a = arms[0] if len(arms) > 0 else {}
            print(f"│  Structure: {arm_a.get('cycle_length_days', '?')}-day cycles, "
                  f"{arm_a.get('visits_per_cycle', '?')} visits/cycle for Arm A")
        
        # Pre-judge metrics
        pre = result.get('pre_judge', {})
        pre_a = pre.get('A_metrics', {})
        pre_b = pre.get('B_metrics', {})
        
        # Post-judge metrics  
        post = result.get('post_judge', {})
        post_a = post.get('A_metrics', {})
        post_b = post.get('B_metrics', {})
        
        print(f"│")
        print(f"│  {'Window':<12} │ {'GT_A':>5} {'Pre':>5} {'Post':>5} {'Chg':>5} │ {'GT_B':>5} {'Pre':>5} {'Post':>5} {'Chg':>5}")
        print(f"│  {'─'*12}─┼─{'─'*23}─┼─{'─'*23}")
        
        for w in WINDOWS:
            pre_a_val = pre.get('A', {}).get(w, 0)
            post_a_val = post.get('A', {}).get(w, 0)
            gt_a = pre_a.get('windows', {}).get(w, {}).get('gt', 0)
            chg_a = result.get('judge_changes', {}).get('A', {}).get(w, 0)
            
            pre_b_val = pre.get('B', {}).get(w, 0)
            post_b_val = post.get('B', {}).get(w, 0)
            gt_b = pre_b.get('windows', {}).get(w, {}).get('gt', 0)
            chg_b = result.get('judge_changes', {}).get('B', {}).get(w, 0)
            
            chg_a_str = f"{chg_a:+d}" if chg_a != 0 else "  -"
            chg_b_str = f"{chg_b:+d}" if chg_b != 0 else "  -"
            
            print(f"│  {w:<12} │ {gt_a:>5} {pre_a_val:>5} {post_a_val:>5} {chg_a_str:>5} │ {gt_b:>5} {pre_b_val:>5} {post_b_val:>5} {chg_b_str:>5}")
        
        print(f"│  {'─'*12}─┼─{'─'*23}─┼─{'─'*23}")
        
        # Accuracy row
        print(f"│  {'Exact Acc':<12} │ {'Pre:'} {pre_a.get('exact_accuracy', 0):>5.0%}  {'Post:'} {post_a.get('exact_accuracy', 0):>5.0%}     │ {'Pre:'} {pre_b.get('exact_accuracy', 0):>5.0%}  {'Post:'} {post_b.get('exact_accuracy', 0):>5.0%}")
        print(f"│  {'Clinical':<12} │ {'Pre:'} {pre_a.get('clinical_accuracy', 0):>5.0%}  {'Post:'} {post_a.get('clinical_accuracy', 0):>5.0%}     │ {'Pre:'} {pre_b.get('clinical_accuracy', 0):>5.0%}  {'Post:'} {post_b.get('clinical_accuracy', 0):>5.0%}")
        
        # Encounter breakdown
        breakdown_a = pre.get('A_breakdown', {})
        breakdown_b = pre.get('B_breakdown', {})
        if breakdown_a:
            print(f"│")
            print(f"│  Encounter Breakdown (Stage 2):")
            print(f"│    Arm A: {breakdown_a.get('total_cycles', '?')} cycles × {breakdown_a.get('treatment_visits', '?')//max(1,breakdown_a.get('total_cycles', 1))} visits = {breakdown_a.get('treatment_visits', '?')} treatment + {breakdown_a.get('screening_visits', '?')} screening + {breakdown_a.get('eot_visits', '?')} EOT + {breakdown_a.get('followup_visits', '?')} FU = {breakdown_a.get('total_visits', '?')} total")
            print(f"│    Arm B: {breakdown_b.get('total_cycles', '?')} cycles × {breakdown_b.get('treatment_visits', '?')//max(1,breakdown_b.get('total_cycles', 1))} visits = {breakdown_b.get('treatment_visits', '?')} treatment + {breakdown_b.get('screening_visits', '?')} screening + {breakdown_b.get('eot_visits', '?')} EOT + {breakdown_b.get('followup_visits', '?')} FU = {breakdown_b.get('total_visits', '?')} total")
        
        print(f"└{'─' * 88}")
    
    # ===== WHAT THE JUDGE CHANGED =====
    print("\n" + "─" * 90)
    print("JUDGE CORRECTIONS SUMMARY")
    print("─" * 90)
    
    total_changes = 0
    improvements = 0
    regressions = 0
    
    for result in results:
        if 'error' in result or result.get('judge_verdict') != 'FAIL':
            continue
        
        pre = result.get('pre_judge', {})
        post = result.get('post_judge', {})
        changes = result.get('judge_changes', {})
        
        for arm in ['A', 'B']:
            for w in WINDOWS:
                chg = changes.get(arm, {}).get(w, 0)
                if chg != 0:
                    total_changes += 1
                    gt = pre.get(f'{arm}_metrics', {}).get('windows', {}).get(w, {}).get('gt', 0)
                    pre_val = pre.get(arm, {}).get(w, 0)
                    post_val = post.get(arm, {}).get(w, 0)
                    
                    pre_err = abs(pre_val - gt)
                    post_err = abs(post_val - gt)
                    
                    if post_err < pre_err:
                        improvements += 1
                    elif post_err > pre_err:
                        regressions += 1
    
    print(f"Total values changed by judge: {total_changes}")
    print(f"  Improvements (closer to GT):  {improvements}")
    print(f"  Regressions (further from GT): {regressions}")
    print(f"  No change in error:           {total_changes - improvements - regressions}")


def main():
    num_schedules = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    
    print("=" * 90)
    print(f"3-STAGE JUDGE PIPELINE ANALYSIS - {num_schedules} Schedules")
    print("=" * 90)
    
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    gt_all = load_ground_truth()
    
    results = []
    
    for i in range(1, num_schedules + 1):
        schedule_id = f"{i:02d}"
        
        # Find PDF
        schedules_dir = os.path.join(os.path.dirname(__file__), '..', 'synthetic_schedules')
        pdf_files = [f for f in os.listdir(schedules_dir) 
                     if f.startswith(f'synthetic_schedule_{schedule_id}') and f.endswith('.pdf')]
        
        if not pdf_files:
            print(f"\n⚠️ No PDF found for schedule {schedule_id}")
            continue
        
        pdf_path = os.path.join(schedules_dir, pdf_files[0])
        gt = gt_all.get(schedule_id, {})
        
        print(f"\n{'─' * 90}")
        print(f"Processing Schedule {schedule_id}: {gt.get('disease', 'Unknown')[:50]}")
        print(f"{'─' * 90}")
        
        result = run_pipeline(client, pdf_path, schedule_id, gt)
        results.append(result)
        
        print(f"  ✓ Completed. Judge: {result.get('judge_verdict', 'ERROR')}")
        time.sleep(1)  # Rate limiting
    
    # Print detailed results
    print_detailed_results(results)
    
    # Save raw results
    output_path = os.path.join(os.path.dirname(__file__), '..', 'results', 
                               f'judge_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Raw results saved to: {output_path}")


if __name__ == "__main__":
    main()

