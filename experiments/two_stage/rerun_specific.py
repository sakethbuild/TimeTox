#!/usr/bin/env python3
"""Re-run specific schedules and merge with existing results."""

import sys
import os
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from experiments.two_stage.pipeline import run_two_stage_pipeline, load_ground_truth
from dotenv import load_dotenv
load_dotenv(override=True)

from google import genai

def main():
    schedule_ids = ['15', '20']
    
    print("=" * 90)
    print(f"Re-running Schedules: {', '.join(schedule_ids)}")
    print("=" * 90)
    
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    gt_all = load_ground_truth()
    
    results = []
    
    for schedule_id in schedule_ids:
        schedules_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'synthetic_schedules')
        pdf_files = [f for f in os.listdir(schedules_dir) 
                     if f.startswith(f'synthetic_schedule_{schedule_id}') and f.endswith('.pdf')]
        
        if not pdf_files:
            print(f"\n⚠️ No PDF found for schedule {schedule_id}")
            continue
        
        pdf_path = os.path.join(schedules_dir, pdf_files[0])
        gt = gt_all.get(schedule_id, {})
        
        print(f"\n{'─' * 90}")
        print(f"Processing Schedule {schedule_id}: {gt.get('disease', 'Unknown')[:50]}")
        print(f"{'─' * 90}")
        
        result = run_two_stage_pipeline(client, pdf_path, schedule_id, gt)
        results.append(result)
        
        if 'error' not in result:
            m_a = result.get('metrics_A', {})
            m_b = result.get('metrics_B', {})
            print(f"  ✓ Done. Exact: A={m_a.get('exact_accuracy', 0):.0%}, B={m_b.get('exact_accuracy', 0):.0%}")
        else:
            print(f"  ✗ Error: {result['error']}")
        
        import time
        time.sleep(1)
    
    # Save results
    output_path = os.path.join(os.path.dirname(__file__), '..', '..', 'results', 
                               f'two_stage_rerun_15_20.json')
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {output_path}")
    return results

if __name__ == "__main__":
    main()

