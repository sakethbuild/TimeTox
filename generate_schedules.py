#!/usr/bin/env python3
"""
Synthetic Schedule of Assessments Generator

Generates 20 synthetic SoA HTML files with varied styles and a ground truth CSV.
HTML files can be converted to PDF using browser print or additional tools.

For PDF conversion, install one of:
1. wkhtmltopdf: brew install wkhtmltopdf
2. WeasyPrint: pip install weasyprint (requires: brew install pango cairo gdk-pixbuf libffi)
3. Or use Chrome/Safari: open HTML file -> Print -> Save as PDF
"""

import os
import csv
import random
import subprocess
from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime
import shutil

# Check for PDF conversion tools
WKHTMLTOPDF_PATH = shutil.which('wkhtmltopdf')
WEASYPRINT_AVAILABLE = False

try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except ImportError:
    pass
except OSError:
    pass


@dataclass
class TrialConfig:
    """Configuration for a clinical trial schedule."""
    trial_id: str
    disease: str
    category: str  # breast, thoracic, gi, gu, head_neck, melanoma, gyn, sarcoma
    treatment_name: str
    control_name: str
    cycle_days: int
    treatment_months: int
    arm_a_visit_days: List[int]
    arm_b_visit_days: List[int]
    imaging_months: List[int]
    complexity: str
    style_variant: int
    has_radiation: bool = False
    has_surgery: bool = False


@dataclass
class StyleConfig:
    """Visual style configuration."""
    font_family: str
    header_bg: str
    header_text: str
    category_bg: str
    border_color: str
    accent_color: str
    font_size_base: str
    table_style: str


# Style presets mimicking different protocol document styles
STYLE_PRESETS = {
    1: StyleConfig(
        font_family="'Times New Roman', Times, serif",
        header_bg="#c0c0c0",
        header_text="#000000",
        category_bg="#e0e0e0",
        border_color="#000000",
        accent_color="#333333",
        font_size_base="9pt",
        table_style="classic"
    ),
    2: StyleConfig(
        font_family="Arial, Helvetica, sans-serif",
        header_bg="#4472C4",
        header_text="#ffffff",
        category_bg="#D6DCE5",
        border_color="#2F5496",
        accent_color="#1F3864",
        font_size_base="8pt",
        table_style="modern"
    ),
    3: StyleConfig(
        font_family="'Calibri', 'Segoe UI', sans-serif",
        header_bg="#548235",
        header_text="#ffffff",
        category_bg="#E2EFDA",
        border_color="#375623",
        accent_color="#2E4A1C",
        font_size_base="9pt",
        table_style="clinical"
    ),
    4: StyleConfig(
        font_family="'Georgia', serif",
        header_bg="#595959",
        header_text="#ffffff",
        category_bg="#F2F2F2",
        border_color="#404040",
        accent_color="#262626",
        font_size_base="8.5pt",
        table_style="minimal"
    ),
    5: StyleConfig(
        font_family="'Verdana', Geneva, sans-serif",
        header_bg="#843C0C",
        header_text="#ffffff",
        category_bg="#FCE4D6",
        border_color="#843C0C",
        accent_color="#5B2A09",
        font_size_base="7.5pt",
        table_style="compact"
    ),
}

