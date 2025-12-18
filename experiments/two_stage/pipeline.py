#!/usr/bin/env python3
"""
Two-Stage Pipeline Experiment (No Judge)

Stage 1: Extract structure (legend, cycle info)
Stage 2: Calculate visit counts using extracted structure

No Stage 3 Judge - just raw extraction + calculation

Usage:
    python3 experiments/two_stage/pipeline.py [num_schedules]
"""

import os
import sys
import csv
import json
import re
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

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
# PROMPTS
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

IMPORTANT RULES:
1. Read the LEGEND carefully - it tells you exactly which days each arm visits.
2. screening_days is the NUMBER OF SCREENING VISIT DAYS (typically 1-2 days), NOT the cycle length.
   - This is usually listed as "Screening" or "SCR" in the schedule header.
   - Even if cycle_length_days is 7, screening_days is still typically 1 or 2.
   - Look for the screening column(s) to count the actual screening days.
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

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def load_ground_truth() -> Dict:
    """Load ground truth from CSV file."""
    gt_all = {}
    csv_path = os.path.join(os.path.dirname(__file__), '..', '..', 'synthetic_schedules', 'ground_truth.csv')
    
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


def call_api(client, uploaded_file, prompt, temp=0.1, force_json=False):
    """Make API call with retry.
    
    Args:
        force_json: If True, use response_mime_type to force JSON output
    """
    for attempt in range(3):
        try:
            config = types.GenerateContentConfig(temperature=temp)
            if force_json:
                config.response_mime_type = "application/json"
            
            response = client.models.generate_content(
                model=MODEL,
                contents=[types.Content(role="user", parts=[
                    types.Part.from_uri(file_uri=uploaded_file.uri, mime_type="application/pdf"),
                    types.Part.from_text(text=prompt)
                ])],
                config=config
            )
            return response.text
        except Exception as e:
            print(f"  Retry {attempt+1}: {e}")
            time.sleep(2 ** attempt)
    return None


def parse_json(text):
    """Extract JSON from response.
    
    Handles both:
    - Forced JSON output (response_mime_type) - direct JSON
    - Prompt-based JSON - may be in code blocks or raw
    """
    if not text:
        return None
    
    # Try direct JSON parse first (for forced JSON mode)
    try:
        return json.loads(text.strip())
    except:
        pass
    
    # Try code block extraction
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            pass
    
    # Try raw JSON extraction
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
        # Match "Arm A" or "Arm B" specifically (not just 'A' or 'B' anywhere)
        if 'Arm A' in name and 'Arm B' not in name:
            ext_a = days
        elif 'Arm B' in name:
            ext_b = days
        else:
            # Fallback: check position in list (first = A, second = B)
            if len(results) == 2:
                idx = results.index(arm)
                if idx == 0:
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
# TWO-STAGE PIPELINE
# ============================================================================

def run_two_stage_pipeline(client, pdf_path: str, schedule_id: str, gt: Dict) -> Dict:
    """Run 2-stage pipeline (no judge) on a single PDF."""
    result = {
        'schedule_id': schedule_id,
        'pdf_path': pdf_path,
        'complexity': gt.get('complexity', 'unknown'),
        'disease': gt.get('disease', 'unknown'),
    }
    
    # Upload PDF
    print(f"  Uploading {os.path.basename(pdf_path)}...")
    uploaded = client.files.upload(file=pdf_path)
    
    # ===== STAGE 1: Extract Structure =====
    print("  Stage 1: Extracting structure...")
    stage1_response = call_api(client, uploaded, PROMPT_STAGE1, force_json=True)
    structure = parse_json(stage1_response)
    
    if not structure:
        result['error'] = 'Failed to parse Stage 1'
        return result
    
    result['structure'] = structure
    
    # Extract key structure info for display
    arms_info = structure.get('arms', [])
    if arms_info:
        result['cycle_length'] = arms_info[0].get('cycle_length_days', '?')
        result['arm_a_visits_per_cycle'] = arms_info[0].get('visits_per_cycle', '?')
        result['arm_b_visits_per_cycle'] = arms_info[1].get('visits_per_cycle', '?') if len(arms_info) > 1 else '?'
        result['treatment_months'] = structure.get('protocol_info', {}).get('treatment_duration_months', '?')
    
    time.sleep(0.5)
    
    # ===== STAGE 2: Calculate Counts =====
    print("  Stage 2: Calculating counts...")
    prompt_stage2 = PROMPT_STAGE2_TEMPLATE.format(structure=json.dumps(structure, indent=2))
    stage2_response = call_api(client, uploaded, prompt_stage2, force_json=True)
    stage2_results = parse_json(stage2_response)
    
    if not stage2_results:
        result['error'] = 'Failed to parse Stage 2'
        return result
    
    # Extract results
    ext_a, ext_b = extract_arm_results(stage2_results)
    result['extracted'] = {'A': ext_a, 'B': ext_b}
    
    # Compute metrics
    result['metrics_A'] = compute_metrics(ext_a, gt.get('A', {}))
    result['metrics_B'] = compute_metrics(ext_b, gt.get('B', {}))
    
    # Extract breakdowns
    for arm in stage2_results:
        name = arm.get('arm_name', '')
        breakdown = arm.get('calculation_breakdown', {})
        if 'A' in name and 'B' not in name:
            result['breakdown_A'] = breakdown
        else:
            result['breakdown_B'] = breakdown
    
    return result


