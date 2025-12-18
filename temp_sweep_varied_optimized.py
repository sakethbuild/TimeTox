#!/usr/bin/env python3
"""
Temperature Sweep: 6 temperatures per schedule, OPTIMIZED with parallelization
"""

import os
import json
import statistics
import time
from pathlib import Path
from typing import Dict, List, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Error: google-genai not installed.")
    exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from agent_comparison import (
    MODEL, SCHEDULES_FOLDER, GROUND_TRUTH_FILE, TIME_WINDOWS,
    PROMPT_OPTIMIZED, load_ground_truth, extract_schedule_id,
    parse_json_response, map_arm_to_letter, setup_client
)

# Thread-safe print lock
print_lock = Lock()


def safe_print(*args, **kwargs):
    """Thread-safe print function."""
    with print_lock:
        print(*args, **kwargs)


def call_gemini(client: genai.Client, uploaded_file, prompt: str, temperature: float) -> str:
    """Make a single Gemini API call."""
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_uri(file_uri=uploaded_file.uri, mime_type="application/pdf"),
                types.Part.from_text(text=prompt),
            ],
        ),
    ]
    config = types.GenerateContentConfig(temperature=temperature)
    response = client.models.generate_content(model=MODEL, contents=contents, config=config)
    return response.text


def process_single_call(args: Tuple) -> Dict[str, Any]:
    """Process a single API call. Returns result dict or None on error."""
    client, uploaded_file, prompt, temp, schedule_id, ground_truth = args
    
    try:
        start_time = time.time()
        response = call_gemini(client, uploaded_file, prompt, temp)
        elapsed = time.time() - start_time
        
        arms = parse_json_response(response)
        
        # Calculate accuracy if ground truth available
        matches = None
        if schedule_id in ground_truth:
            matches = sum(
                1 for arm in arms
                for window in TIME_WINDOWS
                if map_arm_to_letter(arm.get('arm_name', ''), arm.get('intervention_type', '')) in ground_truth[schedule_id]
                and arm.get('healthcare_contact_days', {}).get(window) == ground_truth[schedule_id][map_arm_to_letter(arm.get('arm_name', ''), arm.get('intervention_type', ''))].get(window)
            )
        
        safe_print(f"  T={temp} ✓ ({elapsed:.1f}s)" + (f" {matches}/12" if matches is not None else ""))
        
        return {
            'arms': arms,
            'temperature': temp,
            'schedule_id': schedule_id,
            'success': True,
            'elapsed': elapsed
        }
    except Exception as e:
        safe_print(f"  T={temp} ✗ {e}")
        return {
            'arms': [],
            'temperature': temp,
            'schedule_id': schedule_id,
            'success': False,
            'error': str(e)
        }


def upload_file(client: genai.Client, pdf_path: Path) -> Tuple[str, Any]:
    """Upload a file and return (schedule_id, uploaded_file)."""
    filename = os.path.basename(pdf_path)
    schedule_id = extract_schedule_id(filename)
    uploaded_file = client.files.upload(file=str(pdf_path))
    return schedule_id, uploaded_file