# Disease/treatment combinations across multiple tumor types
TRIAL_TEMPLATES = [
    # BREAST
    {
        "disease": "HR+/HER2- Breast Cancer",
        "category": "breast",
        "treatments": [
            ("Ribociclib + Letrozole", "Letrozole"),
            ("Abemaciclib + Fulvestrant", "Fulvestrant"),
        ]
    },
    {
        "disease": "Triple-Negative Breast Cancer",
        "category": "breast",
        "treatments": [
            ("Pembrolizumab + Chemotherapy", "Chemotherapy"),
        ]
    },
    # THORACIC / LUNG
    {
        "disease": "Non-Small Cell Lung Cancer (NSCLC)",
        "category": "thoracic",
        "treatments": [
            ("Pembrolizumab + Carboplatin + Pemetrexed", "Carboplatin + Pemetrexed"),
            ("Osimertinib", "Platinum-Based Chemotherapy"),
            ("Durvalumab + Chemoradiation", "Chemoradiation Alone"),
        ]
    },
    {
        "disease": "Small Cell Lung Cancer (SCLC)",
        "category": "thoracic",
        "treatments": [
            ("Atezolizumab + Carboplatin + Etoposide", "Carboplatin + Etoposide"),
        ]
    },
    {
        "disease": "Malignant Pleural Mesothelioma",
        "category": "thoracic",
        "treatments": [
            ("Nivolumab + Ipilimumab", "Pemetrexed + Cisplatin"),
        ]
    },
    # GI - COLORECTAL
    {
        "disease": "Metastatic Colorectal Cancer (mCRC)",
        "category": "gi",
        "treatments": [
            ("FOLFOX + Bevacizumab", "FOLFOX"),
            ("FOLFIRI + Cetuximab", "FOLFIRI"),
            ("Pembrolizumab", "Investigator's Choice Chemotherapy"),
        ]
    },
    {
        "disease": "Locally Advanced Rectal Cancer",
        "category": "gi",
        "treatments": [
            ("Total Neoadjuvant Therapy (TNT) + Surgery", "Chemoradiation + Surgery"),
            ("Short-Course RT + Chemotherapy + Surgery", "Long-Course Chemoradiation + Surgery"),
        ]
    },
    # GI - GASTRIC/ESOPHAGEAL
    {
        "disease": "Gastric/GEJ Adenocarcinoma",
        "category": "gi",
        "treatments": [
            ("Nivolumab + FOLFOX", "FOLFOX"),
            ("Trastuzumab + Pembrolizumab + Chemotherapy", "Trastuzumab + Chemotherapy"),
        ]
    },
    {
        "disease": "Esophageal Squamous Cell Carcinoma",
        "category": "gi",
        "treatments": [
            ("Pembrolizumab + Chemotherapy", "Chemotherapy"),
            ("Nivolumab + Ipilimumab", "Chemotherapy"),
        ]
    },
    # GI - PANCREATIC/HEPATOBILIARY
    {
        "disease": "Pancreatic Ductal Adenocarcinoma",
        "category": "gi",
        "treatments": [
            ("FOLFIRINOX", "Gemcitabine + Nab-Paclitaxel"),
            ("Gemcitabine + Nab-Paclitaxel + Pamrevlumab", "Gemcitabine + Nab-Paclitaxel"),
        ]
    },
    {
        "disease": "Hepatocellular Carcinoma (HCC)",
        "category": "gi",
        "treatments": [
            ("Atezolizumab + Bevacizumab", "Sorafenib"),
            ("Durvalumab + Tremelimumab", "Sorafenib"),
        ]
    },
    {
        "disease": "Cholangiocarcinoma",
        "category": "gi",
        "treatments": [
            ("Gemcitabine + Cisplatin + Durvalumab", "Gemcitabine + Cisplatin"),
        ]
    },
    # GU - PROSTATE
    {
        "disease": "Metastatic Castration-Resistant Prostate Cancer (mCRPC)",
        "category": "gu",
        "treatments": [
            ("Olaparib + Abiraterone", "Abiraterone"),
            ("Enzalutamide + Talazoparib", "Enzalutamide"),
            ("177Lu-PSMA-617 + Standard of Care", "Standard of Care"),
        ]
    },
    {
        "disease": "Localized Prostate Cancer",
        "category": "gu",
        "treatments": [
            ("Radical Prostatectomy + Adjuvant RT", "Radical Prostatectomy + Observation"),
            ("SBRT (5 fractions)", "Conventional RT (39 fractions)"),
        ]
    },
    # GU - BLADDER/RENAL
    {
        "disease": "Muscle-Invasive Bladder Cancer",
        "category": "gu",
        "treatments": [
            ("Neoadjuvant Pembrolizumab + Chemotherapy + Cystectomy", "Neoadjuvant Chemotherapy + Cystectomy"),
            ("Trimodality Therapy (TURBT + Chemoradiation)", "Radical Cystectomy"),
        ]
    },
    {
        "disease": "Advanced Renal Cell Carcinoma",
        "category": "gu",
        "treatments": [
            ("Pembrolizumab + Lenvatinib", "Sunitinib"),
            ("Nivolumab + Cabozantinib", "Sunitinib"),
        ]
    },
    # HEAD AND NECK
    {
        "disease": "Head and Neck Squamous Cell Carcinoma (HNSCC)",
        "category": "head_neck",
        "treatments": [
            ("Pembrolizumab + Chemotherapy", "Cetuximab + Chemotherapy"),
            ("Definitive Chemoradiation + Pembrolizumab", "Definitive Chemoradiation"),
        ]
    },
    # MELANOMA
    {
        "disease": "Unresectable/Metastatic Melanoma",
        "category": "melanoma",
        "treatments": [
            ("Nivolumab + Relatlimab", "Nivolumab"),
            ("Dabrafenib + Trametinib", "Pembrolizumab"),
        ]
    },
    {
        "disease": "Resected Stage III Melanoma",
        "category": "melanoma",
        "treatments": [
            ("Adjuvant Pembrolizumab", "Observation"),
            ("Adjuvant Nivolumab", "Adjuvant Ipilimumab"),
        ]
    },
    # GYNECOLOGIC
    {
        "disease": "Advanced Ovarian Cancer",
        "category": "gyn",
        "treatments": [
            ("Carboplatin + Paclitaxel + Bevacizumab + Olaparib", "Carboplatin + Paclitaxel + Bevacizumab"),
            ("Niraparib Maintenance", "Observation"),
        ]
    },
    {
        "disease": "Cervical Cancer",
        "category": "gyn",
        "treatments": [
            ("Pembrolizumab + Chemoradiation", "Chemoradiation"),
            ("Tisotumab Vedotin", "Investigator's Choice Chemotherapy"),
        ]
    },
    # SARCOMA
    {
        "disease": "Soft Tissue Sarcoma",
        "category": "sarcoma",
        "treatments": [
            ("Doxorubicin + Olaratumab", "Doxorubicin"),
            ("Neoadjuvant RT + Surgery", "Surgery + Adjuvant RT"),
        ]
    },
]

# Assessment categories and items - base set
ASSESSMENTS_BASE = {
    "ADMINISTRATIVE": [
        ("Informed Consent", "screening_only"),
        ("Inclusion/Exclusion Criteria", "screening_only"),
        ("Medical History & Demographics", "screening_only"),
        ("Randomization", "c1d1_only"),
    ],
    "CLINICAL ASSESSMENTS": [
        ("Physical Examination", "d1_and_eot"),
        ("Vital Signs", "all_visits"),
        ("ECOG/Karnofsky Performance Status", "d1_and_eot"),
        ("Weight", "d1_only"),
        ("Height", "screening_only"),
    ],
    "LABORATORY ASSESSMENTS": [
        ("Complete Blood Count (CBC)", "all_visits"),
        ("Comprehensive Metabolic Panel", "all_visits"),
        ("Liver Function Tests", "all_visits"),
        ("Serum Pregnancy Test", "screening_c1d1_eot"),
        ("Urinalysis", "d1_only"),
    ],
    "CARDIAC ASSESSMENTS": [
        ("12-Lead ECG", "d1_and_eot"),
    ],
    "SAFETY MONITORING": [
        ("Adverse Event Assessment", "all_visits_and_fu"),
        ("Concomitant Medications", "all_visits_and_fu"),
    ],
    "STUDY TREATMENT": [
        ("Investigational Product Dispensing", "arm_a_all"),
        ("Drug Accountability/Compliance", "arm_a_from_visit2"),
        ("Standard Therapy Administration", "d1_only"),
    ],
    "PATIENT-REPORTED OUTCOMES": [
        ("EORTC QLQ-C30", "d1_select_and_fu"),
        ("EQ-5D-5L", "d1_select_and_fu"),
    ],
}

