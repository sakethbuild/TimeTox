#!/usr/bin/env python3
"""
TimeTox Validation Script

Tests the Gemini-based extraction pipeline against synthetic schedules
with known ground truth values.

Usage:
    1. Set your API key: export GEMINI_API_KEY="your_key_here"
    2. Run: python3 test_extraction.py
"""

import os
import csv
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Error: google-genai not installed.")
    print("Run: pip install google-genai python-dotenv")
    exit(1)

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
    print("Loaded .env file")
except ImportError:
    print("python-dotenv not installed, using system environment variables")


# ============================================================================
# CONFIGURATION
# ============================================================================

MODEL = "gemini-3-flash-preview"  # Gemini 3 Pro with advanced reasoning
SCHEDULES_FOLDER = "synthetic_schedules"
GROUND_TRUTH_FILE = "synthetic_schedules/ground_truth.csv"
OUTPUT_CSV = "extraction_results.csv"
VALIDATION_REPORT = "validation_report.md"

# Time windows to extract (matching ground truth columns)
TIME_WINDOWS = ['screening', '1_month', '3_months', '6_months', '9_months', '12_months']

# Map ground truth columns to extraction windows
GT_TO_EXTRACTION = {
    'screening_days': 'screening',
    'month1_days': '1_month',
    'month3_days': '3_months',
    'month6_days': '6_months',
    'month9_days': '9_months',
    'month12_days': '12_months',
}


# ============================================================================
# EXTRACTION PROMPT (based on reference script)
# ============================================================================

EXTRACTION_PROMPT = """
You are an expert clinical trial protocol analyst. Your task is to extract healthcare contact days from the Schedule of Assessments (SoA) table.

## DEFINITIONS

**Healthcare Contact Day**: Any calendar day requiring in-person contact with the healthcare system (clinic visits, labs, imaging, infusions, procedures). Count each unique calendar day ONCE regardless of how many assessments occur that day.

**Time Windows**:
- screening: All pre-randomization/pre-treatment visits
- 1_month: Day 1 through Day 30 after treatment start
- 3_months: Day 1 through Day 90
- 6_months: Day 1 through Day 180
- 9_months: Day 1 through Day 270
- 12_months: Day 1 through Day 365

## EXTRACTION RULES

1. **Identify all treatment arms** from the table (look for Arm A, Arm B, intervention vs control)
2. **Map cycle structure** to calendar days (e.g., 28-day cycles: C1D1=Day 1, C1D15=Day 15, C2D1=Day 29, etc.)
3. **CRITICAL - Expand grouped columns**: Columns like "C4-C12" or "C4-C6" represent MULTIPLE cycles. You must expand these by calculating visits for EACH cycle in the range. Example: "C4-C12 D1" = 9 separate visit days (C4D1, C5D1, C6D1, C7D1, C8D1, C9D1, C10D1, C11D1, C12D1)
4. **Count unique visit days** - if multiple assessments occur on the same day, count as ONE contact day
5. **Handle arm-specific visits**: Look for superscripts like X^A meaning "Arm A only"
6. **Count ALL visit types**: Include Screening visits (often 1-2 days), Treatment visits, EOT (End of Treatment) visit, AND Follow-up visits (M9 FU, M12 FU)
7. **Verify cycle math**: For N-day cycles over M months: total cycles ≈ (M × 30) / N. Ensure your counts reflect this.

## CATEGORY DEFINITIONS (for breakdown)

- **core_treatment**: Drug administration, infusions, treatment procedures
- **imaging_diagnostics**: CT, MRI, PET, X-ray, ultrasound, ECG, ECHO
- **labs**: Blood draws, urinalysis, biomarkers
- **clinic_visits**: Physical exam, vital signs, assessments without above procedures

Note: If a visit day includes multiple categories, assign to highest priority:
core_treatment > imaging_diagnostics > labs > clinic_visits

## OUTPUT FORMAT

Return ONLY valid JSON in this exact structure:

```json
[
  {
    "arm_name": "Arm A (Treatment Name)",
    "intervention_type": "intervention",
    "healthcare_contact_days": {
      "screening": <integer>,
      "1_month": <integer>,
      "3_months": <integer>,
      "6_months": <integer>,
      "9_months": <integer>,
      "12_months": <integer>
    },
    "category_breakdown": {
      "core_treatment": {
        "screening": 0, "1_month": 0, "3_months": 0, "6_months": 0, "9_months": 0, "12_months": 0
      },
      "imaging_diagnostics": {
        "screening": 0, "1_month": 0, "3_months": 0, "6_months": 0, "9_months": 0, "12_months": 0
      },
      "labs": {
        "screening": 0, "1_month": 0, "3_months": 0, "6_months": 0, "9_months": 0, "12_months": 0
      },
      "clinic_visits": {
        "screening": 0, "1_month": 0, "3_months": 0, "6_months": 0, "9_months": 0, "12_months": 0
      }
    },
    "extraction_notes": {
      "cycle_length_days": <integer>,
      "treatment_duration_months": <integer>,
      "visit_pattern": "<description of visit days per cycle>",
      "assumptions": ["<any assumptions made>"]
    }
  },
  {
    "arm_name": "Arm B (Control Name)",
    "intervention_type": "control",
    ...
  }
]
```

## VALIDATION CHECKLIST (verify before responding)
- Each calendar date counted exactly once
- Category sums equal total healthcare_contact_days for each window
- Arm-specific visits (X^A) only counted for that arm
- Cycle math is correct (e.g., 28-day cycles: C2D1 = Day 29, not Day 28)

NOW ANALYZE THE PROVIDED SCHEDULE OF ASSESSMENTS.
"""


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def load_ground_truth(filepath: str) -> Dict[str, Dict[str, Dict[str, int]]]:
    """
    Load ground truth CSV into nested dict structure.
    Returns: {schedule_id: {arm: {window: days}}}
    """
    ground_truth = {}
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            schedule_id = row['schedule_id']
            arm = row['arm']
            
            if schedule_id not in ground_truth:
                ground_truth[schedule_id] = {}
            
            ground_truth[schedule_id][arm] = {
                'screening': int(row['screening_days']),
                '1_month': int(row['month1_days']),
                '3_months': int(row['month3_days']),
                '6_months': int(row['month6_days']),
                '9_months': int(row['month9_days']),
                '12_months': int(row['month12_days']),
                'category': row['category'],
                'disease': row['disease'],
                'complexity': row['complexity'],
            }
    
    return ground_truth


