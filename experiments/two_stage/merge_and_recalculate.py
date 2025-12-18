#!/usr/bin/env python3
"""Merge re-run results for schedules 15 and 20 with existing 20-schedule results and recalculate metrics."""

import json
from pathlib import Path

# Import from pipeline
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from experiments.two_stage.pipeline import WINDOWS

def compute_metrics(extracted, ground_truth):
    """Compute accuracy metrics for a single arm."""
    metrics = {'windows': {}, 'exact_matches': 0, 'within_3': 0, 'total_error': 0}
    
    for w in WINDOWS:
        gt = ground_truth.get(w, 0)
        ext = extracted.get(w, 0)
        diff = ext - gt
        abs_diff = abs(diff)
        
        metrics['windows'][w] = {
            'gt': gt,
            'extracted': ext,
            'diff': diff,
            'match': diff == 0,
            'within_3': abs_diff <= 3
        }
        
        if diff == 0:
            metrics['exact_matches'] += 1
        if abs_diff <= 3:
            metrics['within_3'] += 1
        metrics['total_error'] += abs_diff
    
    metrics['exact_accuracy'] = metrics['exact_matches'] / len(WINDOWS)
    metrics['clinical_accuracy'] = metrics['within_3'] / len(WINDOWS)
    metrics['mae'] = metrics['total_error'] / len(WINDOWS)
    
    return metrics

def load_ground_truth():
    """Load ground truth from CSV."""
    import csv
    gt_all = {}
    csv_path = Path(__file__).parent.parent.parent / 'synthetic_schedules' / 'ground_truth.csv'
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            schedule_id = row['schedule_id']
            arm = row['arm']
            
            if schedule_id not in gt_all:
                gt_all[schedule_id] = {'complexity': row['complexity'], 'disease': row['disease']}
            
            gt_all[schedule_id][arm] = {
                'screening': int(row['screening_days']),
                '1_month': int(row['month1_days']),
                '3_months': int(row['month3_days']),
                '6_months': int(row['month6_days']),
                '9_months': int(row['month9_days']),
                '12_months': int(row['month12_days'])
            }
    return gt_all

def main():
    # Load original 20-schedule results
    original_path = Path(__file__).parent.parent.parent / 'results' / 'two_stage_results_20251218_150314.json'
    
    print("Loading original 20-schedule results...")
    with open(original_path) as f:
        original = json.load(f)
    
    print(f"Original: {original['num_schedules']} schedules, {original['summary_metrics']['total_comparisons']} comparisons")
    
    # Load re-run results
    rerun_15_path = Path(__file__).parent.parent.parent / 'results' / 'two_stage_rerun_15.json'
    rerun_20_path = Path(__file__).parent.parent.parent / 'results' / 'two_stage_rerun_20.json'
    
    # Replace schedules 15 and 20
    schedule_map = {r['schedule_id']: r for r in original['per_schedule_results']}
    
    if rerun_15_path.exists():
        with open(rerun_15_path) as f:
            rerun_15 = json.load(f)
        schedule_15 = rerun_15['schedule_15']
        print(f"\n✓ Replacing schedule 15 (Arm A was empty, now has {len(schedule_15.get('extracted', {}).get('A', {}))} values)")
        schedule_map['15'] = schedule_15
    
    if rerun_20_path.exists():
        with open(rerun_20_path) as f:
            rerun_20 = json.load(f)
        schedule_20 = rerun_20['schedule_20']
        print(f"✓ Replacing schedule 20 (Arm A was empty, now has {len(schedule_20.get('extracted', {}).get('A', {}))} values)")
        schedule_map['20'] = schedule_20
    
    # Reorder
    original['per_schedule_results'] = [schedule_map[sid] for sid in sorted(schedule_map.keys(), key=int)]
    
    # Recalculate metrics
    print("\nRecalculating metrics...")
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
            
            # Update per-arm metrics in result
            result[f'metrics_{arm}'] = m
    
    # Update summary metrics
    old_metrics = original['summary_metrics']
    new_metrics = {
        'exact_accuracy': exact_matches / total_windows if total_windows > 0 else 0,
        'clinical_accuracy': within_3 / total_windows if total_windows > 0 else 0,
        'mae': total_error / total_windows if total_windows > 0 else 0,
        'total_comparisons': total_windows,
        'exact_matches': exact_matches,
        'within_3': within_3,
    }
    
    original['summary_metrics'] = new_metrics
    
    # Save merged results
    output_path = Path(__file__).parent.parent.parent / 'results' / 'two_stage_results_20_merged.json'
    with open(output_path, 'w') as f:
        json.dump(original, f, indent=2, default=str)
    
    print(f"\n{'='*70}")
    print("UPDATED METRICS (After Fixing Schedules 15 & 20)")
    print(f"{'='*70}")
    print(f"\nBefore (with empty Arm A in 15 & 20):")
    print(f"  Exact Match: {old_metrics['exact_accuracy']:.1%} ({old_metrics['exact_matches']}/{old_metrics['total_comparisons']})")
    print(f"  Clinical (±3): {old_metrics['clinical_accuracy']:.1%} ({old_metrics['within_3']}/{old_metrics['total_comparisons']})")
    print(f"  MAE: {old_metrics['mae']:.2f} days")
    
    print(f"\nAfter (with fixed Arm A extraction):")
    print(f"  Exact Match: {new_metrics['exact_accuracy']:.1%} ({new_metrics['exact_matches']}/{new_metrics['total_comparisons']})")
    print(f"  Clinical (±3): {new_metrics['clinical_accuracy']:.1%} ({new_metrics['within_3']}/{new_metrics['total_comparisons']})")
    print(f"  MAE: {new_metrics['mae']:.2f} days")
    
    print(f"\nChange:")
    print(f"  Exact Match: {new_metrics['exact_accuracy'] - old_metrics['exact_accuracy']:+.1%}")
    print(f"  Clinical (±3): {new_metrics['clinical_accuracy'] - old_metrics['clinical_accuracy']:+.1%}")
    print(f"  MAE: {new_metrics['mae'] - old_metrics['mae']:+.2f} days")
    
    print(f"\n✅ Merged results saved to: {output_path}")
    
    return original

if __name__ == "__main__":
    main()

