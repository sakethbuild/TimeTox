#!/usr/bin/env python3
"""
Vanilla Baseline Extraction - Full 20 Schedule Run

Runs the baseline (single-pass) extraction on all 20 synthetic schedules
and outputs results formatted for LaTeX tables.

Usage:
    python3 experiments/vanilla_baseline_full.py
"""

import os
import sys
import csv
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Error: google-genai not installed.")
    print("Run: pip install google-genai python-dotenv")
    exit(1)

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

# Import from core
from core.test_extraction import (
    EXTRACTION_PROMPT,
    load_ground_truth,
    extract_schedule_id,
    parse_json_response,
    map_arm_name_to_letter,
    TIME_WINDOWS,
)

# ============================================================================
# CONFIGURATION
# ============================================================================

MODEL = "gemini-3-flash-preview"  # Gemini 3 Flash
SCHEDULES_FOLDER = "synthetic_schedules"
GROUND_TRUTH_FILE = "synthetic_schedules/ground_truth.csv"
OUTPUT_DIR = "results"

# ============================================================================
# EXTRACTION FUNCTION
# ============================================================================

def extract_single_pdf(client: genai.Client, pdf_path: str, temperature: float = 0.1) -> Optional[Dict[str, Any]]:
    """Extract healthcare contact days from a single PDF."""
    filename = os.path.basename(pdf_path)
    
    try:
        # Upload file
        uploaded_file = client.files.upload(file=pdf_path)
        
        # Build content
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_uri(
                        file_uri=uploaded_file.uri,
                        mime_type="application/pdf"
                    ),
                    types.Part.from_text(text=EXTRACTION_PROMPT),
                ],
            ),
        ]
        
        # Configure generation
        generate_config = types.GenerateContentConfig(
            temperature=temperature,
        )
        
        # Generate with retry
        response_text = ""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=MODEL,
                    contents=contents,
                    config=generate_config,
                )
                response_text = response.text
                break
            except Exception as e:
                error_msg = str(e).lower()
                if any(kw in error_msg for kw in ['overloaded', 'unavailable', 'rate', 'quota', '503', '429']):
                    wait_time = 2 ** (attempt + 1)
                    print(f"    Retry {attempt + 1}/{max_retries} in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise e
        
        if not response_text:
            return None
        
        # Parse
        parsed_arms = parse_json_response(response_text)
        
        if parsed_arms:
            return {
                'filename': filename,
                'schedule_id': extract_schedule_id(filename),
                'arms': parsed_arms,
            }
        return None
        
    except Exception as e:
        print(f"    Error: {e}")
        return None


# ============================================================================
# COMPARISON AND METRICS
# ============================================================================

def compare_single(extracted: Dict[str, Any], ground_truth: Dict) -> Dict[str, Any]:
    """Compare extracted results against ground truth for a single schedule."""
    schedule_id = extracted['schedule_id']
    
    if schedule_id not in ground_truth:
        return {'schedule_id': schedule_id, 'error': 'Not in ground truth'}
    
    gt = ground_truth[schedule_id]
    results = {'schedule_id': schedule_id, 'arms': {}}
    
    for arm_data in extracted['arms']:
        arm_letter = map_arm_name_to_letter(
            arm_data.get('arm_name', ''),
            arm_data.get('intervention_type', '')
        )
        
        if arm_letter not in gt:
            results['arms'][arm_letter] = {'error': 'Arm not in ground truth'}
            continue
        
        gt_arm = gt[arm_letter]
        extracted_days = arm_data.get('healthcare_contact_days', {})
        
        arm_results = {'windows': {}}
        for window in TIME_WINDOWS:
            gt_val = gt_arm.get(window, 0)
            ext_val = extracted_days.get(window, 0)
            if isinstance(ext_val, str):
                ext_val = int(ext_val) if ext_val.isdigit() else 0
            
            arm_results['windows'][window] = {
                'gt': gt_val,
                'ext': ext_val,
                'diff': ext_val - gt_val,
                'match': ext_val == gt_val,
                'within_3': abs(ext_val - gt_val) <= 3,
            }
        
        arm_results['complexity'] = gt_arm.get('complexity', 'unknown')
        arm_results['disease'] = gt_arm.get('disease', 'unknown')
        results['arms'][arm_letter] = arm_results
    
    return results


def calculate_overall_metrics(all_comparisons: List[Dict]) -> Dict[str, Any]:
    """Calculate overall accuracy metrics."""
    total = 0
    exact_match = 0
    within_3 = 0
    total_error = 0
    
    # Per-window stats
    window_stats = {w: {'total': 0, 'exact': 0, 'within_3': 0, 'errors': []} for w in TIME_WINDOWS}
    
    # Per-complexity stats
    complexity_stats = {
        'simple': {'total': 0, 'exact': 0, 'within_3': 0},
        'moderate': {'total': 0, 'exact': 0, 'within_3': 0},
        'complex': {'total': 0, 'exact': 0, 'within_3': 0},
    }
    
    for result in all_comparisons:
        if 'error' in result:
            continue
        
        for arm_letter, arm_data in result.get('arms', {}).items():
            if 'error' in arm_data:
                continue
            
            complexity = arm_data.get('complexity', 'unknown')
            
            for window, data in arm_data.get('windows', {}).items():
                total += 1
                window_stats[window]['total'] += 1
                
                if complexity in complexity_stats:
                    complexity_stats[complexity]['total'] += 1
                
                if data['match']:
                    exact_match += 1
                    within_3 += 1
                    window_stats[window]['exact'] += 1
                    window_stats[window]['within_3'] += 1
                    if complexity in complexity_stats:
                        complexity_stats[complexity]['exact'] += 1
                        complexity_stats[complexity]['within_3'] += 1
                else:
                    abs_diff = abs(data['diff'])
                    total_error += abs_diff
                    window_stats[window]['errors'].append(abs_diff)
                    
                    if data['within_3']:
                        within_3 += 1
                        window_stats[window]['within_3'] += 1
                        if complexity in complexity_stats:
                            complexity_stats[complexity]['within_3'] += 1
    
    return {
        'total': total,
        'exact_match': exact_match,
        'within_3': within_3,
        'exact_accuracy': exact_match / total if total > 0 else 0,
        'clinical_accuracy': within_3 / total if total > 0 else 0,
        'mae': total_error / total if total > 0 else 0,
        'window_stats': window_stats,
        'complexity_stats': complexity_stats,
    }


# ============================================================================
# LATEX OUTPUT
# ============================================================================

def generate_latex_tables(all_comparisons: List[Dict], metrics: Dict, output_dir: str):
    """Generate LaTeX tables for the paper."""
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    
    # Table 1: Overall Summary
    latex_summary = r"""\begin{table}[htbp]
\centering
\caption{Vanilla Baseline Performance Summary (Gemini 2.0 Flash)}
\label{tab:vanilla_baseline_summary}
\begin{tabular}{lc}
\toprule
\textbf{Metric} & \textbf{Value} \\
\midrule
"""
    latex_summary += f"Exact Match Accuracy & {metrics['exact_accuracy']:.1%} \\\\\n"
    latex_summary += f"Clinical Accuracy ($\\pm$3 days) & {metrics['clinical_accuracy']:.1%} \\\\\n"
    latex_summary += f"Mean Absolute Error & {metrics['mae']:.2f} days \\\\\n"
    latex_summary += f"Total Comparisons & {metrics['total']} \\\\\n"
    latex_summary += f"Exact Matches & {metrics['exact_match']}/{metrics['total']} \\\\\n"
    latex_summary += f"Within $\\pm$3 Days & {metrics['within_3']}/{metrics['total']} \\\\\n"
    latex_summary += r"""\bottomrule
\end{tabular}
\end{table}
"""
    
    # Table 2: Per-Window Accuracy
    latex_window = r"""\begin{table}[htbp]
\centering
\caption{Vanilla Baseline Accuracy by Time Window}
\label{tab:vanilla_baseline_windows}
\begin{tabular}{lccc}
\toprule
\textbf{Time Window} & \textbf{Exact Match} & \textbf{$\pm$3 Days} & \textbf{MAE} \\
\midrule
"""
    for window in TIME_WINDOWS:
        stats = metrics['window_stats'][window]
        exact_acc = stats['exact'] / stats['total'] if stats['total'] > 0 else 0
        clin_acc = stats['within_3'] / stats['total'] if stats['total'] > 0 else 0
        mae = sum(stats['errors']) / len(stats['errors']) if stats['errors'] else 0
        
        window_display = window.replace('_', ' ').title()
        latex_window += f"{window_display} & {exact_acc:.1%} & {clin_acc:.1%} & {mae:.2f} \\\\\n"
    
    latex_window += r"""\bottomrule
\end{tabular}
\end{table}
"""
    
    # Table 3: Per-Complexity Accuracy
    latex_complexity = r"""\begin{table}[htbp]
\centering
\caption{Vanilla Baseline Accuracy by Schedule Complexity}
\label{tab:vanilla_baseline_complexity}
\begin{tabular}{lccc}
\toprule
\textbf{Complexity} & \textbf{N} & \textbf{Exact Match} & \textbf{$\pm$3 Days} \\
\midrule
"""
    for complexity in ['simple', 'moderate', 'complex']:
        stats = metrics['complexity_stats'][complexity]
        if stats['total'] > 0:
            exact_acc = stats['exact'] / stats['total']
            clin_acc = stats['within_3'] / stats['total']
            latex_complexity += f"{complexity.title()} & {stats['total']} & {exact_acc:.1%} & {clin_acc:.1%} \\\\\n"
    
    latex_complexity += r"""\bottomrule
\end{tabular}
\end{table}
"""
    
    # Table 4: Full Per-Schedule Results
    latex_detailed = r"""\begin{table}[htbp]
\centering
\caption{Vanilla Baseline: Per-Schedule Results}
\label{tab:vanilla_baseline_detailed}
\small
\begin{tabular}{clcccccccc}
\toprule
\textbf{ID} & \textbf{Arm} & \textbf{Scr} & \textbf{1M} & \textbf{3M} & \textbf{6M} & \textbf{9M} & \textbf{12M} & \textbf{Exact} & \textbf{$\pm$3} \\
\midrule
"""
    
    for result in sorted(all_comparisons, key=lambda x: x['schedule_id']):
        if 'error' in result:
            continue
        
        for arm_letter in ['A', 'B']:
            if arm_letter not in result.get('arms', {}):
                continue
            
            arm_data = result['arms'][arm_letter]
            if 'error' in arm_data:
                continue
            
            windows = arm_data['windows']
            row = [result['schedule_id'], arm_letter]
            
            exact_count = 0
            within_3_count = 0
            
            for window in TIME_WINDOWS:
                data = windows[window]
                diff = data['diff']
                if diff == 0:
                    row.append("\\checkmark")
                    exact_count += 1
                    within_3_count += 1
                elif abs(diff) <= 3:
                    row.append(f"{diff:+d}")
                    within_3_count += 1
                else:
                    row.append(f"\\textbf{{{diff:+d}}}")
            
            row.append(f"{exact_count}/6")
            row.append(f"{within_3_count}/6")
            
            latex_detailed += " & ".join(row) + " \\\\\n"
    
    latex_detailed += r"""\bottomrule
\end{tabular}
\end{table}
"""
    
    # Save all tables
    latex_file = os.path.join(output_dir, f"vanilla_baseline_latex_{timestamp}.tex")
    with open(latex_file, 'w') as f:
        f.write("% Vanilla Baseline Results - LaTeX Tables\n")
        f.write(f"% Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"% Model: {MODEL}\n\n")
        f.write(latex_summary)
        f.write("\n")
        f.write(latex_window)
        f.write("\n")
        f.write(latex_complexity)
        f.write("\n")
        f.write(latex_detailed)
    
    print(f"\nLaTeX tables saved to: {latex_file}")
    return latex_file


def save_json_results(all_comparisons: List[Dict], metrics: Dict, output_dir: str):
    """Save full results as JSON for later analysis."""
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    
    output = {
        'timestamp': datetime.now().isoformat(),
        'model': MODEL,
        'metrics': metrics,
        'per_schedule': all_comparisons,
    }
    
    json_file = os.path.join(output_dir, f"vanilla_baseline_results_{timestamp}.json")
    with open(json_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"JSON results saved to: {json_file}")
    return json_file


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 70)
    print("VANILLA BASELINE - FULL 20 SCHEDULE EXTRACTION")
    print("=" * 70)
    print(f"Model: {MODEL}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Setup client
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set.")
        sys.exit(1)
    
    client = genai.Client(api_key=api_key)
    
    # Load ground truth
    if not os.path.exists(GROUND_TRUTH_FILE):
        print(f"Error: Ground truth file not found: {GROUND_TRUTH_FILE}")
        sys.exit(1)
    
    ground_truth = load_ground_truth(GROUND_TRUTH_FILE)
    print(f"Loaded ground truth for {len(ground_truth)} schedules")
    
    # Find all PDFs
    pdf_folder = Path(SCHEDULES_FOLDER)
    pdf_files = sorted(pdf_folder.glob("*.pdf"))
    
    if not pdf_files:
        print(f"Error: No PDF files found in {SCHEDULES_FOLDER}")
        sys.exit(1)
    
    print(f"Found {len(pdf_files)} PDF files")
    print("-" * 70)
    
    # Process all PDFs
    all_results = []
    all_comparisons = []
    
    for i, pdf_path in enumerate(pdf_files, 1):
        filename = os.path.basename(pdf_path)
        schedule_id = extract_schedule_id(filename)
        print(f"[{i:2d}/{len(pdf_files)}] {filename}...", end=" ", flush=True)
        
        result = extract_single_pdf(client, str(pdf_path))
        
        if result:
            all_results.append(result)
            comparison = compare_single(result, ground_truth)
            all_comparisons.append(comparison)
            
            # Quick summary
            exact = 0
            total = 0
            for arm_data in comparison.get('arms', {}).values():
                if 'windows' in arm_data:
                    for w_data in arm_data['windows'].values():
                        total += 1
                        if w_data['match']:
                            exact += 1
            print(f"✓ ({exact}/{total} exact)")
        else:
            print("✗ Failed")
            all_comparisons.append({'schedule_id': schedule_id, 'error': 'Extraction failed'})
        
        # Rate limiting
        time.sleep(1)
    
    # Calculate metrics
    print("\n" + "=" * 70)
    print("CALCULATING METRICS")
    print("=" * 70)
    
    metrics = calculate_overall_metrics(all_comparisons)
    
    # Print summary
    print(f"\nOverall Exact Match Accuracy: {metrics['exact_accuracy']:.1%}")
    print(f"Clinical Accuracy (±3 days): {metrics['clinical_accuracy']:.1%}")
    print(f"Mean Absolute Error: {metrics['mae']:.2f} days")
    print(f"Total Comparisons: {metrics['total']}")
    
    print("\nPer-Window Accuracy:")
    for window in TIME_WINDOWS:
        stats = metrics['window_stats'][window]
        exact_acc = stats['exact'] / stats['total'] if stats['total'] > 0 else 0
        clin_acc = stats['within_3'] / stats['total'] if stats['total'] > 0 else 0
        print(f"  {window:12s}: {exact_acc:5.1%} exact | {clin_acc:5.1%} ±3 days")
    
    print("\nPer-Complexity Accuracy:")
    for complexity in ['simple', 'moderate', 'complex']:
        stats = metrics['complexity_stats'][complexity]
        if stats['total'] > 0:
            exact_acc = stats['exact'] / stats['total']
            clin_acc = stats['within_3'] / stats['total']
            print(f"  {complexity:10s}: {exact_acc:5.1%} exact | {clin_acc:5.1%} ±3 days (n={stats['total']})")
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Save results
    print("\n" + "=" * 70)
    print("SAVING RESULTS")
    print("=" * 70)
    
    json_file = save_json_results(all_comparisons, metrics, OUTPUT_DIR)
    latex_file = generate_latex_tables(all_comparisons, metrics, OUTPUT_DIR)
    
    print("\n" + "=" * 70)
    print("COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()

