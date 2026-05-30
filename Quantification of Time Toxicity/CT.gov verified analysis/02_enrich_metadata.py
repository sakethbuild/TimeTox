#!/usr/bin/env python3
"""
Step 2: Enrich consensus dataset with metadata from Included Trials.csv.

Joins sponsorship, disease site, treatment modality, etc. onto trial-level data.
Classifies treatment modality using drug dictionary + BIOLOGICAL prefix.
"""

import os
import sys
import re
import pandas as pd
import numpy as np
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    INCLUDED_TRIALS, DATA_DIR, DRUG_CLASSES, DISEASE_SITE_MERGE, MIN_GROUP_SIZE
)


def extract_pmid(filename):
    """Extract PMID from filename pattern."""
    match = re.search(r"(?:PMID|PIMD)\s*(\d+)", filename, re.IGNORECASE)
    if match:
        return match.group(1)
    # Try bare number at start
    match = re.search(r"^(\d{7,8})", filename)
    if match:
        return match.group(1)
    return None


def classify_treatment_modality(intervention_str):
    """
    Classify a trial's treatment modality based on its intervention drugs.
    Returns the class of the primary experimental agent.
    """
    if not intervention_str or pd.isna(intervention_str):
        return "Other"

    intervention_str = str(intervention_str).lower()
    entries = intervention_str.split("|")

    found_classes = []
    for entry in entries:
        entry = entry.strip()
        # Extract drug name after the type prefix
        drug_name = re.sub(r"^(drug|biological|radiation|procedure|other|dietary supplement|diagnostic test|device|genetic|behavioral|combination product):\s*", "", entry)
        drug_name = drug_name.strip()

        # Check against dictionary
        for drug_key, drug_class in DRUG_CLASSES.items():
            if drug_key in drug_name:
                if drug_class != "Supportive":  # Skip supportive drugs for classification
                    found_classes.append(drug_class)
                break
        else:
            # Check BIOLOGICAL prefix as fallback
            if entry.startswith("biological:"):
                found_classes.append("Immunotherapy/Targeted")
            elif entry.startswith("radiation:"):
                found_classes.append("Radiation")
            elif entry.startswith("procedure:"):
                found_classes.append("Procedure")

    if not found_classes:
        return "Other"

    # Priority: Immunotherapy > Targeted > Endocrine > Chemotherapy > Radiation > Other
    priority = ["Immunotherapy", "Immunotherapy/Targeted", "Targeted Therapy", "Endocrine", "Chemotherapy", "Radiation", "Procedure"]
    class_counts = Counter(found_classes)

    for p in priority:
        if p in class_counts:
            return p

    return found_classes[0]


def parse_start_year(row):
    """Extract trial start year from Start Date, falling back to Enrollment Year."""
    start_date = row.get("Start Date")
    if pd.notna(start_date) and str(start_date).strip():
        parsed = pd.to_datetime(str(start_date).strip(), errors="coerce")
        if pd.notna(parsed):
            return int(parsed.year)
    # Fallback to Enrollment Year
    enrollment_year = row.get("Enrollment Year")
    if pd.notna(enrollment_year):
        try:
            return int(float(enrollment_year))
        except (ValueError, TypeError):
            pass
    return np.nan


def load_included_trials():
    """Load and de-duplicate Included Trials.csv by PMID."""
    df = pd.read_csv(INCLUDED_TRIALS, encoding="latin-1")
    # Clean PMID column (has trailing space in header)
    pmid_col = [c for c in df.columns if "PMID" in c][0]
    df["pmid"] = df[pmid_col].astype(str).str.strip()

    # De-duplicate: keep first row per PMID
    before = len(df)
    df = df.drop_duplicates(subset=["pmid"], keep="first")
    print(f"  Loaded {before} rows, de-duplicated to {len(df)} unique PMIDs")

    return df


