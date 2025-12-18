#!/usr/bin/env python3
"""
Multi-Agent Prompt Optimization Comparison

Implements 4 different extraction strategies to optimize accuracy:
1. Agent 1: Context Window Split (early vs late windows)
2. Agent 2: Probabilistic Multi-Sample Aggregation
3. Agent 3: Chain-of-Thought with Explicit Cycle Enumeration
4. Agent 4: Bidirectional Extraction (front-to-back + back-to-front)

Usage:
    python3 agent_comparison.py [num_pdfs]
"""

import os
import csv
import json
import re
import time
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

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


# ============================================================================
# CONFIGURATION
# ============================================================================

MODEL = "gemini-3-flash-preview"
SCHEDULES_FOLDER = "synthetic_schedules"
GROUND_TRUTH_FILE = "synthetic_schedules/ground_truth.csv"

TIME_WINDOWS = ['screening', '1_month', '3_months', '6_months', '9_months', '12_months']
EARLY_WINDOWS = ['screening', '1_month', '3_months']
LATE_WINDOWS = ['6_months', '9_months', '12_months']


# ============================================================================
# PROMPTS FOR EACH AGENT
# ============================================================================

# Base prompt components
BASE_DEFINITIONS = """
**Healthcare Contact Day**: Any calendar day requiring in-person contact with the healthcare system (clinic visits, labs, imaging, infusions, procedures). Count each unique calendar day ONCE regardless of how many assessments occur that day.

**Cycle to Day Mapping**: For N-day cycles:
- C1D1 = Day 1, C1D15 = Day 15
- C2D1 = Day N+1 (e.g., Day 29 for 28-day cycles)
- C3D1 = Day 2N+1 (e.g., Day 57 for 28-day cycles)
"""

# Agent 1: Split Windows Prompts
PROMPT_EARLY_WINDOWS = """
You are an expert clinical trial protocol analyst. Extract healthcare contact days for EARLY time windows only.

## DEFINITIONS
""" + BASE_DEFINITIONS + """

## TASK: Extract counts for these windows ONLY:
- screening: All pre-randomization/pre-treatment visits
- 1_month: Day 1 through Day 30 after treatment start
- 3_months: Day 1 through Day 90

## EXTRACTION RULES
1. Identify all treatment arms (Arm A, Arm B)
2. Map cycle structure to calendar days
3. For grouped columns like "C4-C12", expand to individual cycles
4. Count unique visit days per arm
5. Handle arm-specific visits (X^A = Arm A only)

## OUTPUT FORMAT
Return ONLY valid JSON:
```json
[
  {
    "arm_name": "Arm A (Treatment Name)",
    "intervention_type": "intervention",
    "healthcare_contact_days": {
      "screening": <integer>,
      "1_month": <integer>,
      "3_months": <integer>
    }
  },
  {
    "arm_name": "Arm B (Control Name)",
    "intervention_type": "control",
    "healthcare_contact_days": {
      "screening": <integer>,
      "1_month": <integer>,
      "3_months": <integer>
    }
  }
]
```
"""

PROMPT_LATE_WINDOWS = """
You are an expert clinical trial protocol analyst. Extract healthcare contact days for LATE time windows only.

## DEFINITIONS
""" + BASE_DEFINITIONS + """

## TASK: Extract CUMULATIVE counts for these windows:
- 6_months: Day 1 through Day 180 (cumulative from start)
- 9_months: Day 1 through Day 270 (cumulative from start)
- 12_months: Day 1 through Day 365 (cumulative from start)

IMPORTANT: These are CUMULATIVE counts from Day 1, not incremental.

## EXTRACTION RULES
1. Identify all treatment arms (Arm A, Arm B)
2. Map ALL cycles to calendar days (Cycle N starts at Day (N-1)*cycle_length + 1)
3. CRITICAL: Grouped columns like "C4-C12" represent MULTIPLE cycles - you must count visits for EACH cycle
4. Include: Screening visits, Treatment visits, EOT visit, AND Follow-up visits (M9 FU, M12 FU)
5. Handle arm-specific visits (X^A = Arm A only)

## OUTPUT FORMAT
Return ONLY valid JSON:
```json
[
  {
    "arm_name": "Arm A (Treatment Name)",
    "intervention_type": "intervention",
    "healthcare_contact_days": {
      "6_months": <integer>,
      "9_months": <integer>,
      "12_months": <integer>
    }
  },
  {
    "arm_name": "Arm B (Control Name)",
    "intervention_type": "control",
    "healthcare_contact_days": {
      "6_months": <integer>,
      "9_months": <integer>,
      "12_months": <integer>
    }
  }
]
```
"""

