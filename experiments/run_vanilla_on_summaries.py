#!/usr/bin/env python3
"""
Run Vanilla Extraction on Protocol Summaries

Runs the vanilla (single-pass) extraction on PDF summaries in the 'summaries' folder.
Outputs results to 'results/vanilla_summaries_YYYY-MM-DD.csv' and .json.

Usage:
    python3 experiments/run_vanilla_on_summaries.py [--limit N]
"""

import os
import sys
import csv
import json
import time
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add parent directory to path to import core modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Error: google-genai not installed.")
    print("Run: pip install google-genai python-dotenv")
    sys.exit(1)

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

# Import from core
from core.test_extraction import (
    EXTRACTION_PROMPT,
    parse_json_response,
    extract_schedule_id,
)

# ============================================================================
# CONFIGURATION
# ============================================================================

MODEL = "gemini-3-flash-preview"
INPUT_FOLDER = "summaries_generated"
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
                    print(f"    API Error: {e}")
                    # Allow continuing to next file on other errors
                    return None
        
        if not response_text:
            return None
        
        # Parse
        parsed_arms = parse_json_response(response_text)
        
        if parsed_arms:
            return {
                'filename': filename,
                'schedule_id': extract_schedule_id(filename),  # Might just be filename if no ID found
                'arms': parsed_arms,
                'raw_response_snippet': response_text[:200]
            }
        return {'filename': filename, 'error': 'Failed to parse JSON', 'raw_response': response_text}
        
    except Exception as e:
        print(f"    Error processing {filename}: {e}")
        return {'filename': filename, 'error': str(e)}


# ============================================================================
# OUTPUT FUNCTIONS
# ============================================================================

def save_row_to_csv(item: Dict, csv_path: str):
    """Append a single result row to CSV."""
    file_exists = os.path.isfile(csv_path)
    
    with open(csv_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Determine if we need header
        if not file_exists:
             headers = [
                'filename', 'arm_name', 'intervention_type',
                'screening', '1_month', '3_months', '6_months', '9_months', '12_months',
                'cycle_length', 'visit_pattern', 'error'
            ]
             writer.writerow(headers)
        
        filename = item.get('filename', 'unknown')
        error = item.get('error', '')
        
        if error:
            writer.writerow([filename, '', '', '', '', '', '', '', '', '', '', error])
            return
        
        for arm in item.get('arms', []):
            days = arm.get('healthcare_contact_days', {})
            notes = arm.get('extraction_notes', {})
            
            row = [
                filename,
                arm.get('arm_name', ''),
                arm.get('intervention_type', ''),
                days.get('screening', ''),
                days.get('1_month', ''),
                days.get('3_months', ''),
                days.get('6_months', ''),
                days.get('9_months', ''),
                days.get('12_months', ''),
                notes.get('cycle_length_days', ''),
                notes.get('visit_pattern', ''),
                ''
            ]
            writer.writerow(row)


def get_processed_files(csv_path: str) -> set:
    """Get set of filenames already in the CSV."""
    if not os.path.isfile(csv_path):
        return set()
        
    try:
        processed = set()
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)  # Skip header
            for row in reader:
                if row:
                    processed.add(row[0])  # filename is first column
        return processed
    except Exception as e:
        print(f"Warning: Could not read existing CSV: {e}")
        return set()


# ============================================================================
# MAIN
# ============================================================================

def get_failed_files(csv_path: str) -> set:
    """Get set of filenames that have errors in the CSV."""
    if not os.path.isfile(csv_path):
        return set()
        
    failed = set()
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header: return set()
            
            # error is the last column (index 11)
            for row in reader:
                if row:
                    filename = row[0]
                    # Check if error column is populated
                    if len(row) >= 12 and row[11].strip(): 
                         failed.add(filename)
    except Exception as e:
        print(f"Warning: Could not read CSV for failures: {e}")
    return failed