# Category-specific additional assessments
CATEGORY_ASSESSMENTS = {
    "breast": {
        "IMAGING/TUMOR ASSESSMENT": [
            ("CT Chest/Abdomen/Pelvis", "imaging_schedule"),
            ("Bone Scan", "screening_only"),
            ("Bilateral Mammogram", "screening_12m"),
        ],
        "CARDIAC ASSESSMENTS": [
            ("Echocardiogram (ECHO/MUGA)", "screening_eot"),
        ],
        "PATIENT-REPORTED OUTCOMES": [
            ("FACT-B", "d1_select_and_fu"),
        ],
    },
    "thoracic": {
        "IMAGING/TUMOR ASSESSMENT": [
            ("CT Chest with Contrast", "imaging_schedule"),
            ("PET-CT", "screening_eot"),
            ("Brain MRI", "screening_only"),
        ],
        "PULMONARY FUNCTION": [
            ("Pulmonary Function Tests (PFTs)", "screening_eot"),
            ("6-Minute Walk Test", "screening_eot"),
        ],
        "PATIENT-REPORTED OUTCOMES": [
            ("FACT-L (Lung)", "d1_select_and_fu"),
            ("LCSS (Lung Cancer Symptom Scale)", "d1_select_and_fu"),
        ],
    },
    "gi": {
        "IMAGING/TUMOR ASSESSMENT": [
            ("CT Chest/Abdomen/Pelvis", "imaging_schedule"),
            ("PET-CT", "screening_eot"),
            ("MRI Liver", "screening_eot"),
        ],
        "TUMOR MARKERS": [
            ("CEA", "d1_only"),
            ("CA 19-9", "d1_only"),
            ("AFP (if applicable)", "d1_only"),
        ],
        "ENDOSCOPY": [
            ("EGD/Colonoscopy", "screening_only"),
        ],
        "PATIENT-REPORTED OUTCOMES": [
            ("FACT-G (GI)", "d1_select_and_fu"),
        ],
    },
    "gu": {
        "IMAGING/TUMOR ASSESSMENT": [
            ("CT Chest/Abdomen/Pelvis", "imaging_schedule"),
            ("Bone Scan", "screening_eot"),
            ("MRI Pelvis", "screening_eot"),
        ],
        "TUMOR MARKERS": [
            ("PSA", "d1_only"),
        ],
        "PATIENT-REPORTED OUTCOMES": [
            ("FACT-P (Prostate)", "d1_select_and_fu"),
            ("IPSS (Urinary Symptoms)", "d1_select_and_fu"),
        ],
    },
    "head_neck": {
        "IMAGING/TUMOR ASSESSMENT": [
            ("CT Head/Neck with Contrast", "imaging_schedule"),
            ("PET-CT", "screening_eot"),
            ("MRI Head/Neck", "screening_only"),
        ],
        "DENTAL/ORAL": [
            ("Dental Evaluation", "screening_only"),
            ("Swallowing Assessment", "screening_eot"),
        ],
        "PATIENT-REPORTED OUTCOMES": [
            ("FACT-H&N", "d1_select_and_fu"),
            ("MDASI-HN", "d1_select_and_fu"),
        ],
    },
    "melanoma": {
        "IMAGING/TUMOR ASSESSMENT": [
            ("CT Chest/Abdomen/Pelvis", "imaging_schedule"),
            ("PET-CT", "screening_eot"),
            ("Brain MRI", "screening_eot"),
        ],
        "DERMATOLOGY": [
            ("Full Skin Examination", "d1_and_eot"),
        ],
        "PATIENT-REPORTED OUTCOMES": [
            ("FACT-M (Melanoma)", "d1_select_and_fu"),
        ],
    },
    "gyn": {
        "IMAGING/TUMOR ASSESSMENT": [
            ("CT Chest/Abdomen/Pelvis", "imaging_schedule"),
            ("PET-CT", "screening_eot"),
            ("Transvaginal Ultrasound", "screening_only"),
        ],
        "TUMOR MARKERS": [
            ("CA-125", "d1_only"),
        ],
        "PATIENT-REPORTED OUTCOMES": [
            ("FACT-O (Ovarian)", "d1_select_and_fu"),
            ("FACT-Cx (Cervix)", "d1_select_and_fu"),
        ],
    },
    "sarcoma": {
        "IMAGING/TUMOR ASSESSMENT": [
            ("CT Chest", "imaging_schedule"),
            ("MRI of Primary Site", "imaging_schedule"),
            ("PET-CT", "screening_only"),
        ],
        "CARDIAC ASSESSMENTS": [
            ("Echocardiogram (ECHO/MUGA)", "screening_eot"),
        ],
        "PATIENT-REPORTED OUTCOMES": [
            ("TESS (Toronto Extremity Salvage)", "d1_select_and_fu"),
        ],
    },
}

# Radiation-specific assessments
RADIATION_ASSESSMENTS = {
    "RADIATION THERAPY": [
        ("Radiation Treatment Planning CT/Simulation", "screening_only"),
        ("Radiation Treatment Delivery", "rt_schedule"),
        ("Weekly On-Treatment Visit (RT)", "rt_weekly"),
    ],
    "RADIATION TOXICITY MONITORING": [
        ("Acute Radiation Toxicity Assessment", "rt_weekly"),
        ("Late Radiation Effects Assessment", "fu_only"),
    ],
}

