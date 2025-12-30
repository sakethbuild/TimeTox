#!/usr/bin/env python3
"""
Vanilla Baseline Extraction for Real SoA PDFs

Single-pass extraction (no 2-stage structure extraction).
For comparison with the optimized pipeline.

Usage:
    python3 production/extract_soa_vanilla.py
"""

import os
import sys
import csv
import json
import re
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

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
# VANILLA SINGLE-PASS PROMPT
# ============================================================================

EXTRACTION_PROMPT = """
You are an expert clinical trial protocol analyst. Your task is to extract healthcare contact days from the Schedule of Assessments (SoA) table.

## DEFINITIONS

**Healthcare Contact Day**: Any calendar day requiring in-person contact with the healthcare system (clinic visits, labs, imaging, infusions, procedures). Count each unique calendar day ONCE regardless of how many assessments occur that day.

**Time Windows** (ONLY count visits within each window):
- screening: All pre-randomization/pre-treatment visits
- 1_month: Day 1 through Day 30 after treatment start
- 3_months: Day 1 through Day 90
- 6_months: Day 1 through Day 180
- 9_months: Day 1 through Day 270
- 12_months: Day 1 through Day 365

IMPORTANT: Even if treatment continues beyond 12 months, only count visits that occur within each time window.

## EXTRACTION RULES

1. **Identify all treatment arms** from the table (look for Arm A, Arm B, intervention vs control)
2. **Map cycle structure** to calendar days (e.g., 28-day cycles: C1D1=Day 1, C1D15=Day 15, C2D1=Day 29, etc.)
3. **CRITICAL - Expand grouped columns**: Columns like "C4-C12" or "C4-C6" represent MULTIPLE cycles. You must expand these by calculating visits for EACH cycle in the range.
4. **Count unique visit days** - if multiple assessments occur on the same day, count as ONE contact day
5. **Handle arm-specific visits**: Look for superscripts like X^A meaning "Arm A only"

## CATEGORY DEFINITIONS

- **core_treatment**: Drug administration, infusions, treatment procedures
- **imaging_diagnostics**: CT, MRI, PET, X-ray, ultrasound, ECG, ECHO
- **labs**: Blood draws, urinalysis, biomarkers
- **clinic_visits**: Physical exam, vital signs, assessments without above procedures

Note: A single day may include multiple categories. Count the day in EACH category that occurs.

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
      "disease": "<disease being treated>"
    }
  }
]
```

NOW ANALYZE THE PROVIDED SCHEDULE OF ASSESSMENTS.
"""

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_pmid(filename: str) -> str:
    """Extract PMID from filename."""
    match = re.search(r'PMID\s*(\d+)', filename, re.IGNORECASE)
    if match:
        return match.group(1)
    return os.path.splitext(filename)[0]


def call_api(client, uploaded_file, prompt, temp=0.1):
    """Make API call with retry."""
    for attempt in range(3):
        try:
            config = types.GenerateContentConfig(temperature=temp)
            
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
    
    # Try direct parse
    try:
        return json.loads(text.strip())
    except:
        pass
    
    # Try code block
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


# ============================================================================
# EXTRACTION
# ============================================================================

def extract_vanilla(client, pdf_path: str, pmid: str) -> Dict:
    """Single-pass vanilla extraction."""
    result = {
        'pmid': pmid,
        'pdf_path': pdf_path,
        'filename': os.path.basename(pdf_path),
        'extraction_timestamp': datetime.now().isoformat(),
        'method': 'vanilla_single_pass',
    }
    
    print(f"  Uploading {os.path.basename(pdf_path)}...")
    try:
        uploaded = client.files.upload(file=pdf_path)
    except Exception as e:
        result['error'] = f'Upload failed: {e}'
        return result
    
    print("  Extracting (single pass)...")
    response = call_api(client, uploaded, EXTRACTION_PROMPT)
    parsed = parse_json(response)
    
    if not parsed:
        result['error'] = 'Failed to parse response'
        result['raw_response'] = response
        return result
    
    # Extract arm data
    arms = []
    for i, arm in enumerate(parsed):
        arm_label = 'A' if i == 0 else chr(ord('A') + i)
        if 'Arm A' in arm.get('arm_name', '') and 'Arm B' not in arm.get('arm_name', ''):
            arm_label = 'A'
        elif 'Arm B' in arm.get('arm_name', ''):
            arm_label = 'B'
        
        arms.append({
            'arm_label': arm_label,
            'arm_name': arm.get('arm_name', ''),
            'intervention_type': arm.get('intervention_type', ''),
            'healthcare_contact_days': arm.get('healthcare_contact_days', {}),
            'category_breakdown': arm.get('category_breakdown', {}),
            'extraction_notes': arm.get('extraction_notes', {}),
        })
    
    result['arms'] = arms
    result['num_arms'] = len(arms)
    
    # Extract disease from first arm
    if arms and arms[0].get('extraction_notes', {}).get('disease'):
        result['disease'] = arms[0]['extraction_notes']['disease']
    
    return result


