#!/usr/bin/env python3
"""
Compare Two-Stage vs Vanilla: 5 runs each with timing

Calculates median and IQR for each method.
"""

import os
import sys
import json
import re
import time
import statistics
from datetime import datetime
from typing import Dict, List

from dotenv import load_dotenv
load_dotenv(override=True)

from google import genai
from google.genai import types

MODEL = "gemini-3-flash-preview"
WINDOWS = ['screening', '1_month', '3_months', '6_months', '9_months', '12_months']

# ============================================================================
# TWO-STAGE PROMPTS
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
   
3. Count CUMULATIVE visits per window (ONLY count visits within each window):
   - screening: screening_days only (pre-treatment)
   - 1_month: screening + visits from Day 1-30
   - 3_months: screening + visits from Day 1-90
   - 6_months: screening + visits from Day 1-180
   - 9_months: screening + visits from Day 1-270
   - 12_months: screening + visits from Day 1-365
   
   IMPORTANT: Even if treatment continues beyond 12 months, only count visits 
   that occur within each time window.

4. Add follow-up visits ONLY if they fall within the window.

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
    }}
  }}
]
"""

VANILLA_PROMPT = """
You are an expert clinical trial protocol analyst. Extract healthcare contact days from the Schedule of Assessments.

**Time Windows** (ONLY count visits within each window):
- screening: All pre-treatment visits
- 1_month: Day 1 through Day 30
- 3_months: Day 1 through Day 90
- 6_months: Day 1 through Day 180
- 9_months: Day 1 through Day 270
- 12_months: Day 1 through Day 365

IMPORTANT: Even if treatment continues beyond 12 months, only count visits within each window.

