#!/usr/bin/env python3
"""
TimeTox Best Performer: Two-Stage Pipeline

Achieved 100% Clinical Accuracy (±3 days) on 20 synthetic schedules.

Architecture:
- Stage 1: Structure Extraction (legend, cycle info)
- Stage 2: Visit Count Calculation (using extracted structure + PDF verification)

Key Features:
- Forced JSON output via response_mime_type
- Robust arm matching logic
- Proper screening days extraction (not confused with cycle length)

Final Metrics (n=20 schedules, 240 comparisons):
- Exact Match: 29.2%
- Clinical Accuracy (±3 days): 100.0%
- Mean Absolute Error: 0.81 days

Usage:
    python3 Stage2_Bestperformer/pipeline.py [num_schedules]
"""

import os
import sys
import csv
import json
import re
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

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

def load_ground_truth(csv_path: str = None) -> Dict:
    """Load ground truth from CSV file."""
    if csv_path is None:
        csv_path = os.path.join(os.path.dirname(__file__), '..', 'synthetic_schedules', 'ground_truth.csv')
    
    gt_all = {}
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


def call_api(client, uploaded_file, prompt, temp=0.1, force_json=True):
    """Make API call with retry and forced JSON output."""
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
    """Extract JSON from response."""
    if not text:
        return None
    
    # Try direct JSON parse first (for forced JSON mode)
    try:
        return json.loads(text.strip())
    except:
        pass
    
    # Try code block extraction (fallback)
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            pass
    
    # Try raw JSON extraction (fallback)
    match = re.search(r'[\[\{][\s\S]*[\]\}]', text)
    if match:
        try:
            return json.loads(match.group(0))
        except:
            pass
    return None


def extract_arm_results(results: List[Dict]) -> Tuple[Dict, Dict]:
    """Extract arm A and B results from response with robust matching."""
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
# TWO-STAGE PIPELINE (BEST PERFORMER)
# ============================================================================

def run_pipeline(client, pdf_path: str, schedule_id: str, gt: Dict) -> Dict:
    """
    Run the two-stage pipeline on a single PDF.
    
    Stage 1: Extract structure (legend, cycle info, special visits)
    Stage 2: Calculate visit counts using structure + PDF verification
    
    Returns dictionary with extracted values and metrics.
    """
    result = {
        'schedule_id': schedule_id,
        'pdf_path': pdf_path,
        'complexity': gt.get('complexity', 'unknown'),
        'disease': gt.get('disease', 'unknown'),
    }
    
    # Upload PDF (used by both stages)
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
    
    # Extract key structure info
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
    
    # Extract results with robust arm matching
    ext_a, ext_b = extract_arm_results(stage2_results)
    result['extracted'] = {'A': ext_a, 'B': ext_b}
    
    # Compute metrics
    result['metrics_A'] = compute_metrics(ext_a, gt.get('A', {}))
    result['metrics_B'] = compute_metrics(ext_b, gt.get('B', {}))
    
    # Extract breakdowns
    for arm in stage2_results:
        name = arm.get('arm_name', '')
        breakdown = arm.get('calculation_breakdown', {})
        if 'Arm A' in name and 'Arm B' not in name:
            result['breakdown_A'] = breakdown
        else:
            result['breakdown_B'] = breakdown
    
    return result


# ============================================================================
# MAIN
# ============================================================================

def main():
    num_schedules = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    
    print("=" * 70)
    print("TimeTox Best Performer: Two-Stage Pipeline")
    print("=" * 70)
    print("Stage 1: Extract structure from legend")
    print("Stage 2: Calculate visit counts (with PDF verification)")
    print(f"Running on {num_schedules} schedules...")
    
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    gt_all = load_ground_truth()
    
    results = []
    total_exact = 0
    total_within_3 = 0
    total_comparisons = 0
    
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
        
        print(f"\n[{schedule_id}] {gt.get('disease', 'Unknown')[:50]}")
        
        result = run_pipeline(client, pdf_path, schedule_id, gt)
        results.append(result)
        
        if 'error' not in result:
            m_a = result.get('metrics_A', {})
            m_b = result.get('metrics_B', {})
            total_exact += m_a.get('exact_matches', 0) + m_b.get('exact_matches', 0)
            total_within_3 += m_a.get('within_3', 0) + m_b.get('within_3', 0)
            total_comparisons += 12  # 6 windows × 2 arms
            
            clin_a = m_a.get('clinical_accuracy', 0)
            clin_b = m_b.get('clinical_accuracy', 0)
            print(f"  ✓ Clinical: A={clin_a:.0%}, B={clin_b:.0%}")
        else:
            print(f"  ✗ Error: {result['error']}")
        
        time.sleep(1)
    
    # Summary
    print("\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)
    exact_acc = total_exact / total_comparisons if total_comparisons > 0 else 0
    clin_acc = total_within_3 / total_comparisons if total_comparisons > 0 else 0
    print(f"Exact Match Accuracy: {exact_acc:.1%} ({total_exact}/{total_comparisons})")
    print(f"Clinical Accuracy (±3 days): {clin_acc:.1%} ({total_within_3}/{total_comparisons})")
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(os.path.dirname(__file__), '..', 'results', 
                               f'bestperformer_results_{timestamp}.json')
    
    output_data = {
        'experiment': 'two_stage_bestperformer',
        'timestamp': timestamp,
        'num_schedules': num_schedules,
        'model': MODEL,
        'summary': {
            'exact_accuracy': exact_acc,
            'clinical_accuracy': clin_acc,
            'total_comparisons': total_comparisons,
        },
        'results': results,
    }
    
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {output_path}")


if __name__ == "__main__":
    main()