# ============================================================================
# OUTPUT
# ============================================================================

def results_to_csv(results: List[Dict], output_path: str):
    """Convert results to CSV."""
    header = [
        'pmid', 'method', 'arm_label', 'arm_name', 'disease',
        'cycle_length_days', 'treatment_duration_months',
    ]
    
    for w in WINDOWS:
        header.append(f'total_{w}')
    
    for cat in CATEGORIES:
        for w in WINDOWS:
            header.append(f'{cat}_{w}')
    
    header.extend(['error', 'filename'])
    
    rows = []
    for result in results:
        pmid = result.get('pmid', '')
        method = result.get('method', 'vanilla')
        error = result.get('error', '')
        filename = result.get('filename', '')
        disease = result.get('disease', '')
        
        arms = result.get('arms', [])
        if not arms and error:
            row = {'pmid': pmid, 'method': method, 'error': error, 'filename': filename}
            for col in header:
                if col not in row:
                    row[col] = ''
            rows.append(row)
        else:
            for arm in arms:
                notes = arm.get('extraction_notes', {})
                row = {
                    'pmid': pmid,
                    'method': method,
                    'arm_label': arm.get('arm_label', ''),
                    'arm_name': arm.get('arm_name', ''),
                    'disease': notes.get('disease', disease),
                    'cycle_length_days': notes.get('cycle_length_days', ''),
                    'treatment_duration_months': notes.get('treatment_duration_months', ''),
                    'error': '',
                    'filename': filename,
                }
                
                days = arm.get('healthcare_contact_days', {})
                for w in WINDOWS:
                    row[f'total_{w}'] = days.get(w, '')
                
                categories = arm.get('category_breakdown', {})
                for cat in CATEGORIES:
                    cat_data = categories.get(cat, {})
                    for w in WINDOWS:
                        row[f'{cat}_{w}'] = cat_data.get(w, '')
                
                rows.append(row)
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"📄 CSV saved to: {output_path}")


def results_to_json(results: List[Dict], output_path: str):
    """Save results to JSON."""
    output = {
        'extraction_info': {
            'model': MODEL,
            'method': 'vanilla_single_pass',
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
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pdf_dir = os.path.join(base_dir, 'SoA_PDFs')
    output_dir = os.path.join(base_dir, 'results')
    
    pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        print(f"❌ No PDF files found in {pdf_dir}")
        return
    
    print("=" * 70)
    print("VANILLA BASELINE EXTRACTION")
    print("=" * 70)
    print(f"Method: Single-pass (no structure extraction)")
    print(f"Found {len(pdf_files)} PDF(s)")
    print()
    
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    results = []
    
    for pdf_file in sorted(pdf_files):
        pdf_path = os.path.join(pdf_dir, pdf_file)
        pmid = extract_pmid(pdf_file)
        
        print(f"\n[PMID {pmid}] {pdf_file}")
        
        result = extract_vanilla(client, pdf_path, pmid)
        results.append(result)
        
        if 'error' not in result:
            num_arms = result.get('num_arms', 0)
            print(f"  ✓ Extracted {num_arms} arm(s)")
        else:
            print(f"  ✗ Error: {result['error']}")
        
        time.sleep(1)
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    json_path = os.path.join(output_dir, f'soa_vanilla_{timestamp}.json')
    csv_path = os.path.join(output_dir, f'soa_vanilla_{timestamp}.csv')
    
    results_to_json(results, json_path)
    results_to_csv(results, csv_path)
    
    print("\n" + "=" * 70)
    print("VANILLA EXTRACTION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()

