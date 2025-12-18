#!/usr/bin/env python3
"""
Chained Split Window Extraction Experiment

This experiment tests a two-stage extraction approach:
1. First window: Pass PDF and extract up to 3 months (screening, 1_month, 3_months)
2. Second window: Pass PDF + output from first run, extract the rest (6_months, 9_months, 12_months)

The key difference from standard split windows is that the second call receives
context from the first call, which may help with consistency.

Usage:
    python3 experiments/split_window/chained_split_window.py [limit]
    
    limit: Optional number of PDFs to process (default: all)
"""

import os
import sys
import csv
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Error: google-genai not installed.")
    print("Run: pip install google-genai python-dotenv")
    exit(1)

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

# Import from core
from core.test_extraction import (
    load_ground_truth,
    extract_schedule_id,
    parse_json_response,
    map_arm_name_to_letter,
    TIME_WINDOWS,
)

# ============================================================================
# CONFIGURATION
# ============================================================================

MODEL = "gemini-3-flash-preview"  # Gemini 3 Flash
SCHEDULES_FOLDER = "synthetic_schedules"
GROUND_TRUTH_FILE = "synthetic_schedules/ground_truth.csv"
OUTPUT_DIR = "results"
TEMPERATURE = 0.1

# Define window splits
EARLY_WINDOWS = ['screening', '1_month', '3_months']
LATE_WINDOWS = ['6_months', '9_months', '12_months']

# ============================================================================
# PROMPTS
# ============================================================================

BASE_DEFINITIONS = """
**Healthcare Contact Day**: Any calendar day requiring in-person contact with the healthcare system (clinic visits, labs, imaging, infusions, procedures). Count each unique calendar day ONCE regardless of how many assessments occur that day.

**Cycle Mapping**: Map cycle structure to calendar days. For N-day cycles:
- C1D1 = Day 1
- C1D15 = Day 15 (if applicable)
- C2D1 = Day N+1
- C3D1 = Day 2N+1, etc.

**CRITICAL - Grouped Columns**: Columns like "C4-C12" represent MULTIPLE cycles. Expand by calculating visits for EACH cycle. Example: "C4-C12 D1" with 28-day cycles = 9 separate visit days.

**Arm-Specific Visits**: Look for superscripts like X^A meaning "Arm A only"
"""

PROMPT_FIRST_WINDOW = """
You are an expert clinical trial protocol analyst. Extract healthcare contact days for the EARLY time windows.

## DEFINITIONS
""" + BASE_DEFINITIONS + """

## TIME WINDOWS TO EXTRACT:
- screening: All pre-randomization/pre-treatment visits (before Day 1)
- 1_month: Day 1 through Day 30 after treatment start (CUMULATIVE from Day 1)
- 3_months: Day 1 through Day 90 (CUMULATIVE from Day 1)

Note: These are CUMULATIVE counts. 3_months includes all days from 1_month plus additional days through Day 90.

## EXTRACTION RULES
1. Identify all treatment arms (Arm A, Arm B)
2. Map cycle structure to calendar days
3. For grouped columns like "C4-C12", expand to individual cycles
4. Count unique visit days per arm
5. Handle arm-specific visits (X^A = Arm A only)
6. Include ALL visit types: Screening visits, Treatment visits

## OUTPUT FORMAT
Return ONLY valid JSON:
```json
[
  {
    "arm_name": "Arm A (Treatment Name)",
    "intervention_type": "intervention",
    "healthcare_contact_days": {
      "screening": <integer>,
      "1_month": <integer>,
      "3_months": <integer>
    },
    "extraction_notes": {
      "cycle_length_days": <integer>,
      "treatment_duration_months": <integer>,
      "visit_pattern": "<description of visit days per cycle>"
    }
  },
  {
    "arm_name": "Arm B (Control Name)",
    "intervention_type": "control",
    "healthcare_contact_days": {
      "screening": <integer>,
      "1_month": <integer>,
      "3_months": <integer>
    },
    "extraction_notes": {
      "cycle_length_days": <integer>,
      "treatment_duration_months": <integer>,
      "visit_pattern": "<description of visit days per cycle>"
    }
  }
]
```
"""