# Agent 2: Probabilistic with OPTIMIZED PROMPT (legend-aware)
PROMPT_OPTIMIZED = """
You are an expert clinical trial protocol analyst extracting healthcare contact days from a Schedule of Assessments (SoA).

## CRITICAL: READ THE LEGEND FIRST

The LEGEND section (usually below the table) contains the authoritative visit pattern for each arm.
Example: "Arm A: Visits on Days 1, 8, 15 of each 28-day cycle"

This legend pattern applies to ALL cycles, including those shown as grouped columns (e.g., "C4-C12").
DO NOT rely solely on table columns - they may be abbreviated for space.

## EXTRACTION PROCESS

### Step 1: Extract from Legend
Find the visit pattern for each arm:
- Arm A (intervention): Which days per cycle? (e.g., D1, D8, D15)
- Arm B (control): Which days per cycle? (e.g., D1, D15)
- Cycle length in days (typically 21 or 28)
- Treatment duration in months

### Step 2: Calculate Total Cycles
Total cycles = (treatment_months × 30) / cycle_length_days
Example: 12 months with 28-day cycles = 13 cycles

### Step 3: Count Visits per Cycle Pattern
For each arm, apply the legend's visit pattern to EVERY cycle:
- If legend says "D1, D8, D15" → 3 visits per cycle
- If legend says "D1, D15" → 2 visits per cycle

### Step 4: Map to Calendar Days and Count per Window
Convert cycle visits to calendar days:
- C1D1 = Day 1, C1D8 = Day 8, C1D15 = Day 15
- C2D1 = Day 29, C2D8 = Day 36, C2D15 = Day 43 (for 28-day cycles)
- Continue for all cycles...

Then count cumulative visits:
- screening: Pre-treatment visits (usually 1-2 days)
- 1_month: All visits from Day 1 through Day 30
- 3_months: All visits from Day 1 through Day 90
- 6_months: All visits from Day 1 through Day 180
- 9_months: All visits from Day 1 through Day 270
- 12_months: All visits from Day 1 through Day 365

### Step 5: Add Special Visits
Don't forget:
- Screening visits (check table, usually 1-2 days)
- EOT (End of Treatment) visit
- Follow-up visits: M9 FU, M12 FU columns

## VALIDATION
Before outputting, verify:
- 12_months >= 9_months >= 6_months >= 3_months >= 1_month (cumulative property)
- Visit counts match: (cycles × visits_per_cycle) + screening + EOT + followups

## OUTPUT FORMAT
Return ONLY valid JSON:
```json
[
  {
    "arm_name": "Arm A (Treatment Name)",
    "intervention_type": "intervention",
    "healthcare_contact_days": {
      "screening": <integer>,
      "1_month": <integer>,
      "3_months": <integer>,
      "6_months": <integer>,
      "9_months": <integer>,
      "12_months": <integer>
    },
    "calculation_notes": {
      "legend_pattern": "D1, D8, D15 per cycle",
      "cycle_length": 28,
      "total_cycles": 13,
      "visits_per_cycle": 3
    }
  },
  {
    "arm_name": "Arm B (Control Name)",
    "intervention_type": "control",
    "healthcare_contact_days": {...},
    "calculation_notes": {...}
  }
]
```

NOW ANALYZE THE SCHEDULE OF ASSESSMENTS.
"""

