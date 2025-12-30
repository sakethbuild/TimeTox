#!/usr/bin/env python3
"""
Production Pipeline: Extract Time-Toxic Days from Real SoA PDFs

Based on the tested Stage2_Bestperformer + Category Breakdown pipeline
that achieved 100% clinical accuracy on synthetic schedules.

Input: PDF files in SoA_PDFs/ directory (named with PMID)
Output: JSON and CSV files with extracted data

Usage:
    python3 production/extract_soa.py
    python3 production/extract_soa.py --pdf-dir /path/to/pdfs
"""

import os
import sys
import csv
import json
import re
import time
import argparse
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
# PROMPTS (from tested pipeline)
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
   
3. Count CUMULATIVE visits per window (ONLY count visits up to the day limit):
   - screening: screening_days only (pre-treatment)
   - 1_month: screening + visits from Day 1-30
   - 3_months: screening + visits from Day 1-90
   - 6_months: screening + visits from Day 1-180
   - 9_months: screening + visits from Day 1-270
   - 12_months: screening + visits from Day 1-365
   
   IMPORTANT: Even if treatment continues beyond 12 months, only count visits 
   that occur within each time window. Do NOT count all treatment visits at 12_months.

4. Add follow-up visits ONLY if they fall within the window:
   - EOT visit: Only add if treatment ends within that window
   - M9 FU (Day ~270): Add to 9_months and 12_months
   - M12 FU (Day ~365): Add to 12_months only

## CATEGORY BREAKDOWN

Also break down visits by what happens on each day:

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

def extract_pmid(filename: str) -> str:
    """Extract PMID from filename like 'PMID 23358972_Summary_SoE.pdf'."""
    match = re.search(r'PMID\s*(\d+)', filename, re.IGNORECASE)
    if match:
        return match.group(1)
    # Fallback: use filename without extension
    return os.path.splitext(filename)[0]


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


def extract_arm_results(results: List[Dict]) -> List[Dict]:
    """Extract and label arm results from response."""
    extracted = []
    
    for i, arm in enumerate(results):
        name = arm.get('arm_name', f'Arm {i+1}')
        days = arm.get('healthcare_contact_days', {})
        categories = arm.get('category_breakdown', {})
        breakdown = arm.get('calculation_breakdown', {})
        
        # Determine arm label
        if 'Arm A' in name and 'Arm B' not in name:
            arm_label = 'A'
        elif 'Arm B' in name:
            arm_label = 'B'
        elif i == 0:
            arm_label = 'A'
        else:
            arm_label = chr(ord('A') + i)
        
        extracted.append({
            'arm_label': arm_label,
            'arm_name': name,
            'healthcare_contact_days': days,
            'category_breakdown': categories,
            'calculation_breakdown': breakdown
        })
    
    return extracted


# ============================================================================
# EXTRACTION PIPELINE
# ============================================================================

def extract_from_pdf(client, pdf_path: str, pmid: str) -> Dict:
    """
    Run the extraction pipeline on a single PDF.
    
    Returns dictionary with all extracted data.
    """
    result = {
        'pmid': pmid,
        'pdf_path': pdf_path,
        'filename': os.path.basename(pdf_path),
        'extraction_timestamp': datetime.now().isoformat(),
    }
    
    # Upload PDF
    print(f"  Uploading {os.path.basename(pdf_path)}...")
    try:
        uploaded = client.files.upload(file=pdf_path)
    except Exception as e:
        result['error'] = f'Upload failed: {e}'
        return result
    
    # ===== STAGE 1: Extract Structure =====
    print("  Stage 1: Extracting structure...")
    stage1_response = call_api(client, uploaded, PROMPT_STAGE1, force_json=True)
    structure = parse_json(stage1_response)
    
    if not structure:
        result['error'] = 'Failed to parse Stage 1'
        result['raw_stage1'] = stage1_response
        return result
    
    result['structure'] = structure
    result['protocol_info'] = structure.get('protocol_info', {})
    
    time.sleep(0.5)
    
    # ===== STAGE 2: Calculate Counts with Categories =====
    print("  Stage 2: Calculating counts with category breakdown...")
    prompt_stage2 = PROMPT_STAGE2_TEMPLATE.format(structure=json.dumps(structure, indent=2))
    stage2_response = call_api(client, uploaded, prompt_stage2, force_json=True)
    stage2_results = parse_json(stage2_response)
    
    if not stage2_results:
        result['error'] = 'Failed to parse Stage 2'
        result['raw_stage2'] = stage2_response
        return result
    
    # Extract arm results
    arms = extract_arm_results(stage2_results)
    result['arms'] = arms
    result['num_arms'] = len(arms)
    
    return result


# ============================================================================
# OUTPUT FUNCTIONS
# ============================================================================

