"""
Shared configuration for Quantification of Time Toxicity analysis.
"""
import os

# Base paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANALYSIS_ROOT = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")

# Input files (read-only)
CSV_RUNS = [
    os.path.join(RESULTS_DIR, "vanilla_summaries_dataset.csv"),
    os.path.join(RESULTS_DIR, "vanilla_summaries_dataset_run2.csv"),
    os.path.join(RESULTS_DIR, "vanilla_summaries_dataset_run3.csv"),
]
JSON_RUNS = [
    os.path.join(RESULTS_DIR, "vanilla_summaries_dataset.json"),
    os.path.join(RESULTS_DIR, "vanilla_summaries_dataset_run2.json"),
]  # Run 3 JSON only has 99 entries, excluded from category analysis
PROTOCOL_METADATA = os.path.join(RESULTS_DIR, "protocol_metadata.csv")
INCLUDED_TRIALS = os.path.join(PROJECT_ROOT, "Included Trials.csv")

# Output directories
DATA_DIR = os.path.join(ANALYSIS_ROOT, "data")
FIGURES_DIR = os.path.join(ANALYSIS_ROOT, "figures")
TABLES_DIR = os.path.join(ANALYSIS_ROOT, "tables")

# Timepoint columns in order
TIMEPOINTS = ["screening", "1_month", "3_months", "6_months", "9_months", "12_months"]

# Category breakdown categories
CATEGORIES = ["core_treatment", "imaging_diagnostics", "labs", "clinic_visits"]

