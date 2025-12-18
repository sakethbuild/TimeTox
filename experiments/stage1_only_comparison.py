#!/usr/bin/env python3
"""
Stage 1 Only Comparison

Runs Stage 1 (structure extraction) on first 5 PDFs, calculates visit counts
from the extracted structure, and compares to ground truth.

This shows the baseline before adding Stage 2 and Stage 3.
"""

import os
import json
import re
import time
import csv
import math
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

MODEL = "gemini-3-flash-preview"
WINDOWS = ['screening', '1_month', '3_months', '6_months', '9_months', '12_months']

# Stage 1 prompt
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


def load_ground_truth(filepath: str):
    """Load ground truth CSV."""
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
            }
    return ground_truth


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


def calculate_visits_from_structure(structure):
    """
    Calculate visit counts from Stage 1 extracted structure.
    Implements the Stage 2 calculation logic in Python.
    """
    if not structure:
        return []
    
    protocol_info = structure.get('protocol_info', {})
    treatment_duration_months = protocol_info.get('treatment_duration_months', 12)
    special_visits = structure.get('special_visits', {})
    screening_days = special_visits.get('screening_days', 2)
    has_eot = special_visits.get('eot_visit', True)
    has_m9_fu = special_visits.get('m9_followup', True)
    has_m12_fu = special_visits.get('m12_followup', True)
    
    results = []
    
    for arm_data in structure.get('arms', []):
        arm_name = arm_data.get('arm_name', '')
        cycle_length = arm_data.get('cycle_length_days', 28)
        visit_days_per_cycle = arm_data.get('visit_days_per_cycle', [])
        
        # Calculate total cycles (use 365 days for 12 months)
        total_days = treatment_duration_months * 30
        total_cycles = math.floor(total_days / cycle_length)
        
        # Generate all visit days across all cycles
        all_visit_days = []
        for cycle in range(1, total_cycles + 1):
            cycle_start_day = (cycle - 1) * cycle_length + 1
            for visit_day in visit_days_per_cycle:
                calendar_day = cycle_start_day + (visit_day - 1)
                if calendar_day <= 365:  # Only count up to 12 months
                    all_visit_days.append(calendar_day)
        
        # Count visits per window
        screening = screening_days
        month1 = screening + sum(1 for d in all_visit_days if 1 <= d <= 30)
        month3 = screening + sum(1 for d in all_visit_days if 1 <= d <= 90)
        month6 = screening + sum(1 for d in all_visit_days if 1 <= d <= 180)
        
        # For 9 months, add EOT if treatment ends around there
        month9 = screening + sum(1 for d in all_visit_days if 1 <= d <= 270)
        if has_eot and total_days <= 270:
            month9 += 1
        if has_m9_fu:
            month9 += 1
        
        # For 12 months, include everything
        month12 = screening + len(all_visit_days)
        if has_eot:
            month12 += 1
        if has_m9_fu:
            month12 += 1
        if has_m12_fu:
            month12 += 1
        
        results.append({
            'arm_name': arm_name,
            'healthcare_contact_days': {
                'screening': screening,
                '1_month': month1,
                '3_months': month3,
                '6_months': month6,
                '9_months': month9,
                '12_months': month12
            },
            'calculation_breakdown': {
                'total_cycles': total_cycles,
                'treatment_visits': len(all_visit_days),
                'screening_visits': screening,
                'eot_visits': 1 if has_eot else 0,
                'followup_visits': (1 if has_m9_fu else 0) + (1 if has_m12_fu else 0),
                'total_visits': month12
            }
        })
    
    return results