def main():
    print("=" * 60)
    print("STEP 2: Metadata Enrichment")
    print("=" * 60)

    # Load consensus trial-level data
    print("\n--- Loading consensus trials ---")
    trials = pd.read_csv(os.path.join(DATA_DIR, "consensus_trials.csv"))
    print(f"  {len(trials)} trials")

    # Extract PMID from filename
    trials["pmid"] = trials["filename"].apply(extract_pmid)
    matched = trials["pmid"].notna().sum()
    print(f"  PMIDs extracted: {matched}/{len(trials)}")

    # Load Included Trials
    print("\n--- Loading Included Trials metadata ---")
    meta = load_included_trials()

    # Join
    print("\n--- Joining metadata ---")
    enriched = trials.merge(
        meta[["pmid", "Funder", "Industry", "Disease Site", "Disease Stage",
              "Treatment Type", "Condition", "intervention", "Publication Year",
              "NCT Number", "Design", "Enrollment",
              "Start Date", "Enrollment Year"]],
        on="pmid",
        how="left",
        suffixes=("", "_meta")
    )

    # Check coverage
    n_matched = enriched["Funder"].notna().sum()
    print(f"  Matched to Included Trials: {n_matched}/{len(enriched)} ({100*n_matched/len(enriched):.1f}%)")

    # --- Sponsorship ---
    print("\n--- Processing Sponsorship ---")
    enriched["sponsor_binary"] = enriched["Industry"].map({"Yes": "Industry", "No": "Non-Industry"})
    print(f"  Industry: {(enriched['sponsor_binary']=='Industry').sum()}")
    print(f"  Non-Industry: {(enriched['sponsor_binary']=='Non-Industry').sum()}")
    print(f"  Funder breakdown:")
    for funder, count in enriched["Funder"].value_counts().items():
        print(f"    {funder}: {count}")

    # --- Disease Site ---
    print("\n--- Processing Disease Site ---")
    enriched["disease_site"] = enriched["Disease Site"].str.strip()
    # Apply merges for small groups
    for old, new in DISEASE_SITE_MERGE.items():
        enriched.loc[enriched["disease_site"] == old, "disease_site"] = new
    # Check group sizes and merge small groups
    site_counts = enriched["disease_site"].value_counts()
    small_sites = site_counts[site_counts < MIN_GROUP_SIZE].index.tolist()
    if small_sites:
        print(f"  Merging small groups into 'Other': {small_sites}")
        enriched.loc[enriched["disease_site"].isin(small_sites), "disease_site"] = "Other"

    print(f"  Disease Site distribution:")
    for site, count in enriched["disease_site"].value_counts().sort_values(ascending=False).items():
        print(f"    {site}: {count}")

    # --- Treatment Modality ---
    print("\n--- Classifying Treatment Modality ---")
    enriched["treatment_modality"] = enriched["intervention"].apply(classify_treatment_modality)

    # Resolve Immunotherapy/Targeted to Targeted Therapy (BIOLOGICAL without specific IO drug)
    enriched.loc[enriched["treatment_modality"] == "Immunotherapy/Targeted", "treatment_modality"] = "Targeted Therapy"

    print(f"  Treatment Modality distribution:")
    for modality, count in enriched["treatment_modality"].value_counts().sort_values(ascending=False).items():
        print(f"    {modality}: {count}")

    # --- Trial Start Year ---
    print("\n--- Processing Trial Start Year ---")
    enriched["start_year"] = enriched.apply(parse_start_year, axis=1)
    year_range = enriched["start_year"].dropna()
    print(f"  Year range: {int(year_range.min())}-{int(year_range.max())}")
    print(f"  Median year: {int(year_range.median())}")
    print(f"  Missing: {enriched['start_year'].isna().sum()}")

    # --- Save ---
    print("\n--- Saving enriched dataset ---")
    enriched.to_csv(os.path.join(DATA_DIR, "enriched_trials.csv"), index=False)
    print(f"  Saved: data/enriched_trials.csv ({len(enriched)} rows)")

    # Also enrich arm-level data
    print("\n--- Enriching arm-level data ---")
    arms = pd.read_csv(os.path.join(DATA_DIR, "consensus_arms.csv"))
    arms["pmid"] = arms["filename"].apply(extract_pmid)
    arms_enriched = arms.merge(
        enriched[["filename", "sponsor_binary", "Funder", "disease_site",
                   "Disease Stage", "treatment_modality", "start_year"]],
        on="filename",
        how="left"
    )
    arms_enriched.to_csv(os.path.join(DATA_DIR, "enriched_arms.csv"), index=False)
    print(f"  Saved: data/enriched_arms.csv ({len(arms_enriched)} rows)")

    print("\n" + "=" * 60)
    print("STEP 2 COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
