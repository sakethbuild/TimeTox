#!/usr/bin/env python3
"""
HTML Parser for Category Ground Truth

Parses synthetic schedule HTML files to extract category-level ground truth.

Categories:
- core_treatment: Drug administration, infusions, treatment procedures
- imaging_diagnostics: CT, MRI, PET, X-ray, ultrasound, ECG, ECHO
- labs: Blood draws, urinalysis, biomarkers
- clinic_visits: Physical exam, vital signs, assessments

Usage:
    python3 experiments/category_breakdown/html_parser.py [num_schedules]
"""

import os
import sys
import json
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from bs4 import BeautifulSoup

# ============================================================================
# CONFIGURATION
# ============================================================================

WINDOWS = ['screening', '1_month', '3_months', '6_months', '9_months', '12_months']
CATEGORIES = ['core_treatment', 'imaging_diagnostics', 'labs', 'clinic_visits']

# Map HTML section names to our categories
CATEGORY_MAPPING = {
    # Core Treatment
    'STUDY TREATMENT': 'core_treatment',
    'TREATMENT': 'core_treatment',
    'DRUG ADMINISTRATION': 'core_treatment',
    
    # Imaging/Diagnostics
    'IMAGING/TUMOR ASSESSMENT': 'imaging_diagnostics',
    'IMAGING': 'imaging_diagnostics',
    'TUMOR ASSESSMENT': 'imaging_diagnostics',
    'CARDIAC ASSESSMENTS': 'imaging_diagnostics',  # ECG, ECHO
    'CARDIAC': 'imaging_diagnostics',
    
    # Labs
    'LABORATORY ASSESSMENTS': 'labs',
    'LABORATORY': 'labs',
    'LABS': 'labs',
    
    # Clinic Visits (everything else)
    'CLINICAL ASSESSMENTS': 'clinic_visits',
    'CLINICAL': 'clinic_visits',
    'SAFETY MONITORING': 'clinic_visits',
    'SAFETY': 'clinic_visits',
    'ADMINISTRATIVE': 'clinic_visits',
    'PATIENT-REPORTED OUTCOMES': 'clinic_visits',
    'PRO': 'clinic_visits',
}

# Default category for unmapped sections
DEFAULT_CATEGORY = 'clinic_visits'


@dataclass
class ColumnInfo:
    """Information about a schedule column."""
    index: int
    header: str
    cycle: Optional[int]
    day: Optional[int]
    is_screening: bool
    is_eot: bool
    is_followup: bool
    followup_month: Optional[int]
    is_arm_a_only: bool
    calendar_day: Optional[int]  # Converted to calendar day


@dataclass 
class AssessmentRow:
    """Information about an assessment row."""
    name: str
    category: str
    marks: Dict[int, str]  # column_index -> mark ('X', 'X^A', 'X^B', '')


def parse_column_header(header_text: str, cycle_length: int = 28) -> ColumnInfo:
    """Parse a column header to extract timing information."""
    header = header_text.strip()
    
    # Check for screening
    if 'screening' in header.lower() or 'scr' in header.lower():
        return ColumnInfo(
            index=0, header=header, cycle=None, day=None,
            is_screening=True, is_eot=False, is_followup=False,
            followup_month=None, is_arm_a_only=False, calendar_day=0
        )
    
    # Check for EOT
    if 'eot' in header.lower() or 'end of treatment' in header.lower():
        return ColumnInfo(
            index=0, header=header, cycle=None, day=None,
            is_screening=False, is_eot=True, is_followup=False,
            followup_month=None, is_arm_a_only=False, calendar_day=None
        )
    
    # Check for follow-up (M9 FU, M12 FU, etc.)
    fu_match = re.search(r'm(\d+)\s*fu', header.lower())
    if fu_match:
        month = int(fu_match.group(1))
        return ColumnInfo(
            index=0, header=header, cycle=None, day=None,
            is_screening=False, is_eot=False, is_followup=True,
            followup_month=month, is_arm_a_only=False, 
            calendar_day=month * 30
        )
    
    # Check for cycle notation (C1D1, C1D8, C2D1, etc.)
    cycle_match = re.search(r'c(\d+)[-]?(\d+)?[d\s]*(\d+)?', header.lower())
    if cycle_match:
        cycle_start = int(cycle_match.group(1))
        cycle_end = int(cycle_match.group(2)) if cycle_match.group(2) else cycle_start
        day = int(cycle_match.group(3)) if cycle_match.group(3) else 1
        
        # Check if arm A only (superscript A)
        is_arm_a = '<sup>a</sup>' in header.lower() or '^a' in header.lower()
        
        # For ranges like C4-C12, we'll handle this specially
        # For now, return the first cycle info
        calendar_day = (cycle_start - 1) * cycle_length + day
        
        return ColumnInfo(
            index=0, header=header, cycle=cycle_start, day=day,
            is_screening=False, is_eot=False, is_followup=False,
            followup_month=None, is_arm_a_only=is_arm_a,
            calendar_day=calendar_day
        )
    
    # Try simple day notation (D1, D8, etc.)
    day_match = re.search(r'd(\d+)', header.lower())
    if day_match:
        day = int(day_match.group(1))
        return ColumnInfo(
            index=0, header=header, cycle=1, day=day,
            is_screening=False, is_eot=False, is_followup=False,
            followup_month=None, is_arm_a_only=False,
            calendar_day=day
        )
    
    # Unknown column type
    return ColumnInfo(
        index=0, header=header, cycle=None, day=None,
        is_screening=False, is_eot=False, is_followup=False,
        followup_month=None, is_arm_a_only=False, calendar_day=None
    )