def extract_schedule_id(filename: str) -> str:
    """Extract schedule ID from filename like 'synthetic_schedule_01_complex_two.pdf'"""
    match = re.search(r'synthetic_schedule_(\d+)', filename)
    return match.group(1) if match else filename


def parse_json_response(response_text: str) -> List[Dict[str, Any]]:
    """Parse JSON from Gemini response, handling markdown code blocks."""
    # Try to find JSON in code blocks
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
    if json_match:
        json_str = json_match.group(1)
    else:
        # Try to find raw JSON array
        json_match = re.search(r'\[\s*\{[\s\S]*\}\s*\]', response_text)
        if json_match:
            json_str = json_match.group(0)
        else:
            print("Warning: Could not find JSON in response")
            return []
    
    try:
        parsed = json.loads(json_str)
        if isinstance(parsed, list):
            return parsed
        elif isinstance(parsed, dict):
            return [parsed]
        else:
            return []
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        return []


def map_arm_name_to_letter(arm_name: str, intervention_type: str) -> str:
    """Map extracted arm name to A/B based on intervention type."""
    if 'intervention' in intervention_type.lower():
        return 'A'
    elif 'control' in intervention_type.lower():
        return 'B'
    elif 'a' in arm_name.lower().split()[0] if arm_name else '':
        return 'A'
    else:
        return 'B'


# ============================================================================
# GEMINI API FUNCTIONS
# ============================================================================

