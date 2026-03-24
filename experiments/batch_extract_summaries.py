#!/usr/bin/env python3
"""
Batch PDF Extraction Summary Agent

Processes all PDFs in 'full text Protocols/' folder, extracts Schedule of Events pages,
and generates consolidated Summary_SoE PDFs in 'summaries_generated/' folder.

Usage:
    python3 experiments/batch_extract_summaries.py [--limit N] [--output-dir DIR]
"""

import os
import sys
import json
import argparse
import tempfile
import re
import io
import csv
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Error: google-genai not installed.")
    print("Run: pip install google-genai")
    sys.exit(1)

try:
    from pypdfium2 import PdfDocument
    from pypdf import PdfWriter, PdfReader
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph
    from reportlab.lib.units import inch
except ImportError:
    print("Error: Missing PDF dependencies.")
    print("Run: pip install pypdfium2 pypdf reportlab")
    sys.exit(1)

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

# ============================================================================
# CONFIGURATION
# ============================================================================

MODEL = "gemini-2.5-flash"
INPUT_FOLDER = "full text Protocols"
OUTPUT_FOLDER = "summaries_generated"

# ============================================================================
# GEMINI EXTRACTION
# ============================================================================

EXTRACTION_PROMPT = """
You are an expert AI assistant specializing in analyzing clinical trial protocols.

Please process the provided PDF document and identify the following information:

1. Create a concise summary (max 300 words) of the clinical trial, including:
   - The overall study design (e.g., randomized, placebo-controlled, open-label, phase)
   - The main study arms or treatment groups
   - The total duration of the trial for a participant

2. Your task: Determine if this page MIGHT contain ANY information about WHEN participants need to do study activities. IMPORTANT: BE LIBERAL IN YOUR ASSESSMENT - if you're unsure, answer YES.

Consider this page relevant if it contains ANY of the following:
- ANY tables, charts, or text showing visit schedules or assessments (regardless of what they're called)
- ANY information about timing of procedures or assessments
- ANY mention of specific study timepoints, visit windows, or study duration
- ANY information about frequency of visits or procedures
- ANY footnotes or legends related to scheduling
- ANY information that would help a participant understand when they need to do something
- ANY references to follow-up visits or time-related procedures
- ANY pages that appear to be continuations of schedule tables
- ANY assessment information

DO NOT WORRY about whether the information is complete or detailed. Even if the page only contains partial scheduling information, answer YES.

Remember: In this initial screening, it is MUCH BETTER to include too many pages than to miss important ones. When in doubt, say YES.

Return your analysis in a structured JSON format with these fields:
- "trial_summary": Your concise summary
- "schedule_of_events_pages": Array of page numbers containing the main schedule
- "important_time_commitment_pages": Array of other page numbers with time commitment information, BE MORE RESTRICTIVE HERE

Be COMPREHENSIVE and do not miss any information, this is an original screening and being more liberal is better - focus on information that helps understand participant time commitment.
"""


def process_protocol_with_gemini(client: genai.Client, pdf_path: str) -> Optional[Dict[str, Any]]:
    """Process clinical trial protocol PDF with Gemini API."""
    filename = os.path.basename(pdf_path)

    try:
        # Upload the PDF file to Gemini
        uploaded_file = client.files.upload(file=pdf_path)

        # Create prompt using the uploaded file
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_uri(
                        file_uri=uploaded_file.uri,
                        mime_type="application/pdf",
                    ),
                    types.Part.from_text(text=EXTRACTION_PROMPT),
                ],
            ),
        ]

        # Create schema definition
        generate_content_config = types.GenerateContentConfig(
            temperature=0.0,
            top_p=0.95,
            top_k=40,
            response_mime_type="application/json",
            response_schema=genai.types.Schema(
                type=genai.types.Type.OBJECT,
                properties={
                    "trial_summary": genai.types.Schema(type=genai.types.Type.STRING),
                    "schedule_of_events_pages": genai.types.Schema(
                        type=genai.types.Type.ARRAY,
                        items=genai.types.Schema(type=genai.types.Type.INTEGER),
                        description="Page numbers (1-indexed) containing the Schedule of Events table"
                    ),
                    "important_time_commitment_pages": genai.types.Schema(
                        type=genai.types.Type.ARRAY,
                        items=genai.types.Schema(type=genai.types.Type.INTEGER),
                        description="Page numbers (1-indexed) containing other important time commitment information"
                    )
                },
                required=["trial_summary", "schedule_of_events_pages", "important_time_commitment_pages"]
            ),
        )

        # Generate response (non-streaming for batch)
        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=generate_content_config,
        )

        full_response = response.text

        # Process the JSON response
        try:
            result = json.loads(full_response)

            # Ensure all fields exist
            if "trial_summary" not in result or not result["trial_summary"]:
                result["trial_summary"] = "Summary not available."

            if "schedule_of_events_pages" not in result or not isinstance(result["schedule_of_events_pages"], list):
                result["schedule_of_events_pages"] = []

            if "important_time_commitment_pages" not in result or not isinstance(result["important_time_commitment_pages"], list):
                result["important_time_commitment_pages"] = []

            return result

        except json.JSONDecodeError as e:
            print(f"    JSON parse error: {e}")
            # Fallback extraction
            fallback_result = {
                "trial_summary": "Summary extraction failed.",
                "schedule_of_events_pages": [],
                "important_time_commitment_pages": []
            }

            summary_match = re.search(r'"trial_summary"\s*:\s*"([^"]+)"', full_response)
            if summary_match:
                fallback_result["trial_summary"] = summary_match.group(1)

            soe_match = re.search(r'"schedule_of_events_pages"\s*:\s*\[(.*?)\]', full_response, re.DOTALL)
            if soe_match:
                soe_pages = [int(num.strip()) for num in re.findall(r'\d+', soe_match.group(1))]
                fallback_result["schedule_of_events_pages"] = soe_pages

            time_match = re.search(r'"important_time_commitment_pages"\s*:\s*\[(.*?)\]', full_response, re.DOTALL)
            if time_match:
                time_pages = [int(num.strip()) for num in re.findall(r'\d+', time_match.group(1))]
                fallback_result["important_time_commitment_pages"] = time_pages

            return fallback_result

    except Exception as e:
        print(f"    API Error: {e}")
        return None