def get_cycle_length_from_html(soup: BeautifulSoup) -> int:
    """Try to extract cycle length from legend or protocol info."""
    # Look for legend div
    legend = soup.find('div', class_='legend')
    if legend:
        text = legend.get_text().lower()
        # Look for "X-day cycle" pattern
        match = re.search(r'(\d+)[-\s]*day\s+cycle', text)
        if match:
            return int(match.group(1))
    
    # Default to 28-day cycles
    return 28


def get_treatment_duration_from_html(soup: BeautifulSoup) -> int:
    """Try to extract treatment duration in months from HTML."""
    legend = soup.find('div', class_='legend')
    if legend:
        text = legend.get_text().lower()
        # Look for "X months" pattern
        match = re.search(r'for\s+(\d+)\s+months?', text)
        if match:
            return int(match.group(1))
    return 12  # Default


def parse_schedule_html(html_path: str) -> Dict:
    """
    Parse a schedule HTML file and extract category breakdown.
    
    Returns dict with structure:
    {
        "A": {
            "total": {"screening": N, "1_month": N, ...},
            "category_breakdown": {
                "core_treatment": {"screening": N, ...},
                "imaging_diagnostics": {...},
                "labs": {...},
                "clinic_visits": {...}
            }
        },
        "B": {...}
    }
    """
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    
    cycle_length = get_cycle_length_from_html(soup)
    treatment_months = get_treatment_duration_from_html(soup)
    
    # Find the main table
    table = soup.find('table')
    if not table:
        raise ValueError(f"No table found in {html_path}")
    
    # Parse headers to get column info
    headers = []
    header_row = table.find('thead')
    if header_row:
        th_cells = header_row.find_all('th')
    else:
        # Try first row
        first_row = table.find('tr')
        th_cells = first_row.find_all(['th', 'td']) if first_row else []
    
    for i, th in enumerate(th_cells):
        header_text = th.get_text(separator=' ', strip=True)
        # Also check for superscript markers in raw HTML
        header_html = str(th)
        if '<sup>' in header_html.lower():
            sup = th.find('sup')
            if sup and sup.get_text().strip().upper() == 'A':
                header_text += '^A'
        
        col_info = parse_column_header(header_text, cycle_length)
        col_info.index = i
        headers.append(col_info)
    
    # Parse body rows
    current_category = DEFAULT_CATEGORY
    rows: List[AssessmentRow] = []
    
    tbody = table.find('tbody') or table
    for tr in tbody.find_all('tr'):
        # Check if this is a category row
        if 'category-row' in tr.get('class', []):
            category_text = tr.get_text(strip=True).upper()
            # Map to our categories
            current_category = DEFAULT_CATEGORY
            for pattern, cat in CATEGORY_MAPPING.items():
                if pattern in category_text:
                    current_category = cat
                    break
            continue
        
        # Regular assessment row
        cells = tr.find_all(['td', 'th'])
        if not cells:
            continue
        
        # First cell is assessment name
        assessment_name = cells[0].get_text(strip=True)
        if not assessment_name:
            continue
        
        # Parse marks for each column
        marks = {}
        for i, cell in enumerate(cells[1:], start=1):
            cell_text = cell.get_text(strip=True)
            cell_html = str(cell)
            
            if 'X' in cell_text.upper():
                # Check for arm-specific marks
                if '<sup>' in cell_html.lower():
                    sup = cell.find('sup')
                    if sup:
                        sup_text = sup.get_text().strip().upper()
                        if sup_text == 'A':
                            marks[i] = 'X^A'
                        elif sup_text == 'B':
                            marks[i] = 'X^B'
                        else:
                            marks[i] = 'X'
                    else:
                        marks[i] = 'X'
                else:
                    marks[i] = 'X'
        
        if marks:  # Only add rows that have at least one mark
            rows.append(AssessmentRow(
                name=assessment_name,
                category=current_category,
                marks=marks
            ))
    
    # Now calculate visit days per arm per category
    # We need to track which calendar days have visits for each arm and category
    arm_a_visits: Dict[str, set] = {cat: set() for cat in CATEGORIES}
    arm_b_visits: Dict[str, set] = {cat: set() for cat in CATEGORIES}
    
    # Process each row
    for row in rows:
        category = row.category
        
        for col_idx, mark in row.marks.items():
            if col_idx >= len(headers):
                continue
            
            col = headers[col_idx]
            
            # Determine calendar day
            if col.is_screening:
                calendar_day = 0  # Screening is before day 1
            elif col.calendar_day is not None:
                calendar_day = col.calendar_day
            else:
                continue  # Unknown timing
            
            # Handle cycle ranges (e.g., C4-C12)
            # Check if header indicates a range
            range_match = re.search(r'c(\d+)-c?(\d+)', col.header.lower())
            if range_match:
                start_cycle = int(range_match.group(1))
                end_cycle = int(range_match.group(2))
                # Extract day from header
                day_match = re.search(r'd(\d+)', col.header.lower())
                day = int(day_match.group(1)) if day_match else 1
                
                # Generate all calendar days in range
                for c in range(start_cycle, end_cycle + 1):
                    cal_day = (c - 1) * cycle_length + day
                    
                    # Determine which arms this applies to
                    if mark == 'X^A' or col.is_arm_a_only:
                        arm_a_visits[category].add(cal_day)
                    elif mark == 'X^B':
                        arm_b_visits[category].add(cal_day)
                    else:  # Regular X - applies to both arms
                        arm_a_visits[category].add(cal_day)
                        arm_b_visits[category].add(cal_day)
            else:
                # Single visit day
                if mark == 'X^A' or col.is_arm_a_only:
                    arm_a_visits[category].add(calendar_day)
                elif mark == 'X^B':
                    arm_b_visits[category].add(calendar_day)
                else:  # Regular X
                    arm_a_visits[category].add(calendar_day)
                    arm_b_visits[category].add(calendar_day)
    
    # Convert to cumulative counts per window
    def count_visits_per_window(visits: Dict[str, set]) -> Dict[str, Dict[str, int]]:
        """Convert visit sets to cumulative counts per window."""
        window_limits = {
            'screening': 0,
            '1_month': 30,
            '3_months': 90,
            '6_months': 180,
            '9_months': 270,
            '12_months': 365,
        }
        
        result = {}
        for category in CATEGORIES:
            cat_visits = visits.get(category, set())
            result[category] = {}
            
            for window, limit in window_limits.items():
                if window == 'screening':
                    # Only count day 0 (screening)
                    count = 1 if 0 in cat_visits else 0
                else:
                    # Count all visits up to and including the limit
                    # Plus screening visits
                    screening_count = 1 if 0 in cat_visits else 0
                    treatment_count = sum(1 for d in cat_visits if 1 <= d <= limit)
                    count = screening_count + treatment_count
                
                result[category][window] = count
        
        return result
    
    arm_a_breakdown = count_visits_per_window(arm_a_visits)
    arm_b_breakdown = count_visits_per_window(arm_b_visits)
    
    # Calculate totals per window
    def calc_total(breakdown: Dict[str, Dict[str, int]]) -> Dict[str, int]:
        """Calculate total visits per window from category breakdown."""
        totals = {}
        # We need to count unique days, not sum categories
        # Because a day with labs AND treatment is still 1 visit
        # But for now, we'll return the breakdown and let the caller handle dedup
        for window in WINDOWS:
            # Sum across categories (this overcounts if multiple categories on same day)
            # For ground truth, we'll handle this differently
            totals[window] = sum(breakdown[cat][window] for cat in CATEGORIES)
        return totals
    
    # Actually, for unique day counting, we need to merge all visit days
    def calc_total_unique(visits: Dict[str, set]) -> Dict[str, int]:
        """Calculate total unique visit days per window."""
        all_days = set()
        for cat_days in visits.values():
            all_days.update(cat_days)
        
        window_limits = {
            'screening': 0,
            '1_month': 30,
            '3_months': 90,
            '6_months': 180,
            '9_months': 270,
            '12_months': 365,
        }
        
        totals = {}
        for window, limit in window_limits.items():
            if window == 'screening':
                count = 1 if 0 in all_days else 0
            else:
                screening_count = 1 if 0 in all_days else 0
                treatment_count = sum(1 for d in all_days if 1 <= d <= limit)
                count = screening_count + treatment_count
            totals[window] = count
        
        return totals
    
    return {
        'cycle_length': cycle_length,
        'treatment_months': treatment_months,
        'A': {
            'total': calc_total_unique(arm_a_visits),
            'category_breakdown': arm_a_breakdown,
        },
        'B': {
            'total': calc_total_unique(arm_b_visits),
            'category_breakdown': arm_b_breakdown,
        }
    }