PROMPT_SECOND_WINDOW_TEMPLATE = """
You are an expert clinical trial protocol analyst. Continue extracting healthcare contact days for the LATE time windows.

## CONTEXT FROM FIRST EXTRACTION
I already extracted the early windows from this same PDF. Here are the results:

{first_window_output}

Use this context to ensure consistency in:
- Arm identification (same arm names)
- Cycle length and structure (same cycle_length_days)
- Visit pattern interpretation

## DEFINITIONS
""" + BASE_DEFINITIONS + """

## TIME WINDOWS TO EXTRACT:
- 6_months: Day 1 through Day 180 (CUMULATIVE from Day 1)
- 9_months: Day 1 through Day 270 (CUMULATIVE from Day 1)
- 12_months: Day 1 through Day 365 (CUMULATIVE from Day 1)

IMPORTANT: These are CUMULATIVE counts from Day 1, not incremental from the 3-month mark.
- 6_months should be >= 3_months from first extraction
- 9_months should be >= 6_months
- 12_months should be >= 9_months

## EXTRACTION RULES
1. Use the SAME arm identification as the first extraction
2. Use the SAME cycle length and structure
3. Continue the cycle-to-day mapping beyond Day 90
4. Include: Treatment visits through treatment duration, EOT visit, AND Follow-up visits (M9 FU, M12 FU if present)
5. For protocols with treatment < 12 months, count follow-up visits separately

## OUTPUT FORMAT
Return ONLY valid JSON (matching the arm structure from first extraction):
```json
[
  {{
    "arm_name": "Arm A (Treatment Name)",
    "intervention_type": "intervention",
    "healthcare_contact_days": {{
      "6_months": <integer>,
      "9_months": <integer>,
      "12_months": <integer>
    }}
  }},
  {{
    "arm_name": "Arm B (Control Name)",
    "intervention_type": "control",
    "healthcare_contact_days": {{
      "6_months": <integer>,
      "9_months": <integer>,
      "12_months": <integer>
    }}
  }}
]
```
"""

# ============================================================================
# EXTRACTION FUNCTIONS
# ============================================================================