def setup_gemini_client() -> genai.Client:
    """Initialize Gemini client with API key."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set.")
        print("Set it with: export GEMINI_API_KEY='your_key_here'")
        exit(1)
    
    return genai.Client(api_key=api_key)


def process_pdf(client: genai.Client, pdf_path: str) -> Optional[Dict[str, Any]]:
    """
    Process a single PDF through Gemini and extract healthcare contact days.
    """
    filename = os.path.basename(pdf_path)
    print(f"\nProcessing: {filename}")
    
    try:
        # Upload file directly to Gemini
        uploaded_file = client.files.upload(file=pdf_path)
        print(f"  Uploaded: {uploaded_file.uri}")
        
        # Build content with PDF and prompt
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_uri(
                        file_uri=uploaded_file.uri,
                        mime_type="application/pdf"
                    ),
                    types.Part.from_text(text=EXTRACTION_PROMPT),
                ],
            ),
        ]
        
        # Configure generation
        generate_config = types.GenerateContentConfig(
            temperature=0.1,  # Low temperature for consistent extraction
        )
        
        # Generate response with retry logic
        response_text = ""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=MODEL,
                    contents=contents,
                    config=generate_config,
                )
                response_text = response.text
                break
            except Exception as e:
                error_msg = str(e).lower()
                print(f"  API Error: {e}")
                if any(kw in error_msg for kw in ['overloaded', 'unavailable', 'rate', 'quota', '503', '429']):
                    wait_time = 2 ** attempt
                    print(f"  Retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    raise e
        
        if not response_text:
            print(f"  Error: No response received")
            return None
        
        # Parse response
        parsed_arms = parse_json_response(response_text)
        
        if parsed_arms:
            schedule_id = extract_schedule_id(filename)
            print(f"  ✓ Extracted {len(parsed_arms)} arm(s)")
            return {
                'filename': filename,
                'schedule_id': schedule_id,
                'arms': parsed_arms,
                'raw_response': response_text
            }
        else:
            print(f"  ✗ Failed to parse response")
            print(f"  Raw response preview: {response_text[:500]}...")
            return None
    
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        return None


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def compare_results(
    extracted: Dict[str, Any], 
    ground_truth: Dict[str, Dict[str, Dict[str, int]]]
) -> Dict[str, Any]:
    """
    Compare extracted results against ground truth.
    Returns comparison metrics.
    """
    schedule_id = extracted['schedule_id']
    
    if schedule_id not in ground_truth:
        return {'error': f'Schedule {schedule_id} not in ground truth'}
    
    gt = ground_truth[schedule_id]
    comparisons = []
    
    for arm_data in extracted['arms']:
        arm_letter = map_arm_name_to_letter(
            arm_data.get('arm_name', ''),
            arm_data.get('intervention_type', '')
        )
        
        if arm_letter not in gt:
            comparisons.append({
                'arm': arm_letter,
                'error': f'Arm {arm_letter} not in ground truth'
            })
            continue
        
        gt_arm = gt[arm_letter]
        extracted_days = arm_data.get('healthcare_contact_days', {})
        
        arm_comparison = {
            'arm': arm_letter,
            'arm_name': arm_data.get('arm_name', ''),
            'windows': {}
        }
        
        for window in TIME_WINDOWS:
            gt_value = gt_arm.get(window, 0)
            ext_value = extracted_days.get(window, 0)
            if isinstance(ext_value, str):
                ext_value = int(ext_value) if ext_value.isdigit() else 0
            
            arm_comparison['windows'][window] = {
                'ground_truth': gt_value,
                'extracted': ext_value,
                'difference': ext_value - gt_value,
                'match': ext_value == gt_value
            }
        
        comparisons.append(arm_comparison)
    
    return {
        'schedule_id': schedule_id,
        'comparisons': comparisons
    }


def calculate_metrics(all_comparisons: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate overall accuracy metrics including clinically significant threshold."""
    total_windows = 0
    correct_windows = 0
    within_3_days = 0  # New: clinically significant threshold
    total_error = 0
    window_stats = {w: {'correct': 0, 'within_3': 0, 'total': 0, 'errors': []} for w in TIME_WINDOWS}
    
    for result in all_comparisons:
        if 'error' in result:
            continue
        
        for arm_comp in result.get('comparisons', []):
            if 'error' in arm_comp:
                continue
            
            for window, data in arm_comp.get('windows', {}).items():
                total_windows += 1
                window_stats[window]['total'] += 1
                abs_diff = abs(data['difference'])
                
                if data['match']:
                    correct_windows += 1
                    within_3_days += 1
                    window_stats[window]['correct'] += 1
                    window_stats[window]['within_3'] += 1
                else:
                    total_error += abs_diff
                    window_stats[window]['errors'].append(data['difference'])
                    # Check if within clinically significant threshold
                    if abs_diff <= 3:
                        within_3_days += 1
                        window_stats[window]['within_3'] += 1
    
    accuracy = correct_windows / total_windows if total_windows > 0 else 0
    clinical_accuracy = within_3_days / total_windows if total_windows > 0 else 0
    mae = total_error / total_windows if total_windows > 0 else 0
    
    window_accuracy = {}
    for window in TIME_WINDOWS:
        stats = window_stats[window]
        window_accuracy[window] = {
            'accuracy': stats['correct'] / stats['total'] if stats['total'] > 0 else 0,
            'within_3_accuracy': stats['within_3'] / stats['total'] if stats['total'] > 0 else 0,
            'total': stats['total'],
            'correct': stats['correct'],
            'within_3': stats['within_3'],
            'mean_error': sum(abs(e) for e in stats['errors']) / len(stats['errors']) if stats['errors'] else 0
        }
    
    return {
        'overall_accuracy': accuracy,
        'clinical_accuracy': clinical_accuracy,  # Within ±3 days
        'mean_absolute_error': mae,
        'total_comparisons': total_windows,
        'correct_predictions': correct_windows,
        'within_3_predictions': within_3_days,
        'window_accuracy': window_accuracy
    }