# ============================================================================
# OUTPUT FORMATTING
# ============================================================================

def print_results(results: List[Dict]):
    """Print comprehensive results."""
    
    print("\n" + "=" * 90)
    print("TWO-STAGE PIPELINE RESULTS (No Judge)")
    print("=" * 90)
    
    # Aggregate metrics
    total_windows = 0
    exact_matches = 0
    within_3 = 0
    total_error = 0
    
    complexity_stats = {
        'simple': {'total': 0, 'exact': 0, 'within_3': 0},
        'moderate': {'total': 0, 'exact': 0, 'within_3': 0},
        'complex': {'total': 0, 'exact': 0, 'within_3': 0},
    }
    
    window_stats = {w: {'total': 0, 'exact': 0, 'within_3': 0, 'errors': []} for w in WINDOWS}
    
    for result in results:
        if 'error' in result:
            continue
        
        complexity = result.get('complexity', 'unknown')
        
        for arm in ['A', 'B']:
            m = result.get(f'metrics_{arm}', {})
            total_windows += len(WINDOWS)
            exact_matches += m.get('exact_matches', 0)
            within_3 += m.get('within_3', 0)
            total_error += m.get('total_error', 0)
            
            if complexity in complexity_stats:
                complexity_stats[complexity]['total'] += len(WINDOWS)
                complexity_stats[complexity]['exact'] += m.get('exact_matches', 0)
                complexity_stats[complexity]['within_3'] += m.get('within_3', 0)
            
            for w in WINDOWS:
                window_stats[w]['total'] += 1
                w_data = m.get('windows', {}).get(w, {})
                if w_data.get('match'):
                    window_stats[w]['exact'] += 1
                if w_data.get('within_3'):
                    window_stats[w]['within_3'] += 1
                window_stats[w]['errors'].append(abs(w_data.get('diff', 0)))
    
    # ===== OVERALL SUMMARY =====
    print("\n" + "─" * 90)
    print("OVERALL METRICS")
    print("─" * 90)
    
    acc = exact_matches / total_windows if total_windows > 0 else 0
    clin = within_3 / total_windows if total_windows > 0 else 0
    mae = total_error / total_windows if total_windows > 0 else 0
    
    print(f"{'Exact Match Accuracy:':<30} {exact_matches}/{total_windows} ({acc:.1%})")
    print(f"{'Clinical Accuracy (±3 days):':<30} {within_3}/{total_windows} ({clin:.1%})")
    print(f"{'Mean Absolute Error:':<30} {mae:.2f} days")
    
    # ===== BY COMPLEXITY =====
    print("\n" + "─" * 90)
    print("ACCURACY BY COMPLEXITY")
    print("─" * 90)
    print(f"{'Complexity':<15} {'N':>8} {'Exact':>12} {'Clinical':>12}")
    print("─" * 50)
    
    for comp in ['simple', 'moderate', 'complex']:
        stats = complexity_stats[comp]
        if stats['total'] > 0:
            exact_pct = stats['exact'] / stats['total']
            clin_pct = stats['within_3'] / stats['total']
            print(f"{comp.title():<15} {stats['total']:>8} {exact_pct:>11.1%} {clin_pct:>11.1%}")
    
    # ===== BY WINDOW =====
    print("\n" + "─" * 90)
    print("ACCURACY BY TIME WINDOW")
    print("─" * 90)
    print(f"{'Window':<15} {'N':>6} {'Exact':>10} {'±3 days':>10} {'MAE':>10}")
    print("─" * 55)
    
    for w in WINDOWS:
        stats = window_stats[w]
        if stats['total'] > 0:
            exact_pct = stats['exact'] / stats['total']
            clin_pct = stats['within_3'] / stats['total']
            mae_w = sum(stats['errors']) / len(stats['errors']) if stats['errors'] else 0
            print(f"{w:<15} {stats['total']:>6} {exact_pct:>9.1%} {clin_pct:>9.1%} {mae_w:>9.2f}d")
    
    # ===== PER-SCHEDULE DETAILS =====
    print("\n" + "─" * 90)
    print("PER-SCHEDULE DETAILS")
    print("─" * 90)
    
    for result in results:
        sid = result['schedule_id']
        complexity = result.get('complexity', '?')
        disease = result.get('disease', '?')[:40]
        
        print(f"\n┌─ Schedule {sid} ({complexity}) - {disease}")
        
        if 'error' in result:
            print(f"│  ❌ Error: {result['error']}")
            print(f"└{'─' * 88}")
            continue
        
        # Structure info
        print(f"│  Structure: {result.get('cycle_length', '?')}-day cycles, "
              f"{result.get('treatment_months', '?')} months treatment")
        print(f"│  Visits/cycle: Arm A = {result.get('arm_a_visits_per_cycle', '?')}, "
              f"Arm B = {result.get('arm_b_visits_per_cycle', '?')}")
        
        # Results table
        print(f"│")
        print(f"│  {'Window':<12} │ {'GT_A':>5} {'Ext_A':>6} {'Diff':>5} │ {'GT_B':>5} {'Ext_B':>6} {'Diff':>5}")
        print(f"│  {'─'*12}─┼─{'─'*18}─┼─{'─'*18}")
        
        m_a = result.get('metrics_A', {})
        m_b = result.get('metrics_B', {})
        ext_a = result.get('extracted', {}).get('A', {})
        ext_b = result.get('extracted', {}).get('B', {})
        
        for w in WINDOWS:
            gt_a = m_a.get('windows', {}).get(w, {}).get('gt', 0)
            gt_b = m_b.get('windows', {}).get(w, {}).get('gt', 0)
            ea = ext_a.get(w, 0)
            eb = ext_b.get(w, 0)
            diff_a = ea - gt_a
            diff_b = eb - gt_b
            
            diff_a_str = f"{diff_a:+d}" if diff_a != 0 else "  ✓"
            diff_b_str = f"{diff_b:+d}" if diff_b != 0 else "  ✓"
            
            print(f"│  {w:<12} │ {gt_a:>5} {ea:>6} {diff_a_str:>5} │ {gt_b:>5} {eb:>6} {diff_b_str:>5}")
        
        print(f"│  {'─'*12}─┼─{'─'*18}─┼─{'─'*18}")
        
        # Summary row
        print(f"│  {'Exact Match':<12} │ {m_a.get('exact_accuracy', 0):>17.0%} │ {m_b.get('exact_accuracy', 0):>17.0%}")
        print(f"│  {'Clinical':<12} │ {m_a.get('clinical_accuracy', 0):>17.0%} │ {m_b.get('clinical_accuracy', 0):>17.0%}")
        
        # Breakdown
        bd_a = result.get('breakdown_A', {})
        bd_b = result.get('breakdown_B', {})
        if bd_a:
            print(f"│")
            print(f"│  Encounter Breakdown:")
            cycles_a = bd_a.get('total_cycles', 0)
            visits_per_a = bd_a.get('treatment_visits', 0) // max(1, cycles_a) if cycles_a else 0
            print(f"│    A: {cycles_a} cycles × {visits_per_a}/cycle = {bd_a.get('treatment_visits', '?')} tx "
                  f"+ {bd_a.get('screening_visits', '?')} scr + {bd_a.get('eot_visits', '?')} EOT "
                  f"+ {bd_a.get('followup_visits', '?')} FU = {bd_a.get('total_visits', '?')} total")
            
            cycles_b = bd_b.get('total_cycles', 0)
            visits_per_b = bd_b.get('treatment_visits', 0) // max(1, cycles_b) if cycles_b else 0
            print(f"│    B: {cycles_b} cycles × {visits_per_b}/cycle = {bd_b.get('treatment_visits', '?')} tx "
                  f"+ {bd_b.get('screening_visits', '?')} scr + {bd_b.get('eot_visits', '?')} EOT "
                  f"+ {bd_b.get('followup_visits', '?')} FU = {bd_b.get('total_visits', '?')} total")
        
        print(f"└{'─' * 88}")
    
    return {
        'exact_accuracy': acc,
        'clinical_accuracy': clin,
        'mae': mae,
        'total_comparisons': total_windows,
        'exact_matches': exact_matches,
        'within_3': within_3,
    }


