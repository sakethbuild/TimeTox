#!/usr/bin/env python3
"""Merge re-run results for schedules 15 and 20 with existing 20-schedule results."""

import json
import sys
from pathlib import Path

def merge_results():
    # Load original 20-schedule results
    original_path = Path(__file__).parent.parent.parent / 'results' / 'two_stage_results_20251218_150314.json'
    
    # Load re-run results (if they exist)
    rerun_path = Path(__file__).parent.parent.parent / 'results' / 'two_stage_rerun_15_20.json'
    
    print("Loading original results...")
    with open(original_path) as f:
        original = json.load(f)
    
    print(f"Original: {original['num_schedules']} schedules, {original['summary_metrics']['total_comparisons']} comparisons")
    
    # Check if rerun exists
    if rerun_path.exists():
        print("Loading re-run results...")
        with open(rerun_path) as f:
            rerun_results = json.load(f)
        
        # Replace schedules 15 and 20 in original
        schedule_map = {r['schedule_id']: r for r in original['per_schedule_results']}
        
        for rerun_result in rerun_results:
            sid = rerun_result['schedule_id']
            if sid in ['15', '20']:
                print(f"  Replacing schedule {sid}...")
                schedule_map[sid] = rerun_result
        
        original['per_schedule_results'] = [schedule_map[sid] for sid in sorted(schedule_map.keys(), key=int)]
    else:
        print("⚠️  Re-run results not found. Using original results.")
        print("   To re-run schedules 15 and 20, run: python3 experiments/two_stage/rerun_specific.py")
        return original
    
    # Recalculate metrics
    print("\nRecalculating metrics...")
    from experiments.two_stage.pipeline import WINDOWS, compute_metrics, load_ground_truth
    
    gt_all = load_ground_truth()
    
    total_windows = 0
    exact_matches = 0
    within_3 = 0
    total_error = 0
    
    for result in original['per_schedule_results']:
        if 'error' in result:
            continue
        
        sid = result['schedule_id']
        gt = gt_all.get(sid, {})
        
        for arm in ['A', 'B']:
            ext = result.get('extracted', {}).get(arm, {})
            gt_arm = gt.get(arm, {})
            
            if not ext or not gt_arm:
                continue
            
            m = compute_metrics(ext, gt_arm)
            total_windows += len(WINDOWS)
            exact_matches += m.get('exact_matches', 0)
            within_3 += m.get('within_3', 0)
            total_error += m.get('total_error', 0)
    
    # Update summary metrics
    original['summary_metrics'] = {
        'exact_accuracy': exact_matches / total_windows if total_windows > 0 else 0,
        'clinical_accuracy': within_3 / total_windows if total_windows > 0 else 0,
        'mae': total_error / total_windows if total_windows > 0 else 0,
        'total_comparisons': total_windows,
        'exact_matches': exact_matches,
        'within_3': within_3,
    }
    
    # Save merged results
    output_path = Path(__file__).parent.parent.parent / 'results' / 'two_stage_results_20_merged.json'
    with open(output_path, 'w') as f:
        json.dump(original, f, indent=2, default=str)
    
    print(f"\n✅ Merged results saved to: {output_path}")
    print(f"\nUpdated Metrics:")
    print(f"  Exact Match: {original['summary_metrics']['exact_accuracy']:.1%}")
    print(f"  Clinical (±3): {original['summary_metrics']['clinical_accuracy']:.1%}")
    print(f"  MAE: {original['summary_metrics']['mae']:.2f} days")
    
    return original

if __name__ == "__main__":
    merge_results()

