"""
Category Breakdown Experiment

Extracts time-toxic days broken down by category:
- core_treatment: Drug administration, infusions
- imaging_diagnostics: CT, MRI, PET, ECG, ECHO
- labs: Blood draws, urinalysis, biomarkers
- clinic_visits: Physical exam, vital signs, safety monitoring
"""

from .html_parser import parse_schedule_html, generate_category_ground_truth
from .pipeline import run_category_pipeline