# Drug classification dictionary
DRUG_CLASSES = {
    # Immunotherapy / Immune Checkpoint Inhibitors
    "pembrolizumab": "Immunotherapy", "nivolumab": "Immunotherapy",
    "atezolizumab": "Immunotherapy", "durvalumab": "Immunotherapy",
    "ipilimumab": "Immunotherapy", "avelumab": "Immunotherapy",
    "cemiplimab": "Immunotherapy", "tremelimumab": "Immunotherapy",
    "dostarlimab": "Immunotherapy", "relatlimab": "Immunotherapy",
    "tislelizumab": "Immunotherapy", "camrelizumab": "Immunotherapy",
    "sintilimab": "Immunotherapy", "toripalimab": "Immunotherapy",
    "sugemalimab": "Immunotherapy", "serplulimab": "Immunotherapy",
    "pidilizumab": "Immunotherapy",
    # CAR-T and other immunotherapies
    "interferon": "Immunotherapy", "interleukin": "Immunotherapy",
    "sipuleucel": "Immunotherapy", "talimogene": "Immunotherapy",
    "blinatumomab": "Immunotherapy",

    # Targeted Therapy - Monoclonal antibodies
    "trastuzumab": "Targeted Therapy", "pertuzumab": "Targeted Therapy",
    "bevacizumab": "Targeted Therapy", "cetuximab": "Targeted Therapy",
    "panitumumab": "Targeted Therapy", "ramucirumab": "Targeted Therapy",
    "rituximab": "Targeted Therapy", "obinutuzumab": "Targeted Therapy",
    "daratumumab": "Targeted Therapy", "elotuzumab": "Targeted Therapy",
    "mogamulizumab": "Targeted Therapy", "margetuximab": "Targeted Therapy",
    "sacituzumab": "Targeted Therapy", "enfortumab": "Targeted Therapy",
    "trastuzumab deruxtecan": "Targeted Therapy",
    "trastuzumab emtansine": "Targeted Therapy",
    "ado-trastuzumab": "Targeted Therapy",
    "brentuximab": "Targeted Therapy", "polatuzumab": "Targeted Therapy",
    "inotuzumab": "Targeted Therapy", "gemtuzumab": "Targeted Therapy",
    "denosumab": "Targeted Therapy", "necitumumab": "Targeted Therapy",
    "olaratumab": "Targeted Therapy", "dinutuximab": "Targeted Therapy",
    "zanubrutinib": "Targeted Therapy",

    # Targeted Therapy - Small molecule inhibitors
    "olaparib": "Targeted Therapy", "niraparib": "Targeted Therapy",
    "rucaparib": "Targeted Therapy", "talazoparib": "Targeted Therapy",
    "veliparib": "Targeted Therapy",
    "palbociclib": "Targeted Therapy", "ribociclib": "Targeted Therapy",
    "abemaciclib": "Targeted Therapy",
    "osimertinib": "Targeted Therapy", "erlotinib": "Targeted Therapy",
    "gefitinib": "Targeted Therapy", "afatinib": "Targeted Therapy",
    "dacomitinib": "Targeted Therapy",
    "crizotinib": "Targeted Therapy", "alectinib": "Targeted Therapy",
    "ceritinib": "Targeted Therapy", "lorlatinib": "Targeted Therapy",
    "brigatinib": "Targeted Therapy",
    "sorafenib": "Targeted Therapy", "sunitinib": "Targeted Therapy",
    "pazopanib": "Targeted Therapy", "axitinib": "Targeted Therapy",
    "cabozantinib": "Targeted Therapy", "lenvatinib": "Targeted Therapy",
    "regorafenib": "Targeted Therapy", "vandetanib": "Targeted Therapy",
    "tivozanib": "Targeted Therapy", "nintedanib": "Targeted Therapy",
    "vemurafenib": "Targeted Therapy", "dabrafenib": "Targeted Therapy",
    "encorafenib": "Targeted Therapy",
    "trametinib": "Targeted Therapy", "cobimetinib": "Targeted Therapy",
    "binimetinib": "Targeted Therapy", "selumetinib": "Targeted Therapy",
    "ibrutinib": "Targeted Therapy", "acalabrutinib": "Targeted Therapy",
    "idelalisib": "Targeted Therapy", "duvelisib": "Targeted Therapy",
    "venetoclax": "Targeted Therapy",
    "ruxolitinib": "Targeted Therapy", "fedratinib": "Targeted Therapy",
    "midostaurin": "Targeted Therapy", "gilteritinib": "Targeted Therapy",
    "lapatinib": "Targeted Therapy", "neratinib": "Targeted Therapy",
    "tucatinib": "Targeted Therapy",
    "everolimus": "Targeted Therapy", "temsirolimus": "Targeted Therapy",
    "ixazomib": "Targeted Therapy", "carfilzomib": "Targeted Therapy",
    "bortezomib": "Targeted Therapy",
    "panobinostat": "Targeted Therapy", "vorinostat": "Targeted Therapy",
    "vismodegib": "Targeted Therapy", "sonidegib": "Targeted Therapy",
    "entrectinib": "Targeted Therapy", "larotrectinib": "Targeted Therapy",
    "selpercatinib": "Targeted Therapy", "pralsetinib": "Targeted Therapy",
    "capmatinib": "Targeted Therapy", "tepotinib": "Targeted Therapy",
    "savolitinib": "Targeted Therapy",
    "tazemetostat": "Targeted Therapy",
    "alpelisib": "Targeted Therapy", "capivasertib": "Targeted Therapy",
    "erdafitinib": "Targeted Therapy",
    "ivosidenib": "Targeted Therapy", "enasidenib": "Targeted Therapy",
    "glasdegib": "Targeted Therapy", "quizartinib": "Targeted Therapy",
    "sotorasib": "Targeted Therapy", "adagrasib": "Targeted Therapy",
    "lenalidomide": "Targeted Therapy", "pomalidomide": "Targeted Therapy",
    "thalidomide": "Targeted Therapy",
    "cediranib": "Targeted Therapy", "motesanib": "Targeted Therapy",
    "vatalanib": "Targeted Therapy",
    "figitumumab": "Targeted Therapy", "ganitumab": "Targeted Therapy",
    "onartuzumab": "Targeted Therapy", "rilotumumab": "Targeted Therapy",

    # Chemotherapy
    "cisplatin": "Chemotherapy", "carboplatin": "Chemotherapy",
    "oxaliplatin": "Chemotherapy",
    "paclitaxel": "Chemotherapy", "docetaxel": "Chemotherapy",
    "nab-paclitaxel": "Chemotherapy", "cabazitaxel": "Chemotherapy",
    "gemcitabine": "Chemotherapy", "capecitabine": "Chemotherapy",
    "fluorouracil": "Chemotherapy", "5-fu": "Chemotherapy",
    "5-fluorouracil": "Chemotherapy",
    "irinotecan": "Chemotherapy", "topotecan": "Chemotherapy",
    "doxorubicin": "Chemotherapy", "epirubicin": "Chemotherapy",
    "daunorubicin": "Chemotherapy", "idarubicin": "Chemotherapy",
    "cyclophosphamide": "Chemotherapy", "ifosfamide": "Chemotherapy",
    "temozolomide": "Chemotherapy", "dacarbazine": "Chemotherapy",
    "etoposide": "Chemotherapy", "vinorelbine": "Chemotherapy",
    "vincristine": "Chemotherapy", "vinblastine": "Chemotherapy",
    "vinflunine": "Chemotherapy",
    "methotrexate": "Chemotherapy", "pemetrexed": "Chemotherapy",
    "bleomycin": "Chemotherapy", "mitomycin": "Chemotherapy",
    "mitoxantrone": "Chemotherapy",
    "busulfan": "Chemotherapy", "melphalan": "Chemotherapy",
    "chlorambucil": "Chemotherapy", "bendamustine": "Chemotherapy",
    "fludarabine": "Chemotherapy", "cladribine": "Chemotherapy",
    "cytarabine": "Chemotherapy", "azacitidine": "Chemotherapy",
    "decitabine": "Chemotherapy", "guadecitabine": "Chemotherapy",
    "mercaptopurine": "Chemotherapy", "thioguanine": "Chemotherapy",
    "trabectedin": "Chemotherapy", "eribulin": "Chemotherapy",
    "ixabepilone": "Chemotherapy",
    "streptozocin": "Chemotherapy", "lomustine": "Chemotherapy",
    "carmustine": "Chemotherapy", "procarbazine": "Chemotherapy",
    "prednisone": "Supportive", "prednisolone": "Supportive",
    "dexamethasone": "Supportive", "leucovorin": "Supportive",
    "levoleucovorin": "Supportive", "folinic acid": "Supportive",
    "filgrastim": "Supportive", "pegfilgrastim": "Supportive",

    # Endocrine Therapy
    "tamoxifen": "Endocrine", "letrozole": "Endocrine",
    "anastrozole": "Endocrine", "exemestane": "Endocrine",
    "fulvestrant": "Endocrine",
    "enzalutamide": "Endocrine", "abiraterone": "Endocrine",
    "apalutamide": "Endocrine", "darolutamide": "Endocrine",
    "bicalutamide": "Endocrine", "flutamide": "Endocrine",
    "goserelin": "Endocrine", "leuprolide": "Endocrine",
    "degarelix": "Endocrine", "octreotide": "Endocrine",
    "lanreotide": "Endocrine",

    # Radiation-related
    "radium-223": "Radiation", "radium": "Radiation",
    "lutetium": "Radiation", "iodine-131": "Radiation",
    "yttrium": "Radiation",

    # Other / Supportive
    "zoledronic": "Supportive", "zoledronate": "Supportive",
    "bisphosphonate": "Supportive",
    "placebo": "Supportive",
    "doxepin": "Supportive", "diphenhydramine": "Supportive",
    "sodium thiosulfate": "Supportive", "amifostine": "Supportive",
    "ondansetron": "Supportive", "granisetron": "Supportive",
    "aprepitant": "Supportive",
}

# Disease site groupings for analysis (merge small groups)
DISEASE_SITE_MERGE = {
    "Peds": "Other",
    "All": "Other",
}
MIN_GROUP_SIZE = 10  # Minimum N for inclusion in Kruskal-Wallis

# Extreme TT thresholds for threshold analysis
TT_THRESHOLDS = [30, 60, 90]
