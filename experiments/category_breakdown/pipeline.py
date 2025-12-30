#!/usr/bin/env python3
"""
Category Breakdown Pipeline

Based on Stage2_Bestperformer (100% clinical accuracy), extended to extract
and compare category-level visit breakdowns.

Categories:
- core_treatment: Drug administration, infusions, treatment procedures
- imaging_diagnostics: CT, MRI, PET, X-ray, ultrasound, ECG, ECHO
- labs: Blood draws, urinalysis, biomarkers
- clinic_visits: Physical exam, vital signs, assessments

Usage:
    python3 experiments/category_breakdown/pipeline.py [num_schedules]
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
CATEGORIES = ['core_treatment', 'imaging_diagnostics', 'labs', 'clinic_visits']

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

## CATEGORY DEFINITIONS

Break down visits by what happens on each day:

- **core_treatment**: Days with drug administration, infusions, or treatment procedures
- **imaging_diagnostics**: Days with CT, MRI, PET, X-ray, ultrasound, ECG, or ECHO
- **labs**: Days with blood draws, urinalysis, or biomarker tests
- **clinic_visits**: Days with physical exam, vital signs, or other clinical assessments

Note: A single day may include multiple categories. Count the day in EACH category that occurs.

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
    "category_breakdown": {{
      "core_treatment": {{
        "screening": <int>,
        "1_month": <int>,
        "3_months": <int>,
        "6_months": <int>,
        "9_months": <int>,
        "12_months": <int>
      }},
      "imaging_diagnostics": {{
        "screening": <int>,
        "1_month": <int>,
        "3_months": <int>,
        "6_months": <int>,
        "9_months": <int>,
        "12_months": <int>
      }},
      "labs": {{
        "screening": <int>,
        "1_month": <int>,
        "3_months": <int>,
        "6_months": <int>,
        "9_months": <int>,
        "12_months": <int>
      }},
      "clinic_visits": {{
        "screening": <int>,
        "1_month": <int>,
        "3_months": <int>,
        "6_months": <int>,
        "9_months": <int>,
        "12_months": <int>
      }}
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

def load_category_ground_truth(json_path: str = None) -> Dict:
    """Load category ground truth from JSON file."""
    if json_path is None:
        json_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 
            'synthetic_schedules', 'category_ground_truth.json'
        )
    
    with open(json_path, 'r') as f:
        return json.load(f)


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
    
    try:
        return json.loads(text.strip())
    except:
        pass
    
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
    """Extract arm A and B results from response with robust matching."""
    ext_a, ext_b = {}, {}
    cat_a, cat_b = {}, {}
    
    for arm in results:
        name = arm.get('arm_name', '')
        days = arm.get('healthcare_contact_days', {})
        categories = arm.get('category_breakdown', {})
        
        if 'Arm A' in name and 'Arm B' not in name:
            ext_a = days
            cat_a = categories
        elif 'Arm B' in name:
            ext_b = days
            cat_b = categories
        else:
            if len(results) == 2:
                idx = results.index(arm)
                if idx == 0:
                    ext_a = days
                    cat_a = categories
                else:
                    ext_b = days
                    cat_b = categories
    
    return (ext_a, cat_a), (ext_b, cat_b)


def compute_metrics(extracted: Dict, ground_truth: Dict) -> Dict:
    """Compute accuracy metrics for totals."""
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


def compute_category_metrics(extracted_cat: Dict, gt_cat: Dict) -> Dict:
    """Compute accuracy metrics for category breakdown."""
    metrics = {'categories': {}, 'total_exact': 0, 'total_within_3': 0, 
               'total_comparisons': 0, 'total_error': 0}
    
    for cat in CATEGORIES:
        cat_metrics = {'windows': {}, 'exact_matches': 0, 'within_3': 0, 'total_error': 0}
        ext_cat_data = extracted_cat.get(cat, {})
        gt_cat_data = gt_cat.get(cat, {})
        
        for w in WINDOWS:
            gt = gt_cat_data.get(w, 0)
            ext = ext_cat_data.get(w, 0)
            diff = ext - gt
            abs_diff = abs(diff)
            
            cat_metrics['windows'][w] = {
                'gt': gt,
                'extracted': ext,
                'diff': diff,
                'match': diff == 0,
                'within_3': abs_diff <= 3
            }
            
            if diff == 0:
                cat_metrics['exact_matches'] += 1
                metrics['total_exact'] += 1
            if abs_diff <= 3:
                cat_metrics['within_3'] += 1
                metrics['total_within_3'] += 1
            
            cat_metrics['total_error'] += abs_diff
            metrics['total_error'] += abs_diff
            metrics['total_comparisons'] += 1
        
        cat_metrics['exact_accuracy'] = cat_metrics['exact_matches'] / len(WINDOWS)
        cat_metrics['clinical_accuracy'] = cat_metrics['within_3'] / len(WINDOWS)
        cat_metrics['mae'] = cat_metrics['total_error'] / len(WINDOWS)
        
        metrics['categories'][cat] = cat_metrics
    
    if metrics['total_comparisons'] > 0:
        metrics['overall_exact_accuracy'] = metrics['total_exact'] / metrics['total_comparisons']
        metrics['overall_clinical_accuracy'] = metrics['total_within_3'] / metrics['total_comparisons']
        metrics['overall_mae'] = metrics['total_error'] / metrics['total_comparisons']
    
    return metrics


# ============================================================================
# CATEGORY BREAKDOWN PIPELINE
# ============================================================================

def run_category_pipeline(client, pdf_path: str, schedule_id: str, gt: Dict) -> Dict:
    """
    Run the category breakdown pipeline on a single PDF.
    
    Stage 1: Extract structure (same as best performer)
    Stage 2: Calculate visit counts WITH category breakdown
    """
    result = {
        'schedule_id': schedule_id,
        'pdf_path': pdf_path,
        'cycle_length': gt.get('cycle_length', '?'),
        'treatment_months': gt.get('treatment_months', '?'),
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
    
    time.sleep(0.5)
    
    # ===== STAGE 2: Calculate Counts with Categories =====
    print("  Stage 2: Calculating counts with category breakdown...")
    prompt_stage2 = PROMPT_STAGE2_TEMPLATE.format(structure=json.dumps(structure, indent=2))
    stage2_response = call_api(client, uploaded, prompt_stage2, force_json=True)
    stage2_results = parse_json(stage2_response)
    
    if not stage2_results:
        result['error'] = 'Failed to parse Stage 2'
        return result
    
    # Extract results
    (ext_a, cat_a), (ext_b, cat_b) = extract_arm_results(stage2_results)
    result['extracted'] = {
        'A': {'total': ext_a, 'category_breakdown': cat_a},
        'B': {'total': ext_b, 'category_breakdown': cat_b}
    }
    
    # Get ground truth
    gt_a = gt.get('A', {})
    gt_b = gt.get('B', {})
    
    # Compute total metrics
    result['metrics_A'] = compute_metrics(ext_a, gt_a.get('total', {}))
    result['metrics_B'] = compute_metrics(ext_b, gt_b.get('total', {}))
    
    # Compute category metrics
    result['category_metrics_A'] = compute_category_metrics(cat_a, gt_a.get('category_breakdown', {}))
    result['category_metrics_B'] = compute_category_metrics(cat_b, gt_b.get('category_breakdown', {}))
    
    return result


# ============================================================================
# OUTPUT FORMATTING
# ============================================================================

def print_results(results: List[Dict]):
    """Print comprehensive results."""
    
    print("\n" + "=" * 90)
    print("CATEGORY BREAKDOWN PIPELINE RESULTS")
    print("=" * 90)
    
    # Aggregate metrics
    total_windows = 0
    exact_matches = 0
    within_3 = 0
    
    # Category aggregates
    cat_total = 0
    cat_exact = 0
    cat_within_3 = 0
    
    category_stats = {cat: {'exact': 0, 'within_3': 0, 'total': 0} for cat in CATEGORIES}
    
    for result in results:
        if 'error' in result:
            continue
        
        for arm in ['A', 'B']:
            m = result.get(f'metrics_{arm}', {})
            total_windows += len(WINDOWS)
            exact_matches += m.get('exact_matches', 0)
            within_3 += m.get('within_3', 0)
            
            cm = result.get(f'category_metrics_{arm}', {})
            cat_total += cm.get('total_comparisons', 0)
            cat_exact += cm.get('total_exact', 0)
            cat_within_3 += cm.get('total_within_3', 0)
            
            for cat in CATEGORIES:
                cat_data = cm.get('categories', {}).get(cat, {})
                category_stats[cat]['exact'] += cat_data.get('exact_matches', 0)
                category_stats[cat]['within_3'] += cat_data.get('within_3', 0)
                category_stats[cat]['total'] += len(WINDOWS)
    
    # ===== TOTAL METRICS =====
    print("\n" + "─" * 90)
    print("TOTAL VISIT COUNTS (Same as Best Performer)")
    print("─" * 90)
    
    acc = exact_matches / total_windows if total_windows > 0 else 0
    clin = within_3 / total_windows if total_windows > 0 else 0
    
    print(f"{'Exact Match Accuracy:':<30} {exact_matches}/{total_windows} ({acc:.1%})")
    print(f"{'Clinical Accuracy (±3 days):':<30} {within_3}/{total_windows} ({clin:.1%})")
    
    # ===== CATEGORY METRICS =====
    print("\n" + "─" * 90)
    print("CATEGORY BREAKDOWN METRICS")
    print("─" * 90)
    
    cat_acc = cat_exact / cat_total if cat_total > 0 else 0
    cat_clin = cat_within_3 / cat_total if cat_total > 0 else 0
    
    print(f"{'Overall Exact Match:':<30} {cat_exact}/{cat_total} ({cat_acc:.1%})")
    print(f"{'Overall Clinical (±3 days):':<30} {cat_within_3}/{cat_total} ({cat_clin:.1%})")
    
    print("\n" + "─" * 50)
    print(f"{'Category':<25} {'Exact':>12} {'Clinical':>12}")
    print("─" * 50)
    
    for cat in CATEGORIES:
        stats = category_stats[cat]
        if stats['total'] > 0:
            exact_pct = stats['exact'] / stats['total']
            clin_pct = stats['within_3'] / stats['total']
            print(f"{cat:<25} {exact_pct:>11.1%} {clin_pct:>11.1%}")
    
    # ===== PER-SCHEDULE DETAILS =====
    print("\n" + "─" * 90)
    print("PER-SCHEDULE SUMMARY")
    print("─" * 90)
    
    for result in results:
        sid = result['schedule_id']
        
        print(f"\n┌─ Schedule {sid}")
        
        if 'error' in result:
            print(f"│  ❌ Error: {result['error']}")
            print(f"└{'─' * 88}")
            continue
        
        for arm in ['A', 'B']:
            m = result.get(f'metrics_{arm}', {})
            cm = result.get(f'category_metrics_{arm}', {})
            
            total_acc = m.get('clinical_accuracy', 0)
            cat_acc = cm.get('overall_clinical_accuracy', 0)
            
            print(f"│  Arm {arm}: Total {total_acc:.0%} clinical | Categories {cat_acc:.0%} clinical")
            
            # Show per-category
            for cat in CATEGORIES:
                cat_data = cm.get('categories', {}).get(cat, {})
                cat_clin = cat_data.get('clinical_accuracy', 0)
                print(f"│    {cat}: {cat_clin:.0%}")
        
        print(f"└{'─' * 88}")
    
    return {
        'total_exact_accuracy': acc,
        'total_clinical_accuracy': clin,
        'category_exact_accuracy': cat_acc,
        'category_clinical_accuracy': cat_clin,
        'total_comparisons': total_windows,
        'category_comparisons': cat_total,
    }


# ============================================================================
# MAIN
# ============================================================================

def main():
    num_schedules = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    
    print("=" * 70)
    print("CATEGORY BREAKDOWN PIPELINE")
    print("=" * 70)
    print("Based on Stage2_Bestperformer (100% clinical accuracy)")
    print("Extended with category breakdown extraction")
    print(f"Running on {num_schedules} schedules...")
    
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    gt_all = load_category_ground_truth()
    
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
        
        if not gt:
            print(f"\n⚠️ No ground truth for schedule {schedule_id}")
            continue
        
        print(f"\n[{schedule_id}] Processing...")
        
        result = run_category_pipeline(client, pdf_path, schedule_id, gt)
        results.append(result)
        
        if 'error' not in result:
            m_a = result.get('metrics_A', {})
            m_b = result.get('metrics_B', {})
            cm_a = result.get('category_metrics_A', {})
            cm_b = result.get('category_metrics_B', {})
            
            print(f"  ✓ Total Clinical: A={m_a.get('clinical_accuracy', 0):.0%}, B={m_b.get('clinical_accuracy', 0):.0%}")
            print(f"  ✓ Category Clinical: A={cm_a.get('overall_clinical_accuracy', 0):.0%}, B={cm_b.get('overall_clinical_accuracy', 0):.0%}")
        else:
            print(f"  ✗ Error: {result['error']}")
        
        time.sleep(1)
    
    # Print comprehensive results
    metrics = print_results(results)
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(
        os.path.dirname(__file__), '..', '..', 'results',
        f'category_breakdown_results_{timestamp}.json'
    )
    
    output_data = {
        'experiment': 'category_breakdown_pipeline',
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