# Surgery-specific assessments
SURGERY_ASSESSMENTS = {
    "SURGICAL MANAGEMENT": [
        ("Surgical Fitness Assessment", "screening_only"),
        ("Preoperative Evaluation", "preop_only"),
        ("Surgical Procedure", "surgery_day"),
        ("Postoperative Assessment", "postop_visits"),
    ],
    "PATHOLOGY": [
        ("Surgical Pathology Review", "postop_only"),
        ("Margin Assessment", "postop_only"),
    ],
}


def get_assessments_for_trial(config: 'TrialConfig') -> dict:
    """Get the appropriate assessments based on trial category and treatment."""
    assessments = dict(ASSESSMENTS_BASE)
    
    # Add category-specific assessments
    category = config.category
    if category in CATEGORY_ASSESSMENTS:
        for section, items in CATEGORY_ASSESSMENTS[category].items():
            if section in assessments:
                assessments[section] = assessments[section] + items
            else:
                assessments[section] = items
    
    # Check if trial involves radiation
    treatment_lower = config.treatment_name.lower()
    if any(rt in treatment_lower for rt in ['radiation', 'chemoradiation', 'rt', ' rt ', 'sbrt', 'imrt']):
        for section, items in RADIATION_ASSESSMENTS.items():
            assessments[section] = items
    
    # Check if trial involves surgery
    if any(surg in treatment_lower for surg in ['surgery', 'cystectomy', 'prostatectomy', 'resection', 'turbt']):
        for section, items in SURGERY_ASSESSMENTS.items():
            assessments[section] = items
    
    return assessments