def main():
    print("=" * 70)
    print("STAGE 1 ONLY COMPARISON (First 5 PDFs)")
    print("=" * 70)
    
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    # Load ground truth
    ground_truth = load_ground_truth("synthetic_schedules/ground_truth.csv")
    
    # Get first 5 PDFs
    pdf_folder = Path("synthetic_schedules")
    pdf_files = sorted(pdf_folder.glob("*.pdf"))[:5]
    
    print(f"\nProcessing {len(pdf_files)} PDFs...\n")
    
    all_results = []
    
    for i, pdf_path in enumerate(pdf_files, 1):
        filename = pdf_path.name
        match = re.search(r'schedule_(\d+)', filename)
        schedule_id = match.group(1) if match else '01'
        
        print(f"[{i}/{len(pdf_files)}] Schedule {schedule_id}: {filename}")
        
        # Upload PDF
        print(f"  Uploading...", end=" ")
        uploaded = client.files.upload(file=str(pdf_path))
        print(f"✓")
        
        # Stage 1: Extract structure
        print(f"  Stage 1: Extracting structure...", end=" ")
        stage1_response = call_api(client, uploaded, PROMPT_STAGE1)
        structure = parse_json(stage1_response)
        
        if not structure:
            print("✗ Failed to parse structure")
            print(f"  Raw response: {stage1_response[:200] if stage1_response else 'None'}...")
            continue
        
        print("✓")
        
        # Calculate visits from structure
        calculated_results = calculate_visits_from_structure(structure)
        
        if not calculated_results:
            print("  ✗ Failed to calculate visits")
            continue
        
        # Store results
        all_results.append({
            'schedule_id': schedule_id,
            'filename': filename,
            'structure': structure,
            'results': calculated_results
        })
        
        time.sleep(1)  # Rate limiting
    
    # Print comparison matrix
    print("\n" + "=" * 70)
    print("COMPARISON MATRIX: Stage 1 Only vs Ground Truth")
    print("=" * 70)
    
    # Group by schedule
    for result in all_results:
        schedule_id = result['schedule_id']
        print(f"\nSchedule {schedule_id}:")
        print("-" * 70)
        
        if schedule_id not in ground_truth:
            print("  No ground truth available")
            continue
        
        gt = ground_truth[schedule_id]
        extracted = result['results']
        
        # Print header
        print(f"{'Window':<12} {'GT_A':>6} {'Ext_A':>6} {'Diff':>6} | {'GT_B':>6} {'Ext_B':>6} {'Diff':>6}")
        print("-" * 70)
        
        # Map extracted arms to A/B
        ext_a = {}
        ext_b = {}
        for arm in extracted:
            name = arm.get('arm_name', '')
            days = arm.get('healthcare_contact_days', {})
            if 'intervention' in arm.get('intervention_type', '').lower() or 'A' in name:
                ext_a = days
            else:
                ext_b = days
        
        # Print comparison for each window
        for w in WINDOWS:
            gt_a = gt.get('A', {}).get(w, 0)
            gt_b = gt.get('B', {}).get(w, 0)
            ea = ext_a.get(w, 0)
            eb = ext_b.get(w, 0)
            diff_a = ea - gt_a
            diff_b = eb - gt_b
            
            # Color coding symbols
            match_a = "✓" if diff_a == 0 else ("~" if abs(diff_a) <= 3 else "✗")
            match_b = "✓" if diff_b == 0 else ("~" if abs(diff_b) <= 3 else "✗")
            
            print(f"{w:<12} {gt_a:>6} {ea:>6} {diff_a:>+6}{match_a} | {gt_b:>6} {eb:>6} {diff_b:>+6}{match_b}")
    
    # Summary statistics
    print("\n" + "=" * 70)
    print("SUMMARY STATISTICS")
    print("=" * 70)
    
    total = 0
    exact = 0
    within_3 = 0
    errors = []
    
    for result in all_results:
        schedule_id = result['schedule_id']
        if schedule_id not in ground_truth:
            continue
        
        gt = ground_truth[schedule_id]
        extracted = result['results']
        
        # Map extracted arms
        ext_a = {}
        ext_b = {}
        for arm in extracted:
            name = arm.get('arm_name', '')
            days = arm.get('healthcare_contact_days', {})
            if 'intervention' in arm.get('intervention_type', '').lower() or 'A' in name:
                ext_a = days
            else:
                ext_b = days
        
        for w in WINDOWS:
            for arm_letter, ext_days in [('A', ext_a), ('B', ext_b)]:
                if arm_letter not in gt:
                    continue
                gt_val = gt[arm_letter].get(w, 0)
                ext_val = ext_days.get(w, 0)
                
                total += 1
                diff = abs(ext_val - gt_val)
                errors.append(diff)
                
                if diff == 0:
                    exact += 1
                    within_3 += 1
                elif diff <= 3:
                    within_3 += 1
    
    accuracy = exact / total if total > 0 else 0
    clinical_accuracy = within_3 / total if total > 0 else 0
    mae = sum(errors) / len(errors) if errors else 0
    
    print(f"Total comparisons: {total}")
    print(f"Exact matches: {exact} ({accuracy:.1%})")
    print(f"Within ±3 days: {within_3} ({clinical_accuracy:.1%})")
    print(f"Mean Absolute Error: {mae:.2f} days")
    
    print("\n" + "=" * 70)
    print("This is the baseline with Stage 1 only.")
    print("Compare this to results with Stage 2 + Stage 3 (Judge) added.")
    print("=" * 70)


if __name__ == "__main__":
    main()