# ============================================================================
# OUTPUT FUNCTIONS
# ============================================================================

def save_extraction_results(results: List[Dict[str, Any]], filepath: str):
    """Save raw extraction results to CSV."""
    headers = [
        'filename', 'schedule_id', 'arm_name', 'intervention_type',
        'screening', '1_month', '3_months', '6_months', '9_months', '12_months',
        'cycle_length_days', 'visit_pattern'
    ]
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        
        for result in results:
            for arm in result.get('arms', []):
                days = arm.get('healthcare_contact_days', {})
                notes = arm.get('extraction_notes', {})
                
                row = [
                    result.get('filename', ''),
                    result.get('schedule_id', ''),
                    arm.get('arm_name', ''),
                    arm.get('intervention_type', ''),
                    days.get('screening', ''),
                    days.get('1_month', ''),
                    days.get('3_months', ''),
                    days.get('6_months', ''),
                    days.get('9_months', ''),
                    days.get('12_months', ''),
                    notes.get('cycle_length_days', ''),
                    notes.get('visit_pattern', ''),
                ]
                writer.writerow(row)
    
    print(f"\nExtraction results saved to: {filepath}")


def generate_validation_report(
    all_comparisons: List[Dict[str, Any]], 
    metrics: Dict[str, Any],
    filepath: str
):
    """Generate markdown validation report."""
    report = f"""# TimeTox Extraction Validation Report

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Overall Metrics

| Metric | Value |
|--------|-------|
| Exact Match Accuracy | {metrics['overall_accuracy']:.1%} |
| Clinical Accuracy (±3 days) | {metrics['clinical_accuracy']:.1%} |
| Mean Absolute Error | {metrics['mean_absolute_error']:.2f} days |
| Total Comparisons | {metrics['total_comparisons']} |
| Exact Matches | {metrics['correct_predictions']} |
| Within ±3 Days | {metrics['within_3_predictions']} |

## Accuracy by Time Window

| Window | Exact Match | Within ±3 Days | Mean Error |
|--------|-------------|----------------|------------|
"""
    
    for window in TIME_WINDOWS:
        stats = metrics['window_accuracy'][window]
        report += f"| {window} | {stats['accuracy']:.1%} ({stats['correct']}/{stats['total']}) | {stats['within_3_accuracy']:.1%} ({stats['within_3']}/{stats['total']}) | {stats['mean_error']:.2f} |\n"
    
    report += "\n## Per-Schedule Results\n\n"
    
    for result in all_comparisons:
        schedule_id = result.get('schedule_id', 'Unknown')
        report += f"### Schedule {schedule_id}\n\n"
        
        if 'error' in result:
            report += f"Error: {result['error']}\n\n"
            continue
        
        for arm_comp in result.get('comparisons', []):
            if 'error' in arm_comp:
                report += f"- Arm {arm_comp['arm']}: {arm_comp['error']}\n"
                continue
            
            arm_name = arm_comp.get('arm_name', arm_comp['arm'])
            report += f"**{arm_name}**\n\n"
            report += "| Window | Ground Truth | Extracted | Diff | Match |\n"
            report += "|--------|--------------|-----------|------|-------|\n"
            
            for window, data in arm_comp.get('windows', {}).items():
                match_icon = "✓" if data['match'] else "✗"
                diff_str = f"+{data['difference']}" if data['difference'] > 0 else str(data['difference'])
                report += f"| {window} | {data['ground_truth']} | {data['extracted']} | {diff_str} | {match_icon} |\n"
            
            report += "\n"
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"Validation report saved to: {filepath}")


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main entry point."""
    print("=" * 60)
    print("TimeTox Extraction Validation")
    print("=" * 60)
    
    # Setup
    client = setup_gemini_client()
    print(f"Using model: {MODEL}")
    
    # Load ground truth
    if not os.path.exists(GROUND_TRUTH_FILE):
        print(f"Error: Ground truth file not found: {GROUND_TRUTH_FILE}")
        return
    
    ground_truth = load_ground_truth(GROUND_TRUTH_FILE)
    print(f"Loaded ground truth for {len(ground_truth)} schedules")
    
    # Find PDFs to process
    pdf_folder = Path(SCHEDULES_FOLDER)
    pdf_files = sorted(pdf_folder.glob("*.pdf"))
    
    if not pdf_files:
        print(f"Error: No PDF files found in {SCHEDULES_FOLDER}")
        return
    
    print(f"Found {len(pdf_files)} PDF files to process")
    
    # Check for command line argument or default to 1 for testing
    import sys
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        limit = int(sys.argv[1])
        pdf_files = pdf_files[:limit]
        print(f"\nProcessing {len(pdf_files)} PDFs (from command line)...")
    else:
        # Default to 1 for quick testing
        pdf_files = pdf_files[:1]
        print(f"\nProcessing 1 PDF (default). Use 'python3 test_extraction.py N' to process N PDFs.")
    
    # Process each PDF
    all_results = []
    all_comparisons = []
    
    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"\n[{i}/{len(pdf_files)}] ", end="")
        
        result = process_pdf(client, str(pdf_path))
        
        if result:
            all_results.append(result)
            comparison = compare_results(result, ground_truth)
            all_comparisons.append(comparison)
            
            # Quick summary
            for comp in comparison.get('comparisons', []):
                if 'windows' in comp:
                    matches = sum(1 for w in comp['windows'].values() if w['match'])
                    total = len(comp['windows'])
                    print(f"    {comp['arm']}: {matches}/{total} windows correct")
        
        # Rate limiting
        time.sleep(1)
    
    # Save results
    print("\n" + "=" * 60)
    print("SAVING RESULTS")
    print("=" * 60)
    
    if all_results:
        save_extraction_results(all_results, OUTPUT_CSV)
    
    if all_comparisons:
        metrics = calculate_metrics(all_comparisons)
        generate_validation_report(all_comparisons, metrics, VALIDATION_REPORT)
        
        # Print summary
        print("\n" + "=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)
        print(f"Exact Match Accuracy: {metrics['overall_accuracy']:.1%}")
        print(f"Clinical Accuracy (±3 days): {metrics['clinical_accuracy']:.1%}")
        print(f"Mean Absolute Error: {metrics['mean_absolute_error']:.2f} days")
        print(f"Exact Matches: {metrics['correct_predictions']}/{metrics['total_comparisons']}")
        print(f"Within ±3 Days: {metrics['within_3_predictions']}/{metrics['total_comparisons']}")
        
        print("\nPer-Window Accuracy (Exact | ±3 days):")
        for window in TIME_WINDOWS:
            stats = metrics['window_accuracy'][window]
            print(f"  {window}: {stats['accuracy']:.1%} | {stats['within_3_accuracy']:.1%}")


if __name__ == "__main__":
    main()