# Agent 3: Chain of Thought
PROMPT_COT = """
You are an expert clinical trial protocol analyst. You MUST show your work by enumerating every cycle before counting.

## DEFINITIONS
""" + BASE_DEFINITIONS + """

**Time Windows** (cumulative from Day 1):
- screening: Pre-treatment visits
- 1_month: Day 1-30
- 3_months: Day 1-90
- 6_months: Day 1-180
- 9_months: Day 1-270
- 12_months: Day 1-365

## MANDATORY STEP-BY-STEP PROCESS

### Step 1: Extract Schedule Parameters
Identify: cycle_length, treatment_duration_months, visit_days_per_cycle for each arm

### Step 2: Enumerate ALL Cycles Explicitly
You MUST list every single cycle with its day range. Example for 28-day cycles over 12 months:
- C1: Days 1-28, visits on D1(=1), D15(=15)
- C2: Days 29-56, visits on D1(=29), D15(=43)
- C3: Days 57-84, visits on D1(=57), D15(=71)
- C4: Days 85-112, visits on D1(=85), D15(=99)
... continue for ALL cycles

### Step 3: Count Visits per Window
Sum all unique visit days falling within each window's range.

### Step 4: Add Special Visits
+ Screening visits (usually 1-2 days)
+ EOT visit (1 day)
+ Follow-up visits at M9 and M12

## OUTPUT FORMAT
Return JSON with your enumeration in extraction_notes:
```json
[
  {
    "arm_name": "Arm A (Treatment Name)",
    "intervention_type": "intervention",
    "healthcare_contact_days": {
      "screening": <integer>,
      "1_month": <integer>,
      "3_months": <integer>,
      "6_months": <integer>,
      "9_months": <integer>,
      "12_months": <integer>
    },
    "extraction_notes": {
      "cycle_length_days": <integer>,
      "total_cycles": <integer>,
      "cycle_enumeration": "C1(1-28):D1=1,D15=15; C2(29-56):D1=29,D15=43; ...",
      "visit_count_verification": "screening:2 + treatment:X + EOT:1 + followup:2 = total"
    }
  }
]
```
"""

# Agent 4: Bidirectional Prompts
PROMPT_FORWARD = """
You are an expert clinical trial protocol analyst. Extract healthcare contact days reading FORWARD (chronologically).

## APPROACH: Start from screening and count forward through time

## DEFINITIONS
""" + BASE_DEFINITIONS + """

**Time Windows** (cumulative):
- screening: Pre-treatment (start here)
- 1_month: Day 1-30
- 3_months: Day 1-90
- 6_months: Day 1-180
- 9_months: Day 1-270
- 12_months: Day 1-365 (end here)

## EXTRACTION PROCESS (FORWARD)
1. Count screening visits first
2. Add C1 visits (Days 1-cycle_length)
3. Continue adding subsequent cycles chronologically
4. Add EOT and follow-up visits at the end

## CRITICAL: Expand grouped columns "C4-C12" into individual cycles

## OUTPUT FORMAT
```json
[
  {
    "arm_name": "Arm A",
    "intervention_type": "intervention",
    "healthcare_contact_days": {
      "screening": <int>, "1_month": <int>, "3_months": <int>,
      "6_months": <int>, "9_months": <int>, "12_months": <int>
    }
  },
  {"arm_name": "Arm B", "intervention_type": "control", "healthcare_contact_days": {...}}
]
```
"""

