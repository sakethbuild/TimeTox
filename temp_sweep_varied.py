#!/usr/bin/env python3
"""
Temperature Sweep: 6 temperatures per schedule, no delays
"""

import os
import json
import statistics
from pathlib import Path
from typing import Dict, List, Any

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


def main():
    print("=" * 70)
    print("Temperature Sweep: 6 temps per schedule (no delays)")
    print("=" * 70)
    
    client = setup_client()
    ground_truth = load_ground_truth(GROUND_TRUTH_FILE)
    
    pdf_folder = Path(SCHEDULES_FOLDER)
    pdf_files = sorted(pdf_folder.glob("*.pdf"))[:5]
    
    temperatures = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    
    all_samples = {}
    
    print(f"Running {len(pdf_files)} schedules × {len(temperatures)} temps = {len(pdf_files)*len(temperatures)} calls\n")
    
    for i, pdf_path in enumerate(pdf_files):
        filename = os.path.basename(pdf_path)
        schedule_id = extract_schedule_id(filename)
        all_samples[schedule_id] = []
        
        print(f"Schedule {i+1}/5: {filename}")
        
        # Upload once
        uploaded_file = client.files.upload(file=str(pdf_path))
        
        for temp in temperatures:
            print(f"  T={temp}...", end=" ", flush=True)
            
            try:
                response = call_gemini(client, uploaded_file, PROMPT_OPTIMIZED, temp)
                arms = parse_json_response(response)
                
                all_samples[schedule_id].append({
                    'arms': arms,
                    'temperature': temp,
                    'schedule_id': schedule_id
                })
                
                # Quick accuracy
                if schedule_id in ground_truth:
                    matches = sum(
                        1 for arm in arms
                        for window in TIME_WINDOWS
                        if map_arm_to_letter(arm.get('arm_name', ''), arm.get('intervention_type', '')) in ground_truth[schedule_id]
                        and arm.get('healthcare_contact_days', {}).get(window) == ground_truth[schedule_id][map_arm_to_letter(arm.get('arm_name', ''), arm.get('intervention_type', ''))].get(window)
                    )
                    print(f"✓ {matches}/12", end=" ")
            except Exception as e:
                print(f"✗ {e}", end=" ")
        
        print()
    
    # Stats
    print("\n" + "=" * 70)
    print("MEDIAN AND IQR BY ARM/WINDOW")
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
