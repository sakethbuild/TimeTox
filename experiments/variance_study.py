#!/usr/bin/env python3
"""
TimeTox Variance Study

Goal: Compare the variance (Median & IQR) of Two-Stage vs. Vanilla pipelines
by running each 5 times on all 20 synthetic schedules.

Hypothesis: Two-Stage pipeline exhibits higher, more realistic variance at 
later timepoints (12 months) compared to Vanilla.
"""

import os
import sys
import json
import time
import statistics
import traceback
from datetime import datetime
from typing import Dict, List, Any

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from google import genai
from google.genai import types

# Import Two-Stage Pipeline
# Note: Stage2_Bestperformer is a directory, effectively a package if we treat it so
# getting run_pipeline from it.
try:
    from Stage2_Bestperformer.pipeline import run_pipeline as run_two_stage_pipeline
    from Stage2_Bestperformer.pipeline import load_ground_truth
except ImportError:
    # If standard import fails, try dynamic import or path manipulation
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Stage2_Bestperformer'))
    from pipeline import run_pipeline as run_two_stage_pipeline
    from pipeline import load_ground_truth

# Import Vanilla Logic imports (We will reimplement the runner to ensure valid loop, but reuse prompts/parsing)
from core.test_extraction import EXTRACTION_PROMPT, parse_json_response

# Configuration
MODEL = "gemini-3-flash-preview"
N_RUNS = 5
SCHEDULES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'CTGProtocols')
RESULTS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results', 'variance_study_results.json')
INTERMEDIATE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results', 'variance_study_intermediate.json')


def setup_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not set")
        sys.exit(1)
    return genai.Client(api_key=api_key)


def run_vanilla_extraction(client, pdf_path):
    """Run single-pass vanilla extraction."""
    try:
        uploaded_file = client.files.upload(file=pdf_path)
        
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_uri(file_uri=uploaded_file.uri, mime_type="application/pdf"),
                    types.Part.from_text(text=EXTRACTION_PROMPT),
                ],
            ),
        ]
        
        config = types.GenerateContentConfig(temperature=0.1)
        
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=MODEL,
                    contents=contents,
                    config=config
                )
                
                # Parse
                parsed = parse_json_response(response.text)
                if parsed:
                    # Extract 12-month data for A and B
                    result = {'extraction': parsed}
                    return result
            except Exception as e:
                print(f"    Vanilla Retry {attempt+1}: {e}")
                time.sleep(2**attempt)
                
    except Exception as e:
        print(f"  Vanilla Error: {e}")
    return {'error': 'Failed'}


def extract_12m_from_vanilla(vanilla_result):
    """Extract 12-month counts from vanilla output."""
    if 'error' in vanilla_result or not vanilla_result.get('extraction'):
        return {'A': None, 'B': None}
    
    arms = vanilla_result['extraction']
    val_a, val_b = None, None
    
    # Sort arms to ensure stability if names allow
    # But usually just taking first two is safer if names vary wildly
    # Let's try to be smart about A/B mapping if possible
    
    found_arms = []
    for arm in arms:
        name = arm.get('arm_name', '')
        days = arm.get('healthcare_contact_days', {})
        val = days.get('12_months')
        if isinstance(val, str) and val.isdigit():
            val = int(val)
        found_arms.append((name, val))

    if not found_arms:
        return {'A': None, 'B': None}
        
    # Heuristics
    # 1. Look for 'Arm A' / 'Arm B'
    for name, val in found_arms:
        if 'Arm A' in name and val_a is None: val_a = val
        elif 'Arm B' in name and val_b is None: val_b = val
    
    # 2. Fallback to order if not set
    if val_a is None and len(found_arms) > 0: val_a = found_arms[0][1]
    if val_b is None and len(found_arms) > 1: val_b = found_arms[1][1]
            
    return {'A': val_a, 'B': val_b}


def extract_12m_from_twostage(ts_result):
    """Extract 12-month counts from two-stage output."""
    if 'error' in ts_result:
        return {'A': None, 'B': None}
    
    ext = ts_result.get('extracted', {})
    val_a = ext.get('A', {}).get('12_months')
    val_b = ext.get('B', {}).get('12_months')
    
    return {'A': val_a, 'B': val_b}


def calculate_stats(values):
    """Calculate median and IQR."""
    clean_vals = [v for v in values if v is not None]
    if not clean_vals:
        return {'median': 0, 'iqr': 0, 'n': 0, 'values': []}
    
    if len(clean_vals) < 2:
         return {'median': clean_vals[0] if clean_vals else 0, 'iqr': 0, 'n': len(clean_vals), 'values': clean_vals}
         
    qt = statistics.quantiles(clean_vals, n=4)
    return {
        'median': statistics.median(clean_vals),
        'iqr': qt[2] - qt[0],
        'n': len(clean_vals),
        'values': clean_vals
    }