PROMPT_BACKWARD = """
You are an expert clinical trial protocol analyst. Extract healthcare contact days reading BACKWARD (reverse chronologically).

## APPROACH: Start from 12 months and count backward to verify

## DEFINITIONS
""" + BASE_DEFINITIONS + """

**Time Windows** (cumulative - work backward):
- 12_months: Day 1-365 (start here - count ALL visits in entire study)
- 9_months: Day 1-270
- 6_months: Day 1-180
- 3_months: Day 1-90
- 1_month: Day 1-30
- screening: Pre-treatment (end here)

## EXTRACTION PROCESS (BACKWARD)
1. First, calculate TOTAL visits for 12_months:
   - Count all screening visits
   - Count all treatment cycle visits (expand "C4-C12" to individual cycles)
   - Count EOT visit
   - Count M9 FU and M12 FU visits
2. Then subtract visits that occur AFTER each window boundary:
   - 9_months = 12_months - (visits from Day 271-365)
   - 6_months = 9_months - (visits from Day 181-270)
   - etc.

## CRITICAL: For grouped columns like "C4-C12", count EACH cycle individually

## OUTPUT FORMAT
```json
[
  {
    "arm_name": "Arm A",
    "intervention_type": "intervention", 
    "healthcare_contact_days": {
      "screening": <int>, "1_month": <int>, "3_months": <int>,
      "6_months": <int>, "9_months": <int>, "12_months": <int>
    }
  },
  {"arm_name": "Arm B", "intervention_type": "control", "healthcare_contact_days": {...}}
]
```
"""


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def load_ground_truth(filepath: str) -> Dict[str, Dict[str, Dict[str, int]]]:
    """Load ground truth CSV."""
    ground_truth = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            schedule_id = row['schedule_id']
            arm = row['arm']
            if schedule_id not in ground_truth:
                ground_truth[schedule_id] = {}
            ground_truth[schedule_id][arm] = {
                'screening': int(row['screening_days']),
                '1_month': int(row['month1_days']),
                '3_months': int(row['month3_days']),
                '6_months': int(row['month6_days']),
                '9_months': int(row['month9_days']),
                '12_months': int(row['month12_days']),
            }
    return ground_truth


def extract_schedule_id(filename: str) -> str:
    """Extract schedule ID from filename."""
    match = re.search(r'synthetic_schedule_(\d+)', filename)
    return match.group(1) if match else filename


def parse_json_response(response_text: str) -> List[Dict[str, Any]]:
    """Parse JSON from response."""
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_match = re.search(r'\[\s*\{[\s\S]*\}\s*\]', response_text)
        if json_match:
            json_str = json_match.group(0)
        else:
            return []
    try:
        parsed = json.loads(json_str)
        return parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        return []


def map_arm_to_letter(arm_name: str, intervention_type: str) -> str:
    """Map arm name to A/B."""
    if 'intervention' in intervention_type.lower():
        return 'A'
    return 'B'