def generate_trial_configs(num_trials: int = 20) -> List[TrialConfig]:
    """Generate configurations for multiple trials with variety across tumor types."""
    configs = []
    
    # Distribution: 5 simple, 10 moderate, 5 complex
    complexities = ["simple"] * 5 + ["moderate"] * 10 + ["complex"] * 5
    random.seed(42)  # For reproducibility
    random.shuffle(complexities)
    
    # Ensure diverse disease representation
    # Pick templates to ensure we cover different categories
    categories_to_cover = ["breast", "thoracic", "gi", "gi", "gu", "head_neck", 
                           "melanoma", "gyn", "sarcoma", "thoracic", "gi", "gu",
                           "breast", "thoracic", "gi", "melanoma", "gyn", "gi", 
                           "thoracic", "gu"]
    
    for i in range(num_trials):
        trial_id = f"{i+1:02d}"
        complexity = complexities[i]
        style_variant = (i % 5) + 1
        
        # Select template from target category
        target_category = categories_to_cover[i % len(categories_to_cover)]
        matching_templates = [t for t in TRIAL_TEMPLATES if t["category"] == target_category]
        if not matching_templates:
            matching_templates = TRIAL_TEMPLATES
        
        template = random.choice(matching_templates)
        disease = template["disease"]
        category = template["category"]
        treatment_name, control_name = random.choice(template["treatments"])
        
        # Check for radiation/surgery
        treatment_lower = treatment_name.lower()
        has_radiation = any(rt in treatment_lower for rt in 
                           ['radiation', 'chemoradiation', 'rt ', ' rt', 'sbrt', 'imrt'])
        has_surgery = any(surg in treatment_lower for surg in 
                         ['surgery', 'cystectomy', 'prostatectomy', 'resection', 'turbt'])
        
        # Adjust cycle length and treatment duration based on modality
        if has_radiation:
            cycle_days = 7  # Weekly during RT
            treatment_months = random.choice([2, 3, 6])  # RT is shorter
        elif has_surgery:
            cycle_days = 28
            treatment_months = random.choice([3, 6, 12])  # Perioperative
        else:
            cycle_days = random.choice([21, 28, 28, 28, 35])
            treatment_months = random.choice([6, 6, 9, 12, 12])
        
        # Visit schedules based on complexity and modality
        if has_radiation:
            # RT: daily or weekly visits during treatment
            arm_a_visit_days = [1, 2, 3, 4, 5] if complexity == "complex" else [1]
            arm_b_visit_days = [1]
            imaging_months = [0, 3, 6]
        elif has_surgery:
            # Surgery: preop, surgery, postop visits
            arm_a_visit_days = [1, 7, 14] if complexity != "simple" else [1]
            arm_b_visit_days = [1]
            imaging_months = [0, 3, 6]
        elif complexity == "simple":
            arm_a_visit_days = [1]
            arm_b_visit_days = [1]
            imaging_months = [0, 6] if treatment_months >= 6 else [0, 3]
        elif complexity == "moderate":
            if cycle_days == 28:
                arm_a_visit_days = [1, 15]
                arm_b_visit_days = [1]
            else:
                arm_a_visit_days = [1, 8]
                arm_b_visit_days = [1]
            imaging_months = [0, 6, 12] if treatment_months >= 12 else [0, 6]
        else:  # complex
            if cycle_days == 28:
                arm_a_visit_days = [1, 8, 15]
                arm_b_visit_days = [1, 15]
            else:
                arm_a_visit_days = [1, 8, 15]
                arm_b_visit_days = [1, 8]
            imaging_months = [0, 3, 6, 9, 12][:((treatment_months // 3) + 1)]
        
        configs.append(TrialConfig(
            trial_id=trial_id,
            disease=disease,
            category=category,
            treatment_name=treatment_name,
            control_name=control_name,
            cycle_days=cycle_days,
            treatment_months=treatment_months,
            arm_a_visit_days=arm_a_visit_days,
            arm_b_visit_days=arm_b_visit_days,
            imaging_months=imaging_months,
            complexity=complexity,
            style_variant=style_variant,
            has_radiation=has_radiation,
            has_surgery=has_surgery,
        ))
    
    return configs


def calculate_time_toxic_days(config: TrialConfig) -> Dict[str, Dict[str, int]]:
    """Calculate time-toxic days for each arm at each interval."""
    
    def get_visit_days(visit_days_in_cycle: List[int], cycle_days: int, 
                       treatment_months: int) -> List[int]:
        total_days = treatment_months * 30
        num_cycles = total_days // cycle_days
        
        all_days = set()
        for cycle in range(num_cycles + 1):
            cycle_start = cycle * cycle_days
            for visit_day in visit_days_in_cycle:
                calendar_day = cycle_start + visit_day
                if calendar_day <= total_days:
                    all_days.add(calendar_day)
        
        all_days.add(total_days)  # EOT visit
        return sorted(all_days)
    
    arm_a_days = get_visit_days(config.arm_a_visit_days, config.cycle_days, 
                                 config.treatment_months)
    arm_b_days = get_visit_days(config.arm_b_visit_days, config.cycle_days, 
                                 config.treatment_months)
    
    # Add imaging days if separate
    for month in config.imaging_months:
        img_day = month * 30 if month > 0 else 1
        if img_day not in arm_a_days and img_day <= config.treatment_months * 30:
            arm_a_days.append(img_day)
        if img_day not in arm_b_days and img_day <= config.treatment_months * 30:
            arm_b_days.append(img_day)
    
    arm_a_days = sorted(set(arm_a_days))
    arm_b_days = sorted(set(arm_b_days))
    
    # Add follow-up visits
    if config.treatment_months <= 6:
        arm_a_days.extend([270, 365])
        arm_b_days.extend([270, 365])
    elif config.treatment_months <= 9:
        arm_a_days.append(365)
        arm_b_days.append(365)
    
    arm_a_days = sorted(set(arm_a_days))
    arm_b_days = sorted(set(arm_b_days))
    
    screening_days = 2
    
    intervals = [30, 90, 180, 270, 365]
    interval_names = ["month1", "month3", "month6", "month9", "month12"]
    
    results = {
        "A": {"screening": screening_days},
        "B": {"screening": screening_days}
    }
    
    for interval, name in zip(intervals, interval_names):
        results["A"][name] = len([d for d in arm_a_days if d <= interval])
        results["B"][name] = len([d for d in arm_b_days if d <= interval])
    
    return results


# Consortium names by category
CONSORTIUM_NAMES = {
    "breast": "BREAST ONCOLOGY RESEARCH CONSORTIUM",
    "thoracic": "THORACIC ONCOLOGY COOPERATIVE GROUP",
    "gi": "GASTROINTESTINAL CANCER RESEARCH ALLIANCE",
    "gu": "GENITOURINARY ONCOLOGY CONSORTIUM",
    "head_neck": "HEAD AND NECK CANCER RESEARCH GROUP",
    "melanoma": "MELANOMA AND SKIN CANCER COOPERATIVE",
    "gyn": "GYNECOLOGIC ONCOLOGY RESEARCH CONSORTIUM",
    "sarcoma": "SARCOMA ALLIANCE FOR RESEARCH",
}

PROTOCOL_PREFIXES = {
    "breast": "BRST",
    "thoracic": "THOR",
    "gi": "GICA",
    "gu": "GUCA",
    "head_neck": "HNSC",
    "melanoma": "MELA",
    "gyn": "GYNO",
    "sarcoma": "SARC",
}


def generate_html_schedule(config: TrialConfig, style: StyleConfig) -> str:
    """Generate HTML for a schedule of assessments."""
    
    # Get appropriate assessments for this trial
    assessments = get_assessments_for_trial(config)
    
    num_cycles = (config.treatment_months * 30) // config.cycle_days
    all_visit_days = sorted(set(config.arm_a_visit_days + config.arm_b_visit_days))
    
    # Build column structure
    columns = []
    columns.append({
        "name": "Screening",
        "subtext": f"Day -{config.cycle_days} to -1",
        "arm": None,
        "type": "screening"
    })
    
    # First 2-3 cycles in detail
    detail_cycles = min(3, num_cycles)
    for cycle in range(1, detail_cycles + 1):
        for day in all_visit_days:
            arm_indicator = None
            if day in config.arm_a_visit_days and day not in config.arm_b_visit_days:
                arm_indicator = "A"
            columns.append({
                "name": f"C{cycle}D{day}",
                "subtext": "±3d",
                "arm": arm_indicator,
                "type": f"c{cycle}d{day}"
            })
    
    # Remaining cycles grouped
    if num_cycles > detail_cycles:
        remaining = f"C{detail_cycles + 1}-C{num_cycles}"
        columns.append({
            "name": remaining,
            "subtext": "D1",
            "arm": None,
            "type": "remaining_d1"
        })
        if len(config.arm_a_visit_days) > 1:
            columns.append({
                "name": remaining,
                "subtext": f"D{config.arm_a_visit_days[-1]}",
                "arm": "A",
                "type": "remaining_other"
            })
    
    # EOT and Follow-up
    columns.append({
        "name": "EOT",
        "subtext": f"±7d",
        "arm": None,
        "type": "eot"
    })
    columns.append({
        "name": "M9 FU",
        "subtext": "±14d",
        "arm": None,
        "type": "fu9"
    })
    columns.append({
        "name": "M12 FU",
        "subtext": "±14d",
        "arm": None,
        "type": "fu12"
    })
    
    # Generate header row
    header_cells = '<th class="assessment-col" rowspan="2">Assessment</th>\n'
    for col in columns:
        arm_sup = f'<sup>{col["arm"]}</sup>' if col["arm"] else ""
        header_cells += f'<th>{col["name"]}{arm_sup}<br><span class="sub-header">{col["subtext"]}</span></th>\n'
    
    # Generate assessment rows
    assessment_rows = ""
    for category, items in assessments.items():
        assessment_rows += f'<tr class="category-row"><td colspan="{len(columns) + 1}">{category}</td></tr>\n'
        
        for assessment_name, schedule_type in items:
            row = f'<td class="assessment-col">{assessment_name}</td>'
            
            for col in columns:
                cell = ""
                col_type = col["type"]
                is_arm_a_col = col["arm"] == "A"
                
                is_screening = col_type == "screening"
                is_c1d1 = col_type == "c1d1"
                is_d1 = "d1" in col_type.lower() or col_type == "remaining_d1"
                is_eot = col_type == "eot"
                is_fu = col_type.startswith("fu")
                is_fu12 = col_type == "fu12"
                is_treatment = not is_screening and not is_fu
                
                if schedule_type == "screening_only":
                    if is_screening:
                        cell = "X"
                elif schedule_type == "c1d1_only":
                    if is_c1d1:
                        cell = "X"
                elif schedule_type == "all_visits":
                    if is_treatment:
                        cell = "X<sup>A</sup>" if is_arm_a_col else "X"
                elif schedule_type == "all_visits_and_fu":
                    if is_treatment or is_fu:
                        cell = "X<sup>A</sup>" if is_arm_a_col else "X"
                elif schedule_type == "d1_only":
                    if is_screening or is_d1 or is_eot:
                        cell = "X"
                elif schedule_type == "d1_and_eot":
                    if is_screening or is_d1 or is_eot:
                        cell = "X"
                elif schedule_type == "d1_select":
                    if is_screening or is_d1 and ("c1" in col_type or "c3" in col_type or col_type == "remaining_d1") or is_eot:
                        cell = "X"
                elif schedule_type == "d1_select_and_fu":
                    if is_screening or (is_d1 and ("c2" in col_type or col_type == "remaining_d1")) or is_eot or is_fu12:
                        cell = "X"
                elif schedule_type == "arm_a_all":
                    if is_treatment and not is_eot:
                        cell = "X<sup>A</sup>"
                elif schedule_type == "arm_a_from_visit2":
                    if is_treatment and not is_c1d1 and not is_eot:
                        cell = "X<sup>A</sup>"
                elif schedule_type == "screening_c1d1_eot":
                    if is_screening or is_c1d1 or is_eot:
                        cell = "X"
                elif schedule_type == "screening_eot":
                    if is_screening or is_eot:
                        cell = "X"
                elif schedule_type == "imaging_schedule":
                    if is_screening or is_eot or is_fu12:
                        cell = "X"
                elif schedule_type == "screening_12m":
                    if is_screening or is_fu12:
                        cell = "X"
                
                row += f'<td class="x-mark">{cell}</td>'
            
            assessment_rows += f'<tr>{row}</tr>\n'
    
    prefix = PROTOCOL_PREFIXES.get(config.category, "ONCO")
    protocol_id = f"{prefix}-2025-{config.trial_id}"
    consortium_name = CONSORTIUM_NAMES.get(config.category, "ONCOLOGY RESEARCH CONSORTIUM")
    version_date = datetime.now().strftime("%d %B %Y")
    
    # Style-specific CSS
    table_border_css = f"""
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid {style.border_color}; padding: 3px 5px; text-align: center; vertical-align: middle; }}
        th {{ background-color: {style.header_bg}; color: {style.header_text}; font-weight: bold; }}
    """
    
    if style.table_style == "modern":
        table_border_css += "tr:nth-child(even) { background-color: #f8f9fa; }"
    elif style.table_style == "minimal":
        table_border_css = f"""
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border-bottom: 1px solid {style.border_color}; padding: 4px 5px; text-align: center; vertical-align: middle; }}
            th {{ background-color: {style.header_bg}; color: {style.header_text}; font-weight: bold; border: 1px solid {style.border_color}; }}
        """
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Schedule of Assessments - {protocol_id}</title>
    <style>
        @page {{
            size: letter landscape;
            margin: 0.4in;
        }}
        
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: {style.font_family};
            font-size: {style.font_size_base};
            line-height: 1.3;
            padding: 0.3in;
            background: #fff;
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 12px;
            border-bottom: 2px solid {style.accent_color};
            padding-bottom: 8px;
        }}
        
        .header h1 {{
            font-size: 11pt;
            font-weight: bold;
            color: {style.accent_color};
            margin-bottom: 4px;
        }}
        
        .protocol-info {{
            font-size: 8.5pt;
            color: #333;
        }}
        
        .section-title {{
            font-size: 10pt;
            font-weight: bold;
            margin: 10px 0 8px 0;
            color: {style.accent_color};
        }}
        
        .table-container {{
            overflow-x: auto;
            margin-bottom: 12px;
        }}
        
        {table_border_css}
        
        .assessment-col {{
            text-align: left !important;
            min-width: 130px;
            background-color: #fafafa !important;
            color: #000 !important;
            font-weight: normal !important;
        }}
        
        .category-row {{
            background-color: {style.category_bg} !important;
        }}
        
        .category-row td {{
            text-align: left !important;
            padding-left: 8px !important;
            font-weight: bold;
            color: #000 !important;
        }}
        
        .sub-header {{
            font-size: 7pt;
            font-weight: normal;
            opacity: 0.8;
        }}
        
        .x-mark {{
            font-weight: bold;
        }}
        
        sup {{
            font-size: 6pt;
            color: #666;
        }}
        
        .legend {{
            margin-top: 10px;
            padding: 8px;
            background-color: #f5f5f5;
            border: 1px solid #ddd;
            font-size: 8pt;
        }}
        
        .footnotes {{
            margin-top: 12px;
            font-size: 7pt;
            line-height: 1.4;
            columns: 2;
            column-gap: 20px;
        }}
        
        .footnotes p {{
            margin-bottom: 3px;
            text-indent: -10px;
            padding-left: 10px;
            break-inside: avoid;
        }}
        
        .page-footer {{
            margin-top: 15px;
            padding-top: 6px;
            border-top: 1px solid {style.accent_color};
            font-size: 7pt;
            display: flex;
            justify-content: space-between;
        }}
        
        @media print {{
            body {{ padding: 0; }}
            .footnotes {{ columns: 1; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{consortium_name}</h1>
        <div class="protocol-info">
            Protocol {protocol_id}: A Randomized Phase III Trial of {config.treatment_name}<br>
            Versus {config.control_name} in {config.disease}
        </div>
    </div>

    <div class="section-title">Section 7: Schedule of Assessments</div>

    <div class="table-container">
        <table>
            <thead>
                <tr>
                    {header_cells}
                </tr>
            </thead>
            <tbody>
                {assessment_rows}
            </tbody>
        </table>
    </div>

    <div class="legend">
        <strong>Legend:</strong> X = Required for all patients; X<sup>A</sup> = Required for Arm A only<br>
        <strong>Arm A ({config.treatment_name}):</strong> Visits on Days {', '.join(map(str, config.arm_a_visit_days))} of each {config.cycle_days}-day cycle for {config.treatment_months} months<br>
        <strong>Arm B ({config.control_name}):</strong> Visits on Days {', '.join(map(str, config.arm_b_visit_days))} of each {config.cycle_days}-day cycle for {config.treatment_months} months
    </div>

    <div class="footnotes">
        <p><sup>a</sup> <strong>Screening:</strong> All assessments must be completed within {config.cycle_days} days prior to C1D1. Screening may require 1-2 visits.</p>
        <p><sup>b</sup> <strong>Treatment Phase:</strong> {config.cycle_days}-day cycles. Arm A: Days {', '.join(map(str, config.arm_a_visit_days))}; Arm B: Days {', '.join(map(str, config.arm_b_visit_days))}.</p>
        <p><sup>c</sup> <strong>Labs:</strong> CBC includes WBC with differential, hemoglobin, hematocrit, platelets, ANC.</p>
        <p><sup>d</sup> <strong>CMP:</strong> Includes sodium, potassium, chloride, bicarbonate, BUN, creatinine, glucose, calcium.</p>
        <p><sup>e</sup> <strong>EOT Visit:</strong> End of treatment visit 30-42 days after last dose or at early discontinuation.</p>
        <p><sup>f</sup> <strong>Follow-Up:</strong> Month 9 and 12 visits for disease recurrence and survival monitoring.</p>
        <p><sup>g</sup> <strong>Adverse Events:</strong> Assessed continuously from first dose through 30 days after last dose.</p>
        <p><sup>h</sup> <strong>Imaging:</strong> CT scans at screening, EOT, and Month 12 follow-up per RECIST 1.1.</p>
    </div>

    <div class="page-footer">
        <div>Protocol {protocol_id} | Version 1.0 | {version_date}</div>
        <div>Page 58 of 124</div>
        <div>CONFIDENTIAL</div>
    </div>
</body>
</html>"""
    
    return html


def convert_to_pdf(html_path: str, pdf_path: str) -> bool:
    """Convert HTML to PDF using available tools."""
    if WKHTMLTOPDF_PATH:
        try:
            result = subprocess.run(
                [WKHTMLTOPDF_PATH, '--orientation', 'Landscape', 
                 '--page-size', 'Letter', '--quiet', html_path, pdf_path],
                capture_output=True
            )
            return result.returncode == 0
        except Exception:
            return False
    elif WEASYPRINT_AVAILABLE:
        try:
            HTML(filename=html_path).write_pdf(pdf_path)
            return True
        except Exception:
            return False
    return False


def generate_ground_truth_csv(configs: List[TrialConfig], output_path: str):
    """Generate CSV with ground truth time-toxic days."""
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'schedule_id', 'complexity', 'arms', 'arm', 'category', 'disease',
            'cycle_days', 'treatment_months', 'visit_days',
            'has_radiation', 'has_surgery',
            'screening_days', 'month1_days', 'month3_days', 
            'month6_days', 'month9_days', 'month12_days', 'notes'
        ])
        
        for config in configs:
            ttd = calculate_time_toxic_days(config)
            
            for arm in ['A', 'B']:
                visit_days = config.arm_a_visit_days if arm == 'A' else config.arm_b_visit_days
                treatment = config.treatment_name if arm == 'A' else config.control_name
                
                modalities = []
                if config.has_radiation:
                    modalities.append("RT")
                if config.has_surgery:
                    modalities.append("Surgery")
                modality_str = "+".join(modalities) if modalities else "Systemic"
                
                writer.writerow([
                    config.trial_id,
                    config.complexity,
                    'two',
                    arm,
                    config.category,
                    config.disease,
                    config.cycle_days,
                    config.treatment_months,
                    ','.join(map(str, visit_days)),
                    config.has_radiation,
                    config.has_surgery,
                    ttd[arm]['screening'],
                    ttd[arm]['month1'],
                    ttd[arm]['month3'],
                    ttd[arm]['month6'],
                    ttd[arm]['month9'],
                    ttd[arm]['month12'],
                    f"{treatment}; {config.cycle_days}-day cycles; {modality_str}"
                ])


def main():
    """Main function to generate all schedules."""
    
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'synthetic_schedules')
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"=" * 60)
    print("SYNTHETIC SCHEDULE OF ASSESSMENTS GENERATOR")
    print(f"=" * 60)
    print(f"Output directory: {output_dir}")
    print()
    
    # Check PDF conversion capability
    pdf_tool = None
    if WKHTMLTOPDF_PATH:
        pdf_tool = "wkhtmltopdf"
    elif WEASYPRINT_AVAILABLE:
        pdf_tool = "weasyprint"
    
    if pdf_tool:
        print(f"✓ PDF conversion available via: {pdf_tool}")
    else:
        print("⚠ No PDF converter found. HTML files will be generated.")
        print("  Install wkhtmltopdf: brew install wkhtmltopdf")
        print("  Or convert manually: Open HTML in browser → Print → Save as PDF")
    print()
    
    # Generate configurations
    configs = generate_trial_configs(20)
    
    print("Generating schedules...")
    html_count = 0
    pdf_count = 0
    
    for config in configs:
        style = STYLE_PRESETS[config.style_variant]
        html_content = generate_html_schedule(config, style)
        
        filename_base = f"synthetic_schedule_{config.trial_id}_{config.complexity}_two"
        
        # Save HTML
        html_path = os.path.join(output_dir, f"{filename_base}.html")
        with open(html_path, 'w') as f:
            f.write(html_content)
        html_count += 1
        
        # Convert to PDF if possible
        if pdf_tool:
            pdf_path = os.path.join(output_dir, f"{filename_base}.pdf")
            if convert_to_pdf(html_path, pdf_path):
                pdf_count += 1
                print(f"  ✓ {filename_base} (HTML + PDF)")
            else:
                print(f"  ✓ {filename_base} (HTML only)")
        else:
            print(f"  ✓ {filename_base} (HTML)")
    
    # Generate ground truth CSV
    csv_path = os.path.join(output_dir, 'ground_truth.csv')
    generate_ground_truth_csv(configs, csv_path)
    print(f"\n✓ Ground truth CSV saved")
    
    # Generate detailed calculations markdown
    calc_path = os.path.join(output_dir, 'ground_truth_calculations.md')
    with open(calc_path, 'w') as f:
        f.write("# Ground Truth Calculations for All Synthetic Schedules\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        
        for config in configs:
            ttd = calculate_time_toxic_days(config)
            modalities = []
            if config.has_radiation:
                modalities.append("Radiation")
            if config.has_surgery:
                modalities.append("Surgery")
            modality_str = " + ".join(modalities) if modalities else "Systemic therapy"
            
            f.write(f"## Schedule {config.trial_id} ({config.complexity.upper()}) - {config.category.upper()}\n\n")
            f.write(f"| Property | Value |\n")
            f.write(f"|----------|-------|\n")
            f.write(f"| Disease | {config.disease} |\n")
            f.write(f"| Category | {config.category} |\n")
            f.write(f"| Arm A | {config.treatment_name} |\n")
            f.write(f"| Arm B | {config.control_name} |\n")
            f.write(f"| Modality | {modality_str} |\n")
            f.write(f"| Cycle Length | {config.cycle_days} days |\n")
            f.write(f"| Treatment Duration | {config.treatment_months} months |\n")
            f.write(f"| Arm A Visit Days | {config.arm_a_visit_days} |\n")
            f.write(f"| Arm B Visit Days | {config.arm_b_visit_days} |\n\n")
            
            f.write("### Time-Toxic Days\n\n")
            f.write("| Interval | Arm A | Arm B | Difference |\n")
            f.write("|----------|-------|-------|------------|\n")
            for interval in ['screening', 'month1', 'month3', 'month6', 'month9', 'month12']:
                diff = ttd['A'][interval] - ttd['B'][interval]
                diff_str = f"+{diff}" if diff > 0 else str(diff)
                f.write(f"| {interval.replace('month', 'Month ')} | {ttd['A'][interval]} | {ttd['B'][interval]} | {diff_str} |\n")
            f.write("\n---\n\n")
    
    print(f"✓ Calculations markdown saved")
    
    # Summary
    print()
    print(f"=" * 60)
    print("GENERATION COMPLETE")
    print(f"=" * 60)
    print(f"HTML files: {html_count}")
    print(f"PDF files:  {pdf_count}")
    print(f"Ground truth CSV: {csv_path}")
    print()
    print("Complexity distribution:")
    print(f"  Simple:   {sum(1 for c in configs if c.complexity == 'simple')}")
    print(f"  Moderate: {sum(1 for c in configs if c.complexity == 'moderate')}")
    print(f"  Complex:  {sum(1 for c in configs if c.complexity == 'complex')}")
    print()
    print("Disease category distribution:")
    categories = {}
    for c in configs:
        categories[c.category] = categories.get(c.category, 0) + 1
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")
    print()
    print("Treatment modality:")
    print(f"  With Radiation: {sum(1 for c in configs if c.has_radiation)}")
    print(f"  With Surgery:   {sum(1 for c in configs if c.has_surgery)}")
    print(f"  Systemic Only:  {sum(1 for c in configs if not c.has_radiation and not c.has_surgery)}")
    print()
    print("Style distribution:")
    for i in range(1, 6):
        count = sum(1 for c in configs if c.style_variant == i)
        style = STYLE_PRESETS[i]
        print(f"  Style {i} ({style.table_style}): {count}")
    
    if not pdf_tool:
        print()
        print("=" * 60)
        print("TO CONVERT HTML TO PDF:")
        print("=" * 60)
        print("Option 1: Install wkhtmltopdf")
        print("  brew install wkhtmltopdf")
        print("  Then re-run this script")
        print()
        print("Option 2: Use browser")
        print("  Open each HTML file in Chrome/Safari")
        print("  File → Print → Save as PDF")
        print()
        print("Option 3: Batch convert with Chrome")
        print('  for f in synthetic_schedules/*.html; do')
        print('    /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\')
        print('      --headless --disable-gpu --print-to-pdf="${f%.html}.pdf" "$f"')
        print('  done')


if __name__ == "__main__":
    main()