def main():
    print("="*60)
    print("VARIANCE STUDY: Two-Stage vs Vanilla (Real PDFs)")
    print(f"Directory: {SCHEDULES_DIR}")
    print(f"Settings: 5 Runs per Method")
    print("="*60)
    
    client = setup_client()
    # gt_all = load_ground_truth() # No ground truth for real PDFs
    gt_all = {}
    
    # Structure to hold all results
    study_data = {}
    
    # Load intermediate if exists
    if os.path.exists(INTERMEDIATE_FILE):
        print(f"Resuming from {INTERMEDIATE_FILE}...")
        with open(INTERMEDIATE_FILE, 'r') as f:
            study_data = json.load(f)
    
    # Find PDFs
    pdf_files = [f for f in os.listdir(SCHEDULES_DIR) if f.lower().endswith('.pdf')]
    pdf_files.sort()
    
    if not pdf_files:
        print("No PDFs found!")
        return

    try:
        for i, pdf_name in enumerate(pdf_files, 1):
            schedule_id = pdf_name  # Use filename as ID since we don't have IDs
            
            if schedule_id not in study_data:
                study_data[schedule_id] = {
                    'TwoStage': {'A': [], 'B': []},
                    'Vanilla': {'A': [], 'B': []}
                }
            
            pdf_path = os.path.join(SCHEDULES_DIR, pdf_name)
            gt = {} # Empty ground truth
            print(f"\n[{i}/{len(pdf_files)}] Processing {pdf_name}...")
            
            # --- TWO-STAGE RUNS ---
            current_runs = len(study_data[schedule_id]['TwoStage']['A'])
            if current_runs < N_RUNS:
                print(f"  Running Two-Stage ({N_RUNS - current_runs} runs remaining)...")
                for r in range(current_runs, N_RUNS):
                    print(f"    Run {r+1}/{N_RUNS}...", end=" ", flush=True)
                    try:
                        res = run_two_stage_pipeline(client, pdf_path, schedule_id, gt)
                        vals = extract_12m_from_twostage(res)
                        study_data[schedule_id]['TwoStage']['A'].append(vals['A'])
                        study_data[schedule_id]['TwoStage']['B'].append(vals['B'])
                        print(f"✓ (A={vals['A']}, B={vals['B']})")
                    except Exception as e:
                        print(f"Error: {e}")
                        traceback.print_exc()
                    
                    # Incremental Save
                    with open(INTERMEDIATE_FILE, 'w') as f:
                        json.dump(study_data, f, indent=2)
                    time.sleep(1)
            else:
                print(f"  Two-Stage: Already verified ({current_runs} runs)")

            # --- VANILLA RUNS ---
            current_runs = len(study_data[schedule_id]['Vanilla']['A'])
            if current_runs < N_RUNS:
                print(f"  Running Vanilla ({N_RUNS - current_runs} runs remaining)...")
                for r in range(current_runs, N_RUNS):
                    print(f"    Run {r+1}/{N_RUNS}...", end=" ", flush=True)
                    try:
                        res = run_vanilla_extraction(client, pdf_path)
                        vals = extract_12m_from_vanilla(res)
                        study_data[schedule_id]['Vanilla']['A'].append(vals['A'])
                        study_data[schedule_id]['Vanilla']['B'].append(vals['B'])
                        print(f"✓ (A={vals['A']}, B={vals['B']})")
                    except Exception as e:
                        print(f"Error: {e}")
                        traceback.print_exc()
                    
                    # Incremental Save
                    with open(INTERMEDIATE_FILE, 'w') as f:
                        json.dump(study_data, f, indent=2)
                    time.sleep(1)
            else:
                 print(f"  Vanilla: Already verified ({current_runs} runs)")
                 
    except KeyboardInterrupt:
        print("\nStopped by user. Saving progress...")
    
    # Final Save
    with open(RESULTS_FILE, 'w') as f:
        json.dump(study_data, f, indent=2)
    print(f"\nFinal results saved to {RESULTS_FILE}")
    
    # --- REPORTING ---
    print("\n" + "="*80)
    print(f"{'ID':<30} | {'Method':<10} | {'Arm':<3} | {'Median':<6} | {'IQR':<6} | {'Values':<20}")
    print("-" * 80)
    
    for sid, data in sorted(study_data.items()):
        short_id = sid[:28] + ".." if len(sid) > 30 else sid
        for method in ['TwoStage', 'Vanilla']:
            for arm in ['A', 'B']:
                vals = data[method][arm]
                stats = calculate_stats(vals)
                val_str = str(stats['values'])
                if len(val_str) > 20: val_str = val_str[:17] + "..."
                
                print(f"{short_id:<30} | {method:<10} | {arm:<3} | {stats['median']:<6.1f} | {stats['iqr']:<6.1f} | {val_str}")
        print("-" * 80)

if __name__ == "__main__":
    main()