Return ONLY valid JSON:
[
  {
    "arm_name": "Arm A (Treatment Name)",
    "healthcare_contact_days": {
      "screening": <integer>,
      "1_month": <integer>,
      "3_months": <integer>,
      "6_months": <integer>,
      "9_months": <integer>,
      "12_months": <integer>
    }
  }
]
"""

# ============================================================================
# HELPERS
# ============================================================================

def call_api(client, uploaded_file, prompt, temp=0.1, force_json=True):
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


def parse_json(text):
    if not text:
        return None
    try:
        return json.loads(text.strip())
    except:
        pass
    match = re.search(r'[\[\{][\s\S]*[\]\}]', text)
    if match:
        try:
            return json.loads(match.group(0))
        except:
            pass
    return None


def extract_days(results):
    """Extract healthcare_contact_days from first arm."""
    if not results:
        return {}
    if isinstance(results, list) and len(results) > 0:
        return results[0].get('healthcare_contact_days', {})
    return {}


# ============================================================================
# EXTRACTION METHODS
# ============================================================================

def run_two_stage(client, uploaded_file) -> Dict:
    """Run two-stage extraction, return days and timing."""
    start = time.time()
    
    # Stage 1
    s1_response = call_api(client, uploaded_file, PROMPT_STAGE1, force_json=True)
    structure = parse_json(s1_response)
    
    if not structure:
        return {'error': 'Stage 1 failed', 'time': time.time() - start}
    
    time.sleep(0.5)
    
    # Stage 2
    prompt_s2 = PROMPT_STAGE2_TEMPLATE.format(structure=json.dumps(structure, indent=2))
    s2_response = call_api(client, uploaded_file, prompt_s2, force_json=True)
    results = parse_json(s2_response)
    
    elapsed = time.time() - start
    
    days = extract_days(results)
    return {'days': days, 'time': elapsed}


def run_vanilla(client, uploaded_file) -> Dict:
    """Run vanilla single-pass extraction."""
    start = time.time()
    
    response = call_api(client, uploaded_file, VANILLA_PROMPT, force_json=True)
    results = parse_json(response)
    
    elapsed = time.time() - start
    
    days = extract_days(results)
    return {'days': days, 'time': elapsed}


# ============================================================================
# MAIN
# ============================================================================

def main():
    N_RUNS = 5
    
    # Find the PDF
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pdf_dir = os.path.join(base_dir, 'SoA_PDFs')
    
    pdf_file = None
    for f in os.listdir(pdf_dir):
        if '35728048' in f and f.endswith('.pdf'):
            pdf_file = os.path.join(pdf_dir, f)
            break
    
    if not pdf_file:
        print("❌ PDF not found")
        return
    
    print("=" * 70)
    print("METHOD COMPARISON: Two-Stage vs Vanilla (5 runs each)")
    print("=" * 70)
    print(f"PDF: PMID 35728048")
    print(f"Runs per method: {N_RUNS}")
    print()
    
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    # Upload once
    print("Uploading PDF...")
    uploaded = client.files.upload(file=pdf_file)
    print()
    
    # Two-Stage runs
    print("─" * 70)
    print("TWO-STAGE PIPELINE")
    print("─" * 70)
    
    two_stage_results = []
    two_stage_times = []
    
    for i in range(N_RUNS):
        print(f"  Run {i+1}/{N_RUNS}...", end=" ", flush=True)
        result = run_two_stage(client, uploaded)
        two_stage_results.append(result.get('days', {}))
        two_stage_times.append(result.get('time', 0))
        print(f"✓ {result.get('time', 0):.1f}s | 12m={result.get('days', {}).get('12_months', '?')}")
        time.sleep(1)
    
    # Vanilla runs
    print()
    print("─" * 70)
    print("VANILLA SINGLE-PASS")
    print("─" * 70)
    
    vanilla_results = []
    vanilla_times = []
    
    for i in range(N_RUNS):
        print(f"  Run {i+1}/{N_RUNS}...", end=" ", flush=True)
        result = run_vanilla(client, uploaded)
        vanilla_results.append(result.get('days', {}))
        vanilla_times.append(result.get('time', 0))
        print(f"✓ {result.get('time', 0):.1f}s | 12m={result.get('days', {}).get('12_months', '?')}")
        time.sleep(1)
    
    # Calculate statistics
    print()
    print("=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    
    def calc_stats(values):
        if not values or len(values) < 2:
            return {'median': values[0] if values else 0, 'iqr': 0, 'min': values[0] if values else 0, 'max': values[0] if values else 0}
        sorted_vals = sorted(values)
        median = statistics.median(sorted_vals)
        q1 = sorted_vals[len(sorted_vals)//4]
        q3 = sorted_vals[3*len(sorted_vals)//4]
        return {'median': median, 'iqr': q3 - q1, 'min': min(values), 'max': max(values), 'values': values}
    
    # Time comparison
    print("\n📊 TIMING COMPARISON")
    print("─" * 50)
    ts_time = calc_stats(two_stage_times)
    van_time = calc_stats(vanilla_times)
    
    print(f"{'Method':<20} {'Median':>10} {'IQR':>10} {'Range':>15}")
    print("─" * 50)
    print(f"{'Two-Stage':<20} {ts_time['median']:>9.1f}s {ts_time['iqr']:>9.1f}s {ts_time['min']:.1f}-{ts_time['max']:.1f}s")
    print(f"{'Vanilla':<20} {van_time['median']:>9.1f}s {van_time['iqr']:>9.1f}s {van_time['min']:.1f}-{van_time['max']:.1f}s")
    
    # Results comparison per window
    print("\n📊 12-MONTH EXTRACTION COMPARISON")
    print("─" * 50)
    
    for window in WINDOWS:
        ts_vals = [r.get(window, 0) for r in two_stage_results]
        van_vals = [r.get(window, 0) for r in vanilla_results]
        
        ts_stats = calc_stats(ts_vals)
        van_stats = calc_stats(van_vals)
        
        print(f"\n{window}:")
        print(f"  Two-Stage: median={ts_stats['median']}, IQR={ts_stats['iqr']}, range={ts_stats['min']}-{ts_stats['max']}")
        print(f"  Vanilla:   median={van_stats['median']}, IQR={van_stats['iqr']}, range={van_stats['min']}-{van_stats['max']}")
    
    # Raw values
    print("\n📊 RAW VALUES (all 5 runs)")
    print("─" * 70)
    print(f"{'Window':<12} {'Two-Stage (5 runs)':<30} {'Vanilla (5 runs)':<30}")
    print("─" * 70)
    
    for window in WINDOWS:
        ts_vals = [str(r.get(window, '?')) for r in two_stage_results]
        van_vals = [str(r.get(window, '?')) for r in vanilla_results]
        print(f"{window:<12} {', '.join(ts_vals):<30} {', '.join(van_vals):<30}")
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = {
        'pmid': '35728048',
        'n_runs': N_RUNS,
        'timestamp': timestamp,
        'two_stage': {
            'times': two_stage_times,
            'results': two_stage_results,
        },
        'vanilla': {
            'times': vanilla_times,
            'results': vanilla_results,
        }
    }
    
    output_path = os.path.join(base_dir, 'results', f'method_comparison_{timestamp}.json')
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 Results saved to: {output_path}")


if __name__ == "__main__":
    main()

