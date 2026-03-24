#!/usr/bin/env python3
"""
Fetch Metadata (Year) for Protocols via PubMed API
"""

import os
import csv
import re
import time
import requests
import argparse
from pathlib import Path
from typing import List, Dict

# Using Entrez E-utilities
# https://www.ncbi.nlm.nih.gov/books/NBK25501/
BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
DB = "pubmed"
RETMODE = "json"

def extract_pmid(filename: str) -> str:
    """Extract PMID from filename pattern 'PMID 12345678 ...'"""
    match = re.search(r'PMID\s*(\d+)', filename, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""

def fetch_metadata_batch(pmids: List[str]) -> Dict[str, str]:
    """Fetch metadata for a batch of PMIDs."""
    if not pmids:
        return {}
        
    ids_str = ",".join(pmids)
    params = {
        "db": DB,
        "id": ids_str,
        "retmode": RETMODE,
        # "api_key": "YOUR_API_KEY" # Optional but recommended for higher limits
    }
    
    try:
        response = requests.get(BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        results = {}
        if 'result' in data:
            for uid in data['result']:
                if uid == 'uids': continue
                item = data['result'][uid]
                
                # Try to get publication date
                pub_date = item.get('pubdate', '')
                epub_date = item.get('epubdate', '')
                
                # Extract year from date string (e.g., "2023 Jun 15" -> "2023")
                year = ""
                # Prefer epub date often for trials, but pubdate is standard
                date_str = pub_date if pub_date else epub_date
                
                year_match = re.search(r'(\d{4})', date_str)
                if year_match:
                    year = year_match.group(1)
                
                results[uid] = year
                
        return results
        
    except Exception as e:
        print(f"Error fetching batch: {e}")
        return {}

def main():
    parser = argparse.ArgumentParser(description="Fetch PubMed metadata (Year)")
    parser.add_argument("--input", default="results/vanilla_summaries_dataset.csv", help="Input CSV with filenames")
    parser.add_argument("--output", default="results/protocol_metadata.csv", help="Output CSV with years")
    args = parser.parse_args()
    
    # 1. Read Input
    print(f"Reading {args.input}...")
    filenames = set()
    try:
        with open(args.input, 'r') as f:
            reader = csv.reader(f)
            next(reader) # header
            for row in reader:
                if row:
                    filenames.add(row[0])
    except Exception as e:
        print(f"Error reading input: {e}")
        return

    print(f"Found {len(filenames)} unique filenames.")
    
    # 2. Extract PMIDs
    file_pmid_map = []
    unique_pmids = set()
    
    for fname in filenames:
        pmid = extract_pmid(fname)
        if pmid:
            file_pmid_map.append((fname, pmid))
            unique_pmids.add(pmid)
        else:
            print(f"Warning: No PMID found in {fname}")
            
    sorted_pmids = sorted(list(unique_pmids))
    print(f"Extracted {len(sorted_pmids)} unique PMIDs.")
    
    # 3. Batch Fetch
    pmid_year_map = {}
    BATCH_SIZE = 200 # Max is usually roughly this for GET requests
    
    for i in range(0, len(sorted_pmids), BATCH_SIZE):
        batch = sorted_pmids[i:i+BATCH_SIZE]
        print(f"Fetching batch {i}-{i+len(batch)}...")
        
        batch_results = fetch_metadata_batch(batch)
        pmid_year_map.update(batch_results)
        
        time.sleep(1) # Be nice to NCBI servers (3 req/sec limit without key)
        
    # 4. Save Results
    print(f"Saving to {args.output}...")
    with open(args.output, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['filename', 'pmid', 'publication_year'])
        
        found_count = 0
        for fname, pmid in file_pmid_map:
            year = pmid_year_map.get(pmid, "")
            if year: found_count += 1
            writer.writerow([fname, pmid, year])
            
    print(f"Done. Found years for {found_count}/{len(file_pmid_map)} protocols.")

if __name__ == "__main__":
    main()
