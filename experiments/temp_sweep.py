#!/usr/bin/env python3
"""
Temperature Sweep Test - Run extraction at different temperatures
to measure variance and find optimal settings.

Usage: python3 temp_sweep.py
"""

import os
import statistics
import json
import re
import time
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

# Config
MODEL = "gemini-3-flash-preview"
TEMPS = [0.1, 0.2, 0.3, 0.4, 0.5]

PROMPT = '''
Extract healthcare contact days from this Schedule of Assessments.

## CRITICAL: READ THE LEGEND FIRST
The legend (below the table) contains the AUTHORITATIVE visit pattern for each arm.
Example: "Arm A: Visits on Days 1, 8, 15 of each 28-day cycle"

Apply this pattern to ALL cycles, including grouped columns like "C4-C12".

## CALCULATION STEPS
1. From legend: Get visits per cycle (e.g., D1,D8,D15 = 3 visits/cycle)
2. Total cycles = treatment_months × 30 / cycle_length_days
3. Treatment visits = cycles × visits_per_cycle

## INCLUDE ALL VISIT TYPES
- Screening visits (usually 1-2 days)
- Treatment visits (calculated above)
- EOT (End of Treatment) visit (1 day)
- Follow-up visits: M9 FU (1 day), M12 FU (1 day)

## CUMULATIVE COUNTS (from Day 1)
- screening: Pre-treatment visits only
- 1_month: All visits through Day 30
- 3_months: All visits through Day 90
- 6_months: All visits through Day 180
- 9_months: All visits through Day 270
- 12_months: All visits through Day 365

Return ONLY JSON:
[{"arm_name": "...", "intervention_type": "intervention", "healthcare_contact_days": {"screening": INT, "1_month": INT, "3_months": INT, "6_months": INT, "9_months": INT, "12_months": INT}}]
'''

def main():
    print("=" * 70)
    print("TEMPERATURE SWEEP TEST")
    print("=" * 70)
    
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    pdf_path = "synthetic_schedules/synthetic_schedule_01_complex_two.pdf"
    print(f"\nUploading {pdf_path}...")
    uploaded = client.files.upload(file=pdf_path)
    print(f"Uploaded: {uploaded.uri}\n")
    
    windows = ['screening', '1_month', '3_months', '6_months', '9_months', '12_months']
    samples_A = {w: [] for w in windows}
    samples_B = {w: [] for w in windows}
    
    for temp in TEMPS:
        print(f"Testing temp={temp}...", end=" ")
        
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=[types.Content(role="user", parts=[
                    types.Part.from_uri(file_uri=uploaded.uri, mime_type="application/pdf"),
                    types.Part.from_text(text=PROMPT)
                ])],
                config=types.GenerateContentConfig(temperature=temp)
            )
            
            match = re.search(r'\[\s*\{[\s\S]*\}\s*\]', response.text)
            if match:
                data = json.loads(match.group(0))
                for arm in data:
                    name = arm.get('arm_name', '')
                    is_A = 'Abemaciclib' in name or ('A' in name and 'B' not in name and 'Fulvestrant' not in name)
                    target = samples_A if is_A else samples_B
                    if 'Fulvestrant' in name and 'Abemaciclib' not in name:
                        target = samples_B
                    
                    days = arm.get('healthcare_contact_days', {})
                    for w in windows:
                        if w in days and isinstance(days[w], int):
                            target[w].append(days[w])
                
                a_12 = samples_A['12_months'][-1] if samples_A['12_months'] else '?'
                b_12 = samples_B['12_months'][-1] if samples_B['12_months'] else '?'
                print(f"OK  A_12mo={a_12}, B_12mo={b_12}")
            else:
                print("Parse error")
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(1)
    
    # Calculate stats
    print("\n" + "=" * 80)
    print("RESULTS: Median, IQR, Range")
    print("=" * 80)
    
    gt_a = {'screening': 2, '1_month': 4, '3_months': 11, '6_months': 22, '9_months': 33, '12_months': 43}
    gt_b = {'screening': 2, '1_month': 3, '3_months': 8, '6_months': 15, '9_months': 23, '12_months': 30}
    
    def stats(values):
        if not values:
            return None, None, None, None, None
        s = sorted(values)
        n = len(s)
        median = int(statistics.median(s))
        q1 = s[n // 4] if n > 1 else s[0]
        q3 = s[(3 * n) // 4] if n > 1 else s[0]
        return median, q1, q3, min(s), max(s)
    
    print("\nArm A (Abemaciclib + Fulvestrant):")
    print(f"  {'Window':<12} {'Median':>7} {'Q1':>5} {'Q3':>5} {'IQR':>5} {'Range':>10} {'GT':>5} {'Err':>5}  Samples")
    print("-" * 85)
    for w in windows:
        median, q1, q3, mn, mx = stats(samples_A[w])
        if median:
            iqr = q3 - q1
            rng = f"{mn}-{mx}"
            diff = median - gt_a[w]
            print(f"  {w:<12} {median:>7} {q1:>5} {q3:>5} {iqr:>5} {rng:>10} {gt_a[w]:>5} {diff:>+5}  {samples_A[w]}")
    
    print("\nArm B (Fulvestrant):")
    print(f"  {'Window':<12} {'Median':>7} {'Q1':>5} {'Q3':>5} {'IQR':>5} {'Range':>10} {'GT':>5} {'Err':>5}  Samples")
    print("-" * 85)
    for w in windows:
        median, q1, q3, mn, mx = stats(samples_B[w])
        if median:
            iqr = q3 - q1
            rng = f"{mn}-{mx}"
            diff = median - gt_b[w]
            print(f"  {w:<12} {median:>7} {q1:>5} {q3:>5} {iqr:>5} {rng:>10} {gt_b[w]:>5} {diff:>+5}  {samples_B[w]}")

if __name__ == "__main__":
    main()