def setup_client() -> genai.Client:
    """Initialize Gemini client."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not set")
        exit(1)
    return genai.Client(api_key=api_key)


def upload_pdf(client: genai.Client, pdf_path: str):
    """Upload PDF and return file reference."""
    return client.files.upload(file=pdf_path)


def call_gemini(client: genai.Client, uploaded_file, prompt: str, temperature: float = 0.1) -> str:
    """Make a single Gemini API call."""
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_uri(file_uri=uploaded_file.uri, mime_type="application/pdf"),
                types.Part.from_text(text=prompt),
            ],
        ),
    ]
    config = types.GenerateContentConfig(temperature=temperature)
    
    for attempt in range(3):
        try:
            response = client.models.generate_content(model=MODEL, contents=contents, config=config)
            return response.text
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                raise e
    return ""


# ============================================================================
# AGENT IMPLEMENTATIONS
# ============================================================================

def agent_baseline(client: genai.Client, pdf_path: str, uploaded_file) -> Dict[str, Any]:
    """Baseline: Single pass with standard prompt."""
    from test_extraction import EXTRACTION_PROMPT
    response = call_gemini(client, uploaded_file, EXTRACTION_PROMPT)
    arms = parse_json_response(response)
    return {'arms': arms, 'api_calls': 1}


def agent_split_windows(client: genai.Client, pdf_path: str, uploaded_file) -> Dict[str, Any]:
    """Agent 1: Split into early and late window extractions."""
    # Extract early windows
    early_response = call_gemini(client, uploaded_file, PROMPT_EARLY_WINDOWS)
    early_arms = parse_json_response(early_response)
    
    time.sleep(1)  # Rate limiting
    
    # Extract late windows
    late_response = call_gemini(client, uploaded_file, PROMPT_LATE_WINDOWS)
    late_arms = parse_json_response(late_response)
    
    # Merge results
    merged_arms = []
    for early_arm in early_arms:
        arm_name = early_arm.get('arm_name', '')
        intervention_type = early_arm.get('intervention_type', '')
        
        # Find matching late arm
        late_arm = None
        for la in late_arms:
            if map_arm_to_letter(la.get('arm_name', ''), la.get('intervention_type', '')) == \
               map_arm_to_letter(arm_name, intervention_type):
                late_arm = la
                break
        
        merged_days = early_arm.get('healthcare_contact_days', {}).copy()
        if late_arm:
            merged_days.update(late_arm.get('healthcare_contact_days', {}))
        
        merged_arms.append({
            'arm_name': arm_name,
            'intervention_type': intervention_type,
            'healthcare_contact_days': merged_days
        })
    
    return {'arms': merged_arms, 'api_calls': 2}


def agent_probabilistic(client: genai.Client, pdf_path: str, uploaded_file, n_samples: int = 5) -> Dict[str, Any]:
    """Agent 2: Multi-sample with probabilistic aggregation using optimized legend-aware prompt."""
    samples = []
    
    for i in range(n_samples):
        # Use temperature 0.4 for controlled variation
        response = call_gemini(client, uploaded_file, PROMPT_OPTIMIZED, temperature=0.4)
        arms = parse_json_response(response)
        samples.append(arms)
        if i < n_samples - 1:
            time.sleep(0.5)
    
    # Aggregate by arm
    arm_samples = {'A': [], 'B': []}
    for sample in samples:
        for arm in sample:
            letter = map_arm_to_letter(arm.get('arm_name', ''), arm.get('intervention_type', ''))
            arm_samples[letter].append(arm)
    
    # Compute median, IQR, and confidence for each arm
    aggregated_arms = []
    for letter in ['A', 'B']:
        if not arm_samples[letter]:
            continue
        
        # Get first arm for metadata
        first_arm = arm_samples[letter][0]
        aggregated_days = {}
        stats_per_window = {}
        
        for window in TIME_WINDOWS:
            values = []
            for arm in arm_samples[letter]:
                days = arm.get('healthcare_contact_days', {})
                if window in days:
                    val = days[window]
                    if isinstance(val, int):
                        values.append(val)
            
            if values:
                sorted_vals = sorted(values)
                median_val = int(statistics.median(values))
                
                # Calculate IQR (Q1 and Q3)
                n = len(sorted_vals)
                q1_idx = n // 4
                q3_idx = (3 * n) // 4
                q1 = sorted_vals[q1_idx] if n > 1 else sorted_vals[0]
                q3 = sorted_vals[q3_idx] if n > 1 else sorted_vals[0]
                iqr = q3 - q1
                
                aggregated_days[window] = median_val
                stats_per_window[window] = {
                    'median': median_val,
                    'q1': q1,
                    'q3': q3,
                    'iqr': iqr,
                    'min': min(values),
                    'max': max(values),
                    'samples': values,
                    'agreement': max(Counter(values).values()) / len(values)
                }
            else:
                aggregated_days[window] = 0
                stats_per_window[window] = {'median': 0, 'iqr': 0, 'samples': []}
        
        aggregated_arms.append({
            'arm_name': first_arm.get('arm_name', f'Arm {letter}'),
            'intervention_type': first_arm.get('intervention_type', 'intervention' if letter == 'A' else 'control'),
            'healthcare_contact_days': aggregated_days,
            'statistics': stats_per_window,
            'n_samples': n_samples
        })
    
    return {'arms': aggregated_arms, 'api_calls': n_samples}


def agent_cot(client: genai.Client, pdf_path: str, uploaded_file) -> Dict[str, Any]:
    """Agent 3: Chain-of-thought with explicit cycle enumeration."""
    response = call_gemini(client, uploaded_file, PROMPT_COT)
    arms = parse_json_response(response)
    return {'arms': arms, 'api_calls': 1}


def agent_bidirectional(client: genai.Client, pdf_path: str, uploaded_file) -> Dict[str, Any]:
    """Agent 4: Bidirectional extraction (forward + backward)."""
    # Forward pass
    forward_response = call_gemini(client, uploaded_file, PROMPT_FORWARD)
    forward_arms = parse_json_response(forward_response)
    
    time.sleep(1)
    
    # Backward pass
    backward_response = call_gemini(client, uploaded_file, PROMPT_BACKWARD)
    backward_arms = parse_json_response(backward_response)
    
    # Reconcile: take max for each window (fixes undercounting)
    reconciled_arms = []
    for fwd_arm in forward_arms:
        letter = map_arm_to_letter(fwd_arm.get('arm_name', ''), fwd_arm.get('intervention_type', ''))
        
        # Find matching backward arm
        bwd_arm = None
        for ba in backward_arms:
            if map_arm_to_letter(ba.get('arm_name', ''), ba.get('intervention_type', '')) == letter:
                bwd_arm = ba
                break
        
        fwd_days = fwd_arm.get('healthcare_contact_days', {})
        bwd_days = bwd_arm.get('healthcare_contact_days', {}) if bwd_arm else {}
        
        reconciled_days = {}
        flags = []
        
        for window in TIME_WINDOWS:
            fwd_val = fwd_days.get(window, 0)
            bwd_val = bwd_days.get(window, 0)
            
            if isinstance(fwd_val, str):
                fwd_val = int(fwd_val) if fwd_val.isdigit() else 0
            if isinstance(bwd_val, str):
                bwd_val = int(bwd_val) if bwd_val.isdigit() else 0
            
            if fwd_val == bwd_val:
                reconciled_days[window] = fwd_val
            else:
                # Take max to fix undercounting
                reconciled_days[window] = max(fwd_val, bwd_val)
                flags.append(f"{window}: fwd={fwd_val}, bwd={bwd_val}")
        
        reconciled_arms.append({
            'arm_name': fwd_arm.get('arm_name', f'Arm {letter}'),
            'intervention_type': fwd_arm.get('intervention_type', ''),
            'healthcare_contact_days': reconciled_days,
            'disagreements': flags
        })
    
    return {'arms': reconciled_arms, 'api_calls': 2}


# ============================================================================
# EVALUATION
# ============================================================================

def evaluate_agent(results: List[Dict], ground_truth: Dict) -> Dict[str, Any]:
    """Calculate metrics for an agent's results."""
    total = 0
    correct = 0
    within_3 = 0
    errors = []
    
    for result in results:
        schedule_id = result['schedule_id']
        if schedule_id not in ground_truth:
            continue
        
        for arm in result.get('arms', []):
            letter = map_arm_to_letter(arm.get('arm_name', ''), arm.get('intervention_type', ''))
            if letter not in ground_truth[schedule_id]:
                continue
            
            gt_arm = ground_truth[schedule_id][letter]
            ext_days = arm.get('healthcare_contact_days', {})
            
            for window in TIME_WINDOWS:
                gt_val = gt_arm.get(window, 0)
                ext_val = ext_days.get(window, 0)
                if isinstance(ext_val, str):
                    ext_val = int(ext_val) if ext_val.isdigit() else 0
                
                total += 1
                diff = abs(ext_val - gt_val)
                errors.append(diff)
                
                if ext_val == gt_val:
                    correct += 1
                    within_3 += 1
                elif diff <= 3:
                    within_3 += 1
    
    return {
        'exact_accuracy': correct / total if total > 0 else 0,
        'clinical_accuracy': within_3 / total if total > 0 else 0,
        'mae': sum(errors) / len(errors) if errors else 0,
        'total': total,
        'correct': correct,
        'within_3': within_3
    }


