#!/usr/bin/env python3
"""
Analyze saved temperature sweep results - shows per-schedule, per-arm statistics
without needing to re-run API calls.

Usage:
    python3 experiments/analyze_temp_sweep.py
"""

import sys
import json
import statistics
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from experiments.agent_comparison import (
    GROUND_TRUTH_FILE, TIME_WINDOWS,
    load_ground_truth, map_arm_to_letter
)

def analyze_results(results_file="temp_sweep_results.json"):
    """Analyze saved temperature sweep results."""
    
    # Load results
    if not Path(results_file).exists():
        print(f"Error: {results_file} not found. Run temp_sweep_varied_optimized.py first.")
        return
    
    with open(results_file, 'r') as f:
        all_samples = json.load(f)
    
    ground_truth = load_ground_truth(GROUND_TRUTH_FILE)
    
    # Stats - PER SCHEDULE, PER ARM
    print("=" * 80)
    print("MEDIAN AND IQR BY SCHEDULE, PER ARM")
    print("=" * 80)
    
    for schedule_id in sorted(all_samples.keys()):
        print(f"\nSchedule {schedule_id}:")
        
        for arm_letter in ['A', 'B']:
            print(f"\n  Arm {arm_letter}:")
            print(f"  {'Window':<15} {'Median':>10} {'IQR':>10} {'Range':>15} {'GT':>8} {'Diff':>8} {'%Err':>8}")
            print("  " + "-" * 80)
            
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
                    q1 = sorted_vals[n // 4] if n > 1 else sorted_vals[0]
                    q3 = sorted_vals[(3 * n) // 4] if n > 1 else sorted_vals[-1]
                    iqr = q3 - q1
                    
                    # Get ground truth for comparison
                    gt_val = None
                    if schedule_id in ground_truth and arm_letter in ground_truth[schedule_id]:
                        gt_val = ground_truth[schedule_id][arm_letter].get(window, None)
                    
                    gt_str = f"{gt_val:>8}" if gt_val is not None else "      N/A"
                    if gt_val is not None:
                        diff = median - gt_val
                        pct_err = abs(diff) / gt_val * 100 if gt_val > 0 else 0
                        diff_str = f"{diff:>+8.1f}"
                        pct_str = f"{pct_err:>7.1f}%"
                    else:
                        diff_str = "      N/A"
                        pct_str = "     N/A"
                    
                    print(f"  {window:<15} {median:>10.1f} {iqr:>10.1f} [{min(values):>3}, {max(values):>3}] {gt_str} {diff_str} {pct_str}")
    
    # Also show combined stats across all schedules
    print("\n" + "=" * 80)
    print("MEDIAN AND IQR ACROSS ALL SCHEDULES (COMBINED)")
    print("=" * 80)
    
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
                q1 = sorted_vals[n // 4] if n > 1 else sorted_vals[0]
                q3 = sorted_vals[(3 * n) // 4] if n > 1 else sorted_vals[-1]
                iqr = q3 - q1
                print(f"{window:<15} {median:>10.1f} {iqr:>10.1f} [{min(values)}, {max(values)}]")


if __name__ == "__main__":
    analyze_results()