def main():
    num_schedules = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    
    print("=" * 90)
    print(f"TWO-STAGE PIPELINE (No Judge) - {num_schedules} Schedules")
    print("=" * 90)
    print("Stage 1: Extract structure from legend")
    print("Stage 2: Calculate visit counts")
    print("(No Stage 3 Judge)")
    
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    gt_all = load_ground_truth()
    
    results = []
    
    for i in range(1, num_schedules + 1):
        schedule_id = f"{i:02d}"
        
        # Find PDF
        schedules_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'synthetic_schedules')
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
        
        result = run_two_stage_pipeline(client, pdf_path, schedule_id, gt)
        results.append(result)
        
        # Quick status
        if 'error' not in result:
            m_a = result.get('metrics_A', {})
            m_b = result.get('metrics_B', {})
            print(f"  ✓ Done. Exact: A={m_a.get('exact_accuracy', 0):.0%}, B={m_b.get('exact_accuracy', 0):.0%}")
        else:
            print(f"  ✗ Error: {result['error']}")
        
        time.sleep(1)  # Rate limiting
    
    # Print comprehensive results
    metrics = print_results(results)
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(os.path.dirname(__file__), '..', '..', 'results', 
                               f'two_stage_results_{timestamp}.json')
    
    output_data = {
        'experiment': 'two_stage_pipeline',
        'timestamp': timestamp,
        'num_schedules': num_schedules,
        'model': MODEL,
        'summary_metrics': metrics,
        'per_schedule_results': results,
    }
    
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {output_path}")


if __name__ == "__main__":
    main()