def main():
    print("=" * 70)
    print("Temperature Sweep: 5 temps per schedule (0.0-0.4, OPTIMIZED - PARALLEL)")
    print("=" * 70)
    
    client = setup_client()
    ground_truth = load_ground_truth(GROUND_TRUTH_FILE)
    
    pdf_folder = Path(SCHEDULES_FOLDER)
    pdf_files = sorted(pdf_folder.glob("*.pdf"))[:2]
    
    temperatures = [0.0, 0.1, 0.2, 0.3, 0.4]
    
    all_samples = {}
    
    total_calls = len(pdf_files) * len(temperatures)
    print(f"Running {len(pdf_files)} schedules × {len(temperatures)} temps = {total_calls} calls")
    print(f"Using parallel execution with max_workers=10\n")
    
    start_total = time.time()
    
    # STEP 1: Upload all files in parallel
    print("Step 1: Uploading files...")
    uploaded_files = {}
    with ThreadPoolExecutor(max_workers=2) as executor:
        upload_futures = {executor.submit(upload_file, client, pdf_path): pdf_path 
                         for pdf_path in pdf_files}
        
        for future in as_completed(upload_futures):
            try:
                schedule_id, uploaded_file = future.result()
                filename = os.path.basename(upload_futures[future])
                uploaded_files[schedule_id] = uploaded_file
                all_samples[schedule_id] = []
                safe_print(f"  Uploaded: {filename} → {schedule_id}")
            except Exception as e:
                safe_print(f"  Upload failed for {upload_futures[future]}: {e}")
    
    print(f"\nStep 2: Processing {total_calls} API calls in parallel...\n")
    
    # STEP 2: Process all API calls in parallel
    # Prepare all call arguments
    call_args = []
    for schedule_id, uploaded_file in uploaded_files.items():
        for temp in temperatures:
            call_args.append((
                client, uploaded_file, PROMPT_OPTIMIZED, temp, 
                schedule_id, ground_truth
            ))
    
    # Execute all calls in parallel (with max_workers to avoid rate limits)
    # Adjust max_workers based on API rate limits (10 is usually safe)
    completed = 0
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_args = {executor.submit(process_single_call, args): args 
                         for args in call_args}
        
        for future in as_completed(future_to_args):
            completed += 1
            try:
                result = future.result()
                if result and result.get('success'):
                    all_samples[result['schedule_id']].append(result)
            except Exception as e:
                safe_print(f"  Unexpected error: {e}")
            
            # Progress indicator
            if completed % 5 == 0:
                safe_print(f"  Progress: {completed}/{total_calls} calls completed")
    
    elapsed_total = time.time() - start_total
    print(f"\n✓ Completed {completed}/{total_calls} calls in {elapsed_total:.1f}s")
    print(f"  Average: {elapsed_total/total_calls:.2f}s per call")
    print(f"  Speedup: ~{min(len(temperatures), 10)}x faster than sequential\n")
    
    # Save results to file for later analysis
    results_file = "temp_sweep_results.json"
    with open(results_file, 'w') as f:
        json.dump(all_samples, f, indent=2)
    print(f"Results saved to {results_file}\n")
    
    # Stats - PER SCHEDULE, PER ARM
    print("=" * 70)
    print("MEDIAN AND IQR BY SCHEDULE, PER ARM")
    print("=" * 70)
    
    for schedule_id in sorted(all_samples.keys()):
        print(f"\nSchedule {schedule_id}:")
        
        for arm_letter in ['A', 'B']:
            print(f"\n  Arm {arm_letter}:")
            print(f"  {'Window':<15} {'Median':>10} {'IQR':>10} {'Range':>15} {'GT':>8} {'Diff':>8}")
            print("  " + "-" * 70)
            
            for window in TIME_WINDOWS:
                values = []
                for sample in all_samples[schedule_id]:
                    for arm in sample.get('arms', []):
                        if map_arm_to_letter(arm.get('arm_name', ''), arm.get('intervention_type', '')) == arm_letter:
                            val = arm.get('healthcare_contact_days', {}).get(window)
                            if isinstance(val, int):
                                values.append(val)
                
                if values:
                    sorted_vals = sorted(values)
                    n = len(sorted_vals)
                    median = statistics.median(values)
                    q1 = statistics.median(sorted_vals[:n//2]) if n >= 4 else sorted_vals[0]
                    q3 = statistics.median(sorted_vals[n//2 + n%2:]) if n >= 4 else sorted_vals[-1]
                    iqr = q3 - q1
                    
                    # Get ground truth for comparison
                    gt_val = None
                    if schedule_id in ground_truth and arm_letter in ground_truth[schedule_id]:
                        gt_val = ground_truth[schedule_id][arm_letter].get(window, None)
                    
                    gt_str = f"{gt_val:>8}" if gt_val is not None else "      N/A"
                    diff_str = f"{median - gt_val:>+8.1f}" if gt_val is not None else "      N/A"
                    
                    print(f"  {window:<15} {median:>10.1f} {iqr:>10.1f} [{min(values)}, {max(values)}] {gt_str} {diff_str}")
    
    # Also show combined stats across all schedules
    print("\n" + "=" * 70)
    print("MEDIAN AND IQR ACROSS ALL SCHEDULES (COMBINED)")
    print("=" * 70)
    
    for arm_letter in ['A', 'B']:
        print(f"\nArm {arm_letter}:")
        print(f"{'Window':<15} {'Median':>10} {'IQR':>10} {'Range':>15}")
        print("-" * 55)
        
        for window in TIME_WINDOWS:
            values = []
            for schedule_id, samples in all_samples.items():
                for sample in samples:
                    for arm in sample.get('arms', []):
                        if map_arm_to_letter(arm.get('arm_name', ''), arm.get('intervention_type', '')) == arm_letter:
                            val = arm.get('healthcare_contact_days', {}).get(window)
                            if isinstance(val, int):
                                values.append(val)
            
            if values:
                sorted_vals = sorted(values)
                n = len(sorted_vals)
                median = statistics.median(values)
                q1 = statistics.median(sorted_vals[:n//2]) if n >= 4 else sorted_vals[0]
                q3 = statistics.median(sorted_vals[n//2 + n%2:]) if n >= 4 else sorted_vals[-1]
                iqr = q3 - q1
                print(f"{window:<15} {median:>10.1f} {iqr:>10.1f} [{min(values)}, {max(values)}]")
    
    # Accuracy by temp
    print("\n" + "=" * 70)
    print("ACCURACY BY TEMPERATURE")
    print("=" * 70)
    print(f"\n{'Temp':>8} {'Exact':>10} {'Clinical':>10} {'MAE':>10}")
    print("-" * 42)
    
    for temp in temperatures:
        correct = total = within3 = 0
        errors = []
        
        for schedule_id, samples in all_samples.items():
            if schedule_id not in ground_truth:
                continue
            for sample in samples:
                if sample['temperature'] != temp:
                    continue
                for arm in sample.get('arms', []):
                    letter = map_arm_to_letter(arm.get('arm_name', ''), arm.get('intervention_type', ''))
                    if letter not in ground_truth[schedule_id]:
                        continue
                    for window in TIME_WINDOWS:
                        gt = ground_truth[schedule_id][letter].get(window, 0)
                        ext = arm.get('healthcare_contact_days', {}).get(window, 0)
                        if isinstance(ext, str):
                            ext = int(ext) if ext.isdigit() else 0
                        total += 1
                        diff = abs(ext - gt)
                        errors.append(diff)
                        if ext == gt:
                            correct += 1
                            within3 += 1
                        elif diff <= 3:
                            within3 += 1
        
        if total:
            print(f"{temp:>8.1f} {correct/total:>9.1%} {within3/total:>9.1%} {sum(errors)/len(errors):>9.2f}")
    
    print("\nDone!")


if __name__ == "__main__":
    main()