def call_gemini(client: genai.Client, uploaded_file, prompt: str, temperature: float = TEMPERATURE) -> str:
    """Call Gemini with a PDF and prompt."""
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_uri(
                    file_uri=uploaded_file.uri,
                    mime_type="application/pdf"
                ),
                types.Part.from_text(text=prompt),
            ],
        ),
    ]
    
    generate_config = types.GenerateContentConfig(
        temperature=temperature,
    )
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=generate_config,
            )
            return response.text
        except Exception as e:
            error_msg = str(e).lower()
            if any(kw in error_msg for kw in ['overloaded', 'unavailable', 'rate', 'quota', '503', '429']):
                wait_time = 2 ** (attempt + 1)
                print(f"    Retry {attempt + 1}/{max_retries} in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise e
    return ""


def extract_chained_split_window(client: genai.Client, pdf_path: str) -> Optional[Dict[str, Any]]:
    """
    Extract healthcare contact days using chained split window approach.
    
    1. First call: Extract early windows (screening, 1_month, 3_months)
    2. Second call: Pass first output as context, extract late windows (6_months, 9_months, 12_months)
    """
    filename = os.path.basename(pdf_path)
    
    try:
        # Upload file
        uploaded_file = client.files.upload(file=pdf_path)
        
        # === FIRST WINDOW: Early extraction ===
        first_response = call_gemini(client, uploaded_file, PROMPT_FIRST_WINDOW)
        first_arms = parse_json_response(first_response)
        
        if not first_arms:
            print("    First window extraction failed")
            return None
        
        # Rate limiting
        time.sleep(1)
        
        # === SECOND WINDOW: Late extraction with context ===
        # Format first window output as context
        first_output_formatted = json.dumps(first_arms, indent=2)
        second_prompt = PROMPT_SECOND_WINDOW_TEMPLATE.format(first_window_output=first_output_formatted)
        
        second_response = call_gemini(client, uploaded_file, second_prompt)
        second_arms = parse_json_response(second_response)
        
        if not second_arms:
            print("    Second window extraction failed")
            return None
        
        # === MERGE RESULTS ===
        merged_arms = merge_window_results(first_arms, second_arms)
        
        return {
            'filename': filename,
            'schedule_id': extract_schedule_id(filename),
            'arms': merged_arms,
            'first_window_raw': first_arms,
            'second_window_raw': second_arms,
            'api_calls': 2,
        }
        
    except Exception as e:
        print(f"    Error: {e}")
        return None


def merge_window_results(first_arms: List[Dict], second_arms: List[Dict]) -> List[Dict]:
    """Merge early and late window results by matching arms."""
    merged_arms = []
    
    for first_arm in first_arms:
        arm_name = first_arm.get('arm_name', '')
        intervention_type = first_arm.get('intervention_type', '')
        first_letter = map_arm_name_to_letter(arm_name, intervention_type)
        
        # Find matching arm in second window results
        second_arm = None
        for sa in second_arms:
            second_letter = map_arm_name_to_letter(
                sa.get('arm_name', ''),
                sa.get('intervention_type', '')
            )
            if second_letter == first_letter:
                second_arm = sa
                break
        
        # Merge healthcare_contact_days
        merged_days = first_arm.get('healthcare_contact_days', {}).copy()
        if second_arm:
            merged_days.update(second_arm.get('healthcare_contact_days', {}))
        
        merged_arms.append({
            'arm_name': arm_name,
            'intervention_type': intervention_type,
            'healthcare_contact_days': merged_days,
            'extraction_notes': first_arm.get('extraction_notes', {}),
        })
    
    return merged_arms


# ============================================================================
# COMPARISON AND METRICS
# ============================================================================

def compare_single(extracted: Dict[str, Any], ground_truth: Dict) -> Dict[str, Any]:
    """Compare extracted results against ground truth for a single schedule."""
    schedule_id = extracted['schedule_id']
    
    if schedule_id not in ground_truth:
        return {'schedule_id': schedule_id, 'error': 'Not in ground truth'}
    
    gt = ground_truth[schedule_id]
    results = {'schedule_id': schedule_id, 'arms': {}}
    
    for arm_data in extracted['arms']:
        arm_letter = map_arm_name_to_letter(
            arm_data.get('arm_name', ''),
            arm_data.get('intervention_type', '')
        )
        
        if arm_letter not in gt:
            results['arms'][arm_letter] = {'error': 'Arm not in ground truth'}
            continue
        
        gt_arm = gt[arm_letter]
        extracted_days = arm_data.get('healthcare_contact_days', {})
        
        arm_results = {'windows': {}}
        for window in TIME_WINDOWS:
            gt_val = gt_arm.get(window, 0)
            ext_val = extracted_days.get(window, 0)
            if isinstance(ext_val, str):
                ext_val = int(ext_val) if ext_val.isdigit() else 0
            
            arm_results['windows'][window] = {
                'gt': gt_val,
                'ext': ext_val,
                'diff': ext_val - gt_val,
                'match': ext_val == gt_val,
                'within_3': abs(ext_val - gt_val) <= 3,
            }
        
        arm_results['complexity'] = gt_arm.get('complexity', 'unknown')
        arm_results['disease'] = gt_arm.get('disease', 'unknown')
        results['arms'][arm_letter] = arm_results
    
    return results


def calculate_overall_metrics(all_comparisons: List[Dict]) -> Dict[str, Any]:
    """Calculate overall accuracy metrics."""
    total = 0
    exact_match = 0
    within_3 = 0
    total_error = 0
    
    # Per-window stats
    window_stats = {w: {'total': 0, 'exact': 0, 'within_3': 0, 'errors': []} for w in TIME_WINDOWS}
    
    # Per-complexity stats
    complexity_stats = {
        'simple': {'total': 0, 'exact': 0, 'within_3': 0},
        'moderate': {'total': 0, 'exact': 0, 'within_3': 0},
        'complex': {'total': 0, 'exact': 0, 'within_3': 0},
    }
    
    for result in all_comparisons:
        if 'error' in result:
            continue
        
        for arm_letter, arm_data in result.get('arms', {}).items():
            if 'error' in arm_data:
                continue
            
            complexity = arm_data.get('complexity', 'unknown')
            
            for window, data in arm_data.get('windows', {}).items():
                total += 1
                window_stats[window]['total'] += 1
                
                if complexity in complexity_stats:
                    complexity_stats[complexity]['total'] += 1
                
                if data['match']:
                    exact_match += 1
                    within_3 += 1
                    window_stats[window]['exact'] += 1
                    window_stats[window]['within_3'] += 1
                    if complexity in complexity_stats:
                        complexity_stats[complexity]['exact'] += 1
                        complexity_stats[complexity]['within_3'] += 1
                else:
                    abs_diff = abs(data['diff'])
                    total_error += abs_diff
                    window_stats[window]['errors'].append(abs_diff)
                    
                    if data['within_3']:
                        within_3 += 1
                        window_stats[window]['within_3'] += 1
                        if complexity in complexity_stats:
                            complexity_stats[complexity]['within_3'] += 1
    
    return {
        'total': total,
        'exact_match': exact_match,
        'within_3': within_3,
        'exact_accuracy': exact_match / total if total > 0 else 0,
        'clinical_accuracy': within_3 / total if total > 0 else 0,
        'mae': total_error / total if total > 0 else 0,
        'window_stats': window_stats,
        'complexity_stats': complexity_stats,
    }


# ============================================================================
# OUTPUT FUNCTIONS
# ============================================================================

def print_results_table(all_comparisons: List[Dict]):
    """Print a formatted results table."""
    print("\n" + "=" * 90)
    print("DETAILED RESULTS")
    print("=" * 90)
    print(f"{'ID':>4} {'Arm':>4} | {'Scr':>4} {'1M':>4} {'3M':>4} | {'6M':>4} {'9M':>4} {'12M':>5} | {'Exact':>6} {'±3':>4}")
    print("-" * 90)
    
    for result in sorted(all_comparisons, key=lambda x: x['schedule_id']):
        if 'error' in result:
            print(f"{result['schedule_id']:>4} ERROR: {result['error']}")
            continue
        
        for arm_letter in ['A', 'B']:
            if arm_letter not in result.get('arms', {}):
                continue
            
            arm_data = result['arms'][arm_letter]
            if 'error' in arm_data:
                continue
            
            windows = arm_data['windows']
            
            # Format each window result
            row = [result['schedule_id'], arm_letter]
            exact_count = 0
            within_3_count = 0
            
            # Early windows
            for window in EARLY_WINDOWS:
                data = windows[window]
                diff = data['diff']
                if diff == 0:
                    row.append("✓")
                    exact_count += 1
                    within_3_count += 1
                elif abs(diff) <= 3:
                    row.append(f"{diff:+d}")
                    within_3_count += 1
                else:
                    row.append(f"*{diff:+d}*")
            
            # Late windows
            for window in LATE_WINDOWS:
                data = windows[window]
                diff = data['diff']
                if diff == 0:
                    row.append("✓")
                    exact_count += 1
                    within_3_count += 1
                elif abs(diff) <= 3:
                    row.append(f"{diff:+d}")
                    within_3_count += 1
                else:
                    row.append(f"*{diff:+d}*")
            
            row.append(f"{exact_count}/6")
            row.append(f"{within_3_count}/6")
            
            print(f"{row[0]:>4} {row[1]:>4} | {row[2]:>4} {row[3]:>4} {row[4]:>4} | {row[5]:>4} {row[6]:>4} {row[7]:>5} | {row[8]:>6} {row[9]:>4}")


def save_json_results(all_results: List[Dict], all_comparisons: List[Dict], metrics: Dict, output_dir: str):
    """Save full results as JSON for later analysis."""
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    
    output = {
        'experiment': 'chained_split_window',
        'timestamp': datetime.now().isoformat(),
        'model': MODEL,
        'temperature': TEMPERATURE,
        'description': 'Two-stage extraction: First window (up to 3 months), Second window (rest with context)',
        'metrics': metrics,
        'per_schedule': all_comparisons,
        'raw_extractions': all_results,
    }
    
    json_file = os.path.join(output_dir, f"chained_split_window_results_{timestamp}.json")
    with open(json_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\nJSON results saved to: {json_file}")
    return json_file


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 70)
    print("CHAINED SPLIT WINDOW EXTRACTION EXPERIMENT")
    print("=" * 70)
    print(f"Model: {MODEL}")
    print(f"Temperature: {TEMPERATURE}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("Approach:")
    print("  1. First Window: PDF → Extract screening, 1_month, 3_months")
    print("  2. Second Window: PDF + First Output → Extract 6_months, 9_months, 12_months")
    print("=" * 70)
    
    # Setup client
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set.")
        sys.exit(1)
    
    client = genai.Client(api_key=api_key)
    
    # Load ground truth
    if not os.path.exists(GROUND_TRUTH_FILE):
        print(f"Error: Ground truth file not found: {GROUND_TRUTH_FILE}")
        sys.exit(1)
    
    ground_truth = load_ground_truth(GROUND_TRUTH_FILE)
    print(f"Loaded ground truth for {len(ground_truth)} schedules")
    
    # Find all PDFs
    pdf_folder = Path(SCHEDULES_FOLDER)
    pdf_files = sorted(pdf_folder.glob("*.pdf"))
    
    if not pdf_files:
        print(f"Error: No PDF files found in {SCHEDULES_FOLDER}")
        sys.exit(1)
    
    # Handle optional limit
    limit = None
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
            pdf_files = pdf_files[:limit]
        except ValueError:
            pass
    
    print(f"Processing {len(pdf_files)} PDF files")
    print("-" * 70)
    
    # Process all PDFs
    all_results = []
    all_comparisons = []
    total_api_calls = 0
    
    for i, pdf_path in enumerate(pdf_files, 1):
        filename = os.path.basename(pdf_path)
        schedule_id = extract_schedule_id(filename)
        print(f"[{i:2d}/{len(pdf_files)}] {filename}...", end=" ", flush=True)
        
        result = extract_chained_split_window(client, str(pdf_path))
        
        if result:
            all_results.append(result)
            comparison = compare_single(result, ground_truth)
            all_comparisons.append(comparison)
            total_api_calls += result.get('api_calls', 2)
            
            # Quick summary
            exact = 0
            total = 0
            for arm_data in comparison.get('arms', {}).values():
                if 'windows' in arm_data:
                    for w_data in arm_data['windows'].values():
                        total += 1
                        if w_data['match']:
                            exact += 1
            print(f"✓ ({exact}/{total} exact)")
        else:
            print("✗ Failed")
            all_comparisons.append({'schedule_id': schedule_id, 'error': 'Extraction failed'})
        
        # Rate limiting between PDFs
        time.sleep(1)
    
    # Calculate metrics
    print("\n" + "=" * 70)
    print("CALCULATING METRICS")
    print("=" * 70)
    
    metrics = calculate_overall_metrics(all_comparisons)
    
    # Print summary
    print(f"\nOverall Exact Match Accuracy: {metrics['exact_accuracy']:.1%}")
    print(f"Clinical Accuracy (±3 days): {metrics['clinical_accuracy']:.1%}")
    print(f"Mean Absolute Error: {metrics['mae']:.2f} days")
    print(f"Total Comparisons: {metrics['total']}")
    print(f"Total API Calls: {total_api_calls}")
    
    print("\nPer-Window Accuracy:")
    print(f"  {'Window':12s} | {'Exact':>8} | {'±3 Days':>8} | {'MAE':>6}")
    print(f"  {'-'*12}-+-{'-'*8}-+-{'-'*8}-+-{'-'*6}")
    for window in TIME_WINDOWS:
        stats = metrics['window_stats'][window]
        exact_acc = stats['exact'] / stats['total'] if stats['total'] > 0 else 0
        clin_acc = stats['within_3'] / stats['total'] if stats['total'] > 0 else 0
        mae = sum(stats['errors']) / len(stats['errors']) if stats['errors'] else 0
        print(f"  {window:12s} | {exact_acc:7.1%} | {clin_acc:7.1%} | {mae:6.2f}")
    
    print("\nPer-Complexity Accuracy:")
    for complexity in ['simple', 'moderate', 'complex']:
        stats = metrics['complexity_stats'][complexity]
        if stats['total'] > 0:
            exact_acc = stats['exact'] / stats['total']
            clin_acc = stats['within_3'] / stats['total']
            print(f"  {complexity:10s}: {exact_acc:5.1%} exact | {clin_acc:5.1%} ±3 days (n={stats['total']})")
    
    # Print detailed results table
    print_results_table(all_comparisons)
    
    # Create output directory and save results
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("\n" + "=" * 70)
    print("SAVING RESULTS")
    print("=" * 70)
    
    json_file = save_json_results(all_results, all_comparisons, metrics, OUTPUT_DIR)
    
    print("\n" + "=" * 70)
    print("COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()

