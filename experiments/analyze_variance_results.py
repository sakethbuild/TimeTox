#!/usr/bin/env python3
"""
Analyze Variance Study Results
Calculates Median and IQR for Real PDF runs.
"""

import json
import os
import statistics
import sys
from typing import Dict, List, Any

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_FILE = os.path.join(BASE_DIR, 'results', 'variance_study_intermediate.json') # Using intermediate as it was confirmed populated
REPORT_FILE = os.path.join(BASE_DIR, 'variance_report.md')

def calculate_stats(values: List[int]) -> Dict[str, Any]:
    """Calculate median and IQR."""
    clean_vals = [v for v in values if v is not None]
    if not clean_vals:
        return {'median': 0, 'iqr': 0, 'n': 0, 'values': []}
    
    if len(clean_vals) < 2:
         return {'median': clean_vals[0], 'iqr': 0, 'n': len(clean_vals), 'values': clean_vals}
         
    qt = statistics.quantiles(clean_vals, n=4)
    iqr = qt[2] - qt[0]
    return {
        'median': statistics.median(clean_vals),
        'iqr': iqr,
        'n': len(clean_vals),
        'values': sorted(clean_vals)
    }

def main():
    if not os.path.exists(RESULTS_FILE):
        print(f"Error: File not found: {RESULTS_FILE}")
        return

    print(f"Loading results from: {RESULTS_FILE}")
    with open(RESULTS_FILE, 'r') as f:
        data = json.load(f)

    # Generate Report Content
    report_lines = []
    report_lines.append("# Variance Study Report: Two-Stage vs Vanilla (Real PDFs)")
    report_lines.append(f"**Generated:** {os.popen('date').read().strip()}")
    report_lines.append("\n## Executive Summary")
    report_lines.append("Analysis of the 12-month visit counts across 5 runs for each pipeline.")
    report_lines.append("\n## Detailed Statistics")
    
    # Table Header
    headers = ["PDF ID", "Method", "Arm", "Median", "IQR", "Values (Sorted)"]
    row_fmt = "| {0:<35} | {1:<10} | {2:<3} | {3:<6} | {4:<6} | {5:<20} |"
    
    report_lines.append(f"| {' | '.join(headers)} |")
    report_lines.append(f"| {' | '.join(['-'*len(h) for h in headers])} |")

    print("-" * 100)
    print(f"{'PDF ID':<35} | {'Method':<10} | {'Arm':<3} | {'Median':<6} | {'IQR':<6} | {'Values':<20}")
    print("-" * 100)

    for pdf_name, results in sorted(data.items()):
        # Shorten name for display if needed
        short_name = pdf_name
        if len(short_name) > 35:
            short_name = short_name[:32] + "..."

        for method in ['TwoStage', 'Vanilla']:
            method_data = results.get(method, {})
            for arm in ['A', 'B']:
                vals = method_data.get(arm, [])
                stats = calculate_stats(vals)
                
                # Format values
                val_str = str(stats['values'])
                
                # Print to console
                print(f"{short_name:<35} | {method:<10} | {arm:<3} | {stats['median']:<6.1f} | {stats['iqr']:<6.1f} | {val_str}")
                
                # Add to MD report
                report_lines.append(row_fmt.format(
                    pdf_name, 
                    method, 
                    arm, 
                    f"{stats['median']:.1f}", 
                    f"{stats['iqr']:.1f}", 
                    val_str
                ))

    # Write Report
    with open(REPORT_FILE, 'w') as f:
        f.write('\n'.join(report_lines))
    
    print("-" * 100)
    print(f"\nReport saved to: {REPORT_FILE}")

if __name__ == "__main__":
    main()