def main():
    parser = argparse.ArgumentParser(description="Run vanilla extraction on summaries")
    parser.add_argument("--limit", type=int, help="Limit number of PDFs to process")
    parser.add_argument("--output", type=str, default="vanilla_summaries_dataset.csv", help="Output CSV filename")
    parser.add_argument("--run-id", type=int, default=1, help="Run ID to append to output filename if not default")
    parser.add_argument("--retry-failures", action="store_true", help="Only process files that failed in the existing CSV")
    args = parser.parse_args()

    # Modify output filename if run-id is provided and output is default
    if args.run_id > 1 and args.output == "vanilla_summaries_dataset.csv":
        args.output = f"vanilla_summaries_dataset_run{args.run_id}.csv"

    print("=" * 70)
    print("VANILLA EXTRACTION: SUMMARIES (INCREMENTAL)")
    print("=" * 70)
    
    # Setup client
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set.")
        sys.exit(1)
    
    client = genai.Client(api_key=api_key)
    
    # Find PDFs
    pdf_folder = Path(INPUT_FOLDER)
    if not pdf_folder.exists():
        print(f"Error: Input folder not found: {INPUT_FOLDER}")
        sys.exit(1)
        
    pdf_files = sorted(pdf_folder.glob("*.pdf"))
    if not pdf_files:
        print(f"Error: No PDF files found in {INPUT_FOLDER}")
        sys.exit(1)
        
    print(f"Found {len(pdf_files)} PDF files in '{INPUT_FOLDER}'")
    
    # Start Output Setup
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    csv_path = os.path.join(OUTPUT_DIR, args.output)
    json_path = os.path.join(OUTPUT_DIR, args.output.replace('.csv', '.json'))
    
    # Check for existing progress
    processed_files = get_processed_files(csv_path)
    if processed_files:
        print(f"Found existing CSV with {len(processed_files)} processed files. Resuming...")
    
    # Filter out processed files
    if args.retry_failures:
        print("Mode: RETRY FAILURES")
        processed_files = set() # We want to IGNORE processed files check if we are retrying
        failed_files = get_failed_files(csv_path)
        print(f"Found {len(failed_files)} failed files in CSV.")
        
        # Only process files that are in the failed set
        files_to_process = [p for p in pdf_files if os.path.basename(str(p)) in failed_files]
        if not files_to_process:
            print("No failed files found to retry!")
            sys.exit(0)
    else:
        # Normal mode: skip already processed
        files_to_process = [p for p in pdf_files if os.path.basename(str(p)) not in processed_files]
    
    if not files_to_process:
        print("All files already processed!")
        sys.exit(0)

    # Apply limit
    if args.limit:
        files_to_process = files_to_process[:args.limit]
        print(f"Limiting to first {args.limit} remaining files.")
    
    print("-" * 70)
    print(f"Processing {len(files_to_process)} files...")
    
    # Load existing JSON results if available to append properly (optional, simple append list logic)
    # For now, we update JSON at the very end or just focus on CSV for incremental safety
    results = [] # In a real incremental run, we rely on CSV for safety. 
                 # We'll save the full JSON at the end for this batch.

    success_count = 0
    
    for i, pdf_path in enumerate(files_to_process, 1):
        filename = os.path.basename(pdf_path)
        print(f"[{i:3d}/{len(files_to_process)}] {filename}...", end=" ", flush=True)
        
        result = extract_single_pdf(client, str(pdf_path))
        
        if result:
            results.append(result)
            save_row_to_csv(result, csv_path) # SAVE INCREMENTALLY
            
            if 'error' not in result:
                success_count += 1
                arm_count = len(result.get('arms', []))
                print(f"✓ ({arm_count} arms)")
            else:
                print(f"✗ {result['error']}")
        else:
            print("✗ Failed (Unknown error)")
            # Save failure record
            fail_result = {'filename': filename, 'error': 'Unknown failure'}
            results.append(fail_result)
            save_row_to_csv(fail_result, csv_path)
            
        # Rate limiting
        time.sleep(1)
        
    # Save JSON batch (appending to existing if we were smarter, but overwriting is risky if we just took partial list)
    # Better: Read existing JSON, extend, save.
    
    all_json_results = []
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r') as f:
                all_json_results = json.load(f)
        except:
            pass
    
    all_json_results.extend(results)
    
    with open(json_path, 'w') as f:
        json.dump(all_json_results, f, indent=2)
    print(f"\nUpdated JSON results at: {json_path}")
        
    print("\n" + "=" * 70)
    print(f"COMPLETED BATCH. Successful: {success_count}/{len(files_to_process)}")
    print(f"Full results in: {csv_path}")
    print("=" * 70)

if __name__ == "__main__":
    main()