# ============================================================================
# MAIN
# ============================================================================

def main():
    import sys
    
    print("=" * 70)
    print("Multi-Agent Prompt Optimization Comparison")
    print("=" * 70)
    
    # Setup
    client = setup_client()
    ground_truth = load_ground_truth(GROUND_TRUTH_FILE)
    print(f"Loaded ground truth for {len(ground_truth)} schedules")
    
    # Get PDFs
    pdf_folder = Path(SCHEDULES_FOLDER)
    pdf_files = sorted(pdf_folder.glob("*.pdf"))
    
    # Limit
    limit = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 5
    pdf_files = pdf_files[:limit]
    print(f"Processing {len(pdf_files)} PDFs\n")
    
    # Define agents
    agents = {
        'Baseline': agent_baseline,
        'Split Windows': agent_split_windows,
        'Probabilistic': agent_probabilistic,
        'Chain-of-Thought': agent_cot,
        'Bidirectional': agent_bidirectional,
    }
    
    # Run each agent
    all_results = {}
    total_api_calls = {}
    
    for agent_name, agent_fn in agents.items():
        print(f"\n{'='*60}")
        print(f"Running Agent: {agent_name}")
        print('='*60)
        
        agent_results = []
        api_calls = 0
        
        for i, pdf_path in enumerate(pdf_files, 1):
            filename = os.path.basename(pdf_path)
            schedule_id = extract_schedule_id(filename)
            print(f"  [{i}/{len(pdf_files)}] {filename}...", end=" ")
            
            try:
                # Upload once per PDF
                uploaded_file = upload_pdf(client, str(pdf_path))
                
                # Run agent
                if agent_name == 'Baseline':
                    # Import baseline prompt
                    from test_extraction import EXTRACTION_PROMPT
                    response = call_gemini(client, uploaded_file, EXTRACTION_PROMPT)
                    result = {'arms': parse_json_response(response), 'api_calls': 1}
                else:
                    result = agent_fn(client, str(pdf_path), uploaded_file)
                
                result['schedule_id'] = schedule_id
                result['filename'] = filename
                agent_results.append(result)
                api_calls += result.get('api_calls', 1)
                
                # Quick accuracy check
                if schedule_id in ground_truth:
                    matches = 0
                    total = 0
                    for arm in result.get('arms', []):
                        letter = map_arm_to_letter(arm.get('arm_name', ''), arm.get('intervention_type', ''))
                        if letter in ground_truth[schedule_id]:
                            for window in TIME_WINDOWS:
                                ext = arm.get('healthcare_contact_days', {}).get(window, 0)
                                gt = ground_truth[schedule_id][letter].get(window, 0)
                                if ext == gt:
                                    matches += 1
                                total += 1
                    print(f"✓ {matches}/{total} exact")
                else:
                    print("✓")
                    
            except Exception as e:
                print(f"✗ Error: {e}")
            
            time.sleep(1)  # Rate limiting between PDFs
        
        all_results[agent_name] = agent_results
        total_api_calls[agent_name] = api_calls
    
    # Evaluate all agents
    print("\n" + "=" * 70)
    print("COMPARISON RESULTS")
    print("=" * 70)
    
    print(f"\n{'Agent':<20} {'Exact Acc':>12} {'Clinical':>12} {'MAE':>10} {'API Calls':>12}")
    print("-" * 70)
    
    for agent_name, results in all_results.items():
        metrics = evaluate_agent(results, ground_truth)
        print(f"{agent_name:<20} {metrics['exact_accuracy']:>11.1%} {metrics['clinical_accuracy']:>11.1%} {metrics['mae']:>9.2f} {total_api_calls[agent_name]:>12}")
    
    # Save detailed results
    with open('agent_comparison_results.json', 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'num_pdfs': len(pdf_files),
            'results': {
                name: {
                    'metrics': evaluate_agent(results, ground_truth),
                    'api_calls': total_api_calls[name]
                }
                for name, results in all_results.items()
            }
        }, f, indent=2)
    
    print(f"\nDetailed results saved to: agent_comparison_results.json")


if __name__ == "__main__":
    main()