# ============================================================================
# PDF GENERATION
# ============================================================================

def create_summary_pdf_page(summary_text: str) -> PdfReader:
    """Creates a single PDF page with the summary text using ReportLab."""
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    styles = getSampleStyleSheet()
    styleN = styles['Normal']
    styleH = styles['Heading1']

    title = Paragraph("Clinical Trial Protocol Summary", styleH)
    title.wrapOn(can, letter[0] - 2 * inch, letter[1])
    title.drawOn(can, inch, letter[1] - 1 * inch)

    text_paragraphs = summary_text.split('\n')
    y_position = letter[1] - 1.5 * inch

    for para_text in text_paragraphs:
        if para_text.strip():
            p = Paragraph(para_text.strip(), styleN)
            p_width_available = letter[0] - 2 * inch
            p_height_needed = p.wrapOn(can, p_width_available, y_position)[1]

            if y_position - p_height_needed < inch:
                can.showPage()
                y_position = letter[1] - inch

            p.drawOn(can, inch, y_position - p_height_needed)
            y_position -= (p_height_needed + 0.1 * inch)

    can.save()
    packet.seek(0)
    return PdfReader(packet)


def generate_consolidated_pdf(original_pdf_path: str, analysis_results: Dict, output_pdf_path: str) -> bool:
    """
    Generates a new PDF with the summary and specified pages from the original protocol.
    Includes surrounding pages (N-1, N, N+1) for each identified page N.
    """
    if not analysis_results:
        return False

    summary_text = analysis_results.get("trial_summary", "Summary not available.")

    soe_pages_1_indexed = [p for p in analysis_results.get("schedule_of_events_pages", []) if p > 0]
    time_pages_1_indexed = [p for p in analysis_results.get("important_time_commitment_pages", []) if p > 0]

    all_relevant_pages_1_indexed = sorted(list(set(soe_pages_1_indexed + time_pages_1_indexed)))

    # Get total pages
    try:
        original_pdf_doc = PdfDocument(original_pdf_path)
        total_pages = len(original_pdf_doc)
        original_pdf_doc.close()
    except Exception as e:
        print(f"    Error reading original PDF: {e}")
        return False

    # Expand to include surrounding pages
    expanded_pages_1_indexed = []
    for page in all_relevant_pages_1_indexed:
        if page > 1:
            expanded_pages_1_indexed.append(page - 1)
        expanded_pages_1_indexed.append(page)
        if page < total_pages:
            expanded_pages_1_indexed.append(page + 1)

    expanded_pages_1_indexed = sorted(list(set(expanded_pages_1_indexed)))
    expanded_pages_0_indexed = [p - 1 for p in expanded_pages_1_indexed]

    output_pdf = PdfWriter()

    # Add summary page
    try:
        summary_pdf_reader = create_summary_pdf_page(summary_text)
        for page_obj in summary_pdf_reader.pages:
            output_pdf.add_page(page_obj)
    except Exception as e:
        print(f"    Error creating summary page: {e}")

    # Add relevant pages from original PDF
    if expanded_pages_0_indexed:
        original_pdf_doc = None
        extracted_pdf_doc = None
        try:
            original_pdf_doc = PdfDocument(original_pdf_path)
            extracted_pdf_doc = PdfDocument.new()

            extracted_pdf_doc.import_pages(original_pdf_doc, pages=expanded_pages_0_indexed)

            temp_buffer = io.BytesIO()
            extracted_pdf_doc.save(temp_buffer)
            temp_buffer.seek(0)

            extracted_pages_reader = PdfReader(temp_buffer)
            for page_obj in extracted_pages_reader.pages:
                output_pdf.add_page(page_obj)

        except Exception as e:
            print(f"    Error extracting pages: {e}")
            return False
        finally:
            if extracted_pdf_doc:
                extracted_pdf_doc.close()
            if original_pdf_doc:
                original_pdf_doc.close()

    # Save the final PDF
    if len(output_pdf.pages) > 0:
        try:
            with open(output_pdf_path, "wb") as f_out:
                output_pdf.write(f_out)
            return True
        except Exception as e:
            print(f"    Error saving PDF: {e}")
            return False
    return False


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Batch extract Summary_SoE PDFs from protocols")
    parser.add_argument("--limit", type=int, help="Limit number of PDFs to process")
    parser.add_argument("--input-dir", type=str, default=INPUT_FOLDER, help="Input folder with protocol PDFs")
    parser.add_argument("--output-dir", type=str, default=OUTPUT_FOLDER, help="Output folder for Summary_SoE PDFs")
    args = parser.parse_args()

    print("=" * 70)
    print("BATCH PDF EXTRACTION: SUMMARY + SCHEDULE OF EVENTS")
    print("=" * 70)

    # Setup client
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set.")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    # Find PDFs
    input_folder = Path(args.input_dir)
    if not input_folder.exists():
        print(f"Error: Input folder not found: {args.input_dir}")
        sys.exit(1)

    pdf_files = sorted(input_folder.glob("*.pdf"))
    if not pdf_files:
        print(f"Error: No PDF files found in {args.input_dir}")
        sys.exit(1)

    print(f"Found {len(pdf_files)} PDF files in '{args.input_dir}'")

    # Setup output directory
    output_folder = Path(args.output_dir)
    output_folder.mkdir(parents=True, exist_ok=True)

    # Setup CSV log file
    csv_log_path = output_folder / "extraction_log.csv"
    csv_exists = csv_log_path.exists()

    # Check for already processed files
    existing_outputs = set(f.stem.replace("_Summary_SoE", "") for f in output_folder.glob("*_Summary_SoE.pdf"))
    files_to_process = [f for f in pdf_files if f.stem not in existing_outputs]

    if existing_outputs:
        print(f"Found {len(existing_outputs)} already processed. Resuming with {len(files_to_process)} remaining.")

    # Apply limit
    if args.limit:
        files_to_process = files_to_process[:args.limit]
        print(f"Limiting to first {args.limit} files.")

    print(f"Extraction log: {csv_log_path}")
    print("-" * 70)

    success_count = 0
    fail_count = 0

    # Open CSV for appending
    csv_file = open(csv_log_path, 'a', newline='', encoding='utf-8')
    csv_writer = csv.writer(csv_file)

    # Write header if new file
    if not csv_exists:
        csv_writer.writerow([
            'filename', 
            'trial_summary', 
            'schedule_of_events_pages', 
            'num_soe_pages',
            'important_time_commitment_pages',
            'num_time_pages',
            'total_extracted_pages',
            'status',
            'error'
        ])

    try:
        for i, pdf_path in enumerate(files_to_process, 1):
            filename = pdf_path.name
            print(f"[{i:3d}/{len(files_to_process)}] {filename}...", end=" ", flush=True)

            # Process with Gemini
            analysis_results = process_protocol_with_gemini(client, str(pdf_path))

            if analysis_results:
                # Generate output filename
                output_filename = pdf_path.stem + "_Summary_SoE.pdf"
                output_path = output_folder / output_filename

                # Generate consolidated PDF
                if generate_consolidated_pdf(str(pdf_path), analysis_results, str(output_path)):
                    soe_pages = analysis_results.get("schedule_of_events_pages", [])
                    time_pages = analysis_results.get("important_time_commitment_pages", [])
                    soe_count = len(soe_pages)
                    time_count = len(time_pages)
                    total_extracted = len(set(soe_pages + time_pages))

                    print(f"✓ ({soe_count} SoE pages)")
                    success_count += 1

                    # Log to CSV
                    csv_writer.writerow([
                        filename,
                        analysis_results.get("trial_summary", "")[:500],  # Truncate long summaries
                        str(soe_pages),
                        soe_count,
                        str(time_pages),
                        time_count,
                        total_extracted,
                        'success',
                        ''
                    ])
                    csv_file.flush()  # Flush after each write
                else:
                    print("✗ PDF generation failed")
                    fail_count += 1
                    csv_writer.writerow([filename, '', '[]', 0, '[]', 0, 0, 'failed', 'PDF generation failed'])
                    csv_file.flush()
            else:
                print("✗ Analysis failed")
                fail_count += 1
                csv_writer.writerow([filename, '', '[]', 0, '[]', 0, 0, 'failed', 'API analysis failed'])
                csv_file.flush()

            # Rate limiting
            time.sleep(1)

    finally:
        csv_file.close()

    print("\n" + "=" * 70)
    print(f"COMPLETED. Successful: {success_count}/{len(files_to_process)}, Failed: {fail_count}")
    print(f"Output folder: {output_folder}")
    print(f"Extraction log: {csv_log_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