def generate_category_ground_truth(
    schedules_dir: str, 
    schedule_ids: List[str],
    output_path: str = None
) -> Dict:
    """
    Generate category ground truth for specified schedules.
    
    Args:
        schedules_dir: Path to synthetic_schedules directory
        schedule_ids: List of schedule IDs (e.g., ['01', '02', ...])
        output_path: Optional path to save JSON output
        
    Returns:
        Dict with ground truth for all schedules
    """
    ground_truth = {}
    
    for sid in schedule_ids:
        # Find HTML file
        html_files = [f for f in os.listdir(schedules_dir)
                      if f.startswith(f'synthetic_schedule_{sid}') and f.endswith('.html')]
        
        if not html_files:
            print(f"⚠️ No HTML found for schedule {sid}")
            continue
        
        html_path = os.path.join(schedules_dir, html_files[0])
        
        try:
            result = parse_schedule_html(html_path)
            ground_truth[sid] = result
            print(f"✓ Parsed schedule {sid}")
        except Exception as e:
            print(f"✗ Error parsing schedule {sid}: {e}")
    
    if output_path:
        with open(output_path, 'w') as f:
            json.dump(ground_truth, f, indent=2)
        print(f"\n💾 Saved ground truth to: {output_path}")
    
    return ground_truth


def main():
    """Parse schedules and generate category ground truth."""
    num_schedules = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    
    schedules_dir = os.path.join(
        os.path.dirname(__file__), '..', '..', 'synthetic_schedules'
    )
    
    schedule_ids = [f"{i:02d}" for i in range(1, num_schedules + 1)]
    
    output_path = os.path.join(schedules_dir, 'category_ground_truth.json')
    
    print("=" * 60)
    print("Generating Category Ground Truth")
    print("=" * 60)
    print(f"Schedules: {schedule_ids}")
    print()
    
    ground_truth = generate_category_ground_truth(
        schedules_dir, schedule_ids, output_path
    )
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for sid, data in ground_truth.items():
        print(f"\nSchedule {sid}:")
        for arm in ['A', 'B']:
            arm_data = data.get(arm, {})
            total = arm_data.get('total', {})
            print(f"  Arm {arm}: {total.get('12_months', '?')} total visits at 12 months")
            breakdown = arm_data.get('category_breakdown', {})
            for cat in CATEGORIES:
                cat_data = breakdown.get(cat, {})
                print(f"    {cat}: {cat_data.get('12_months', 0)}")


if __name__ == "__main__":
    main()

