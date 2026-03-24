#!/usr/bin/env python3
"""
Analyze Variance of Vanilla Extraction on Summaries

Reads the 5 run CSVs (vanilla_summaries_run1.csv ... run5.csv),
calculates Median and IQR for the '12_months' visit count,
and generates a summary report.
"""

import os
import pandas as pd
import numpy as np
import glob
from pathlib import Path

OUTPUT_DIR = "results"
RUN_FILES_PATTERN = os.path.join(OUTPUT_DIR, "vanilla_summaries_dataset*.csv")

def load_data():
    files = sorted(glob.glob(RUN_FILES_PATTERN))
    print(f"Found {len(files)} run files: {[os.path.basename(f) for f in files]}")
    
    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f)
            # Add run ID based on filename
            filename = os.path.basename(f)
            if "run" in filename:
                # e.g. vanilla_summaries_dataset_run2.csv -> run2
                run_id = filename.replace("vanilla_summaries_dataset_", "").replace(".csv", "")
            else:
                # vanilla_summaries_dataset.csv -> run1
                run_id = "run1"
            
            df['run_id'] = run_id
            dfs.append(df)
        except Exception as e:
            print(f"Error reading {f}: {e}")
            
    if not dfs:
        print("No data found!")
        return None
        
    combined_df = pd.concat(dfs, ignore_index=True)
    return combined_df

def analyze_variance(df):
    # Convert 12_months to numeric, coercing errors to NaN
    df['12_months'] = pd.to_numeric(df['12_months'], errors='coerce')
    
    # Filter out rows with NaN in 12_months (failed extractions)
    valid_df = df.dropna(subset=['12_months'])
    
    print(f"\nTotal rows: {len(df)}")
    print(f"Valid rows (numeric 12_months): {len(valid_df)}")
    
    # Group by filename and arm_name
    # We use a combined key because arm names might vary slightly? 
    # Actually, let's assume arm names are stable prompt outputs or just group by filename/arm_name.
    # If arm names are unstable (LLM generated), we might face issues, but usually they are robust enough or we verify.
    # For this analysis, we trust the LLM output arm names are consistent enough or we just group by filename and list all values.
    
    # Check consistency of arm names count per file?
    # Let's group by filename and arm_name.
    
    stats = valid_df.groupby(['filename', 'arm_name'])['12_months'].agg(
        n='count',
        median='median',
        q1=lambda x: x.quantile(0.25),
        q3=lambda x: x.quantile(0.75),
        mean='mean',
        std='std',
        min='min',
        max='max'
    ).reset_index()
    
    stats['iqr'] = stats['q3'] - stats['q1']
    
    # Calculate overall stats
    avg_iqr = stats['iqr'].mean()
    median_iqr = stats['iqr'].median()
    
    print("\n" + "="*50)
    print("VARIANCE SUMMARY (12-Month Visits)")
    print("="*50)
    print(f"Number of unique arms analyzed: {len(stats)}")
    print(f"Average IQR across arms: {avg_iqr:.2f}")
    print(f"Median IQR across arms:  {median_iqr:.2f}")
    print("-" * 50)
    
    # Breakdown by IQR buckets
    print("IQR Distribution:")
    print(f"  IQR = 0 (Perfect Stability): {len(stats[stats['iqr'] == 0])} arms ({len(stats[stats['iqr'] == 0])/len(stats)*100:.1f}%)")
    print(f"  IQR <= 3 (Clinical Stability): {len(stats[stats['iqr'] <= 3])} arms ({len(stats[stats['iqr'] <= 3])/len(stats)*100:.1f}%)")
    print(f"  IQR > 3 (High Variance):     {len(stats[stats['iqr'] > 3])} arms ({len(stats[stats['iqr'] > 3])/len(stats)*100:.1f}%)")
    
    return stats

def main():
    print("Loading data...")
    df = load_data()
    if df is None:
        return
        
    print("Analyzing...")
    stats = analyze_variance(df)
    
    # Save detailed stats
    output_path = os.path.join(OUTPUT_DIR, "vanilla_summaries_variance_analysis.csv")
    stats.to_csv(output_path, index=False)
    print(f"\nDetailed analysis saved to: {output_path}")

    # Save high variance cases for inspection
    high_var = stats[stats['iqr'] > 3].sort_values('iqr', ascending=False)
    high_var_path = os.path.join(OUTPUT_DIR, "vanilla_summaries_high_variance.csv")
    high_var.to_csv(high_var_path, index=False)
    print(f"High variance cases (>3) saved to: {high_var_path}")

if __name__ == "__main__":
    main()