def results_to_csv(results: List[Dict], output_path: str):
    """Convert results to CSV format with one row per arm."""
    
    # Build header
    header = [
        'pmid', 'arm_label', 'arm_name', 'disease', 
        'cycle_length_days', 'treatment_duration_months',
    ]
    
    # Add time-toxic day columns
    for w in WINDOWS:
        header.append(f'total_{w}')
    
    # Add category columns
    for cat in CATEGORIES:
        for w in WINDOWS:
            header.append(f'{cat}_{w}')
    
    header.extend(['total_cycles', 'total_visits', 'error', 'filename'])
    
    rows = []
    for result in results:
        pmid = result.get('pmid', '')
        protocol = result.get('protocol_info', {})
        structure = result.get('structure', {})
        error = result.get('error', '')
        filename = result.get('filename', '')
        
        # Get cycle info from first arm
        cycle_length = '?'
        if structure.get('arms'):
            cycle_length = structure['arms'][0].get('cycle_length_days', '?')
        
        arms = result.get('arms', [])
        if not arms and error:
            # Error case - one row with error
            row = {
                'pmid': pmid,
                'arm_label': '',
                'arm_name': '',
                'disease': protocol.get('disease', ''),
                'cycle_length_days': cycle_length,
                'treatment_duration_months': protocol.get('treatment_duration_months', ''),
                'error': error,
                'filename': filename,
            }
            for w in WINDOWS:
                row[f'total_{w}'] = ''
            for cat in CATEGORIES:
                for w in WINDOWS:
                    row[f'{cat}_{w}'] = ''
            row['total_cycles'] = ''
            row['total_visits'] = ''
            rows.append(row)
        else:
            for arm in arms:
                row = {
                    'pmid': pmid,
                    'arm_label': arm.get('arm_label', ''),
                    'arm_name': arm.get('arm_name', ''),
                    'disease': protocol.get('disease', ''),
                    'cycle_length_days': cycle_length,
                    'treatment_duration_months': protocol.get('treatment_duration_months', ''),
                    'error': '',
                    'filename': filename,
                }
                
                # Total visits per window
                days = arm.get('healthcare_contact_days', {})
                for w in WINDOWS:
                    row[f'total_{w}'] = days.get(w, '')
                
                # Category breakdown
                categories = arm.get('category_breakdown', {})
                for cat in CATEGORIES:
                    cat_data = categories.get(cat, {})
                    for w in WINDOWS:
                        row[f'{cat}_{w}'] = cat_data.get(w, '')
                
                # Calculation breakdown
                breakdown = arm.get('calculation_breakdown', {})
                row['total_cycles'] = breakdown.get('total_cycles', '')
                row['total_visits'] = breakdown.get('total_visits', '')
                
                rows.append(row)
    
    # Write CSV
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"📄 CSV saved to: {output_path}")


def results_to_json(results: List[Dict], output_path: str):
    """Save results to JSON format."""
    output = {
        'extraction_info': {
            'model': MODEL,
            'timestamp': datetime.now().isoformat(),
            'num_pdfs': len(results),
        },
        'results': results
    }
    
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"📋 JSON saved to: {output_path}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Extract time-toxic days from SoA PDFs')
    parser.add_argument('--pdf-dir', default=None, 
                        help='Directory containing PDF files (default: SoA_PDFs/)')
    parser.add_argument('--output-dir', default=None,
                        help='Output directory (default: results/)')
    args = parser.parse_args()
    
    # Set directories
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pdf_dir = args.pdf_dir or os.path.join(base_dir, 'SoA_PDFs')
    output_dir = args.output_dir or os.path.join(base_dir, 'results')
    
    # Find PDFs
    pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        print(f"❌ No PDF files found in {pdf_dir}")
        return
    
    print("=" * 70)
    print("PRODUCTION EXTRACTION: Real SoA PDFs")
    print("=" * 70)
    print(f"PDF Directory: {pdf_dir}")
    print(f"Found {len(pdf_files)} PDF(s)")
    print()
    
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    results = []
    
    for pdf_file in sorted(pdf_files):
        pdf_path = os.path.join(pdf_dir, pdf_file)
        pmid = extract_pmid(pdf_file)
        
        print(f"\n[PMID {pmid}] {pdf_file}")
        
        result = extract_from_pdf(client, pdf_path, pmid)
        results.append(result)
        
        if 'error' not in result:
            num_arms = result.get('num_arms', 0)
            disease = result.get('protocol_info', {}).get('disease', 'Unknown')
            print(f"  ✓ Extracted {num_arms} arm(s) - {disease[:50]}")
        else:
            print(f"  ✗ Error: {result['error']}")
        
        time.sleep(1)
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    json_path = os.path.join(output_dir, f'soa_extractions_{timestamp}.json')
    csv_path = os.path.join(output_dir, f'soa_extractions_{timestamp}.csv')
    
    results_to_json(results, json_path)
    results_to_csv(results, csv_path)
    
    # Summary
    print("\n" + "=" * 70)
    print("EXTRACTION COMPLETE")
    print("=" * 70)
    successful = sum(1 for r in results if 'error' not in r)
    print(f"Successfully extracted: {successful}/{len(results)} PDFs")
    print(f"Output files:")
    print(f"  - {json_path}")
    print(f"  - {csv_path}")


if __name__ == "__main__":
    main()

