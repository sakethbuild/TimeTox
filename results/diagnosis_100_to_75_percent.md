# Diagnosis: Why 100% → 75% Clinical Accuracy?

## The Mystery

- **First 5 schedules:** 100% clinical accuracy (±3 days)
- **All 20 schedules:** 75% clinical accuracy
- **Question:** What happened?

---

## Root Cause: 7-Day Cycle Protocols

### The Pattern

| Cycle Length | Schedules | Clinical Accuracy | Status |
|--------------|-----------|-------------------|--------|
| **7-day** | 06, 09, 10, 17, 20 | **0.0%** (0/60) | ❌ **ALL FAIL** |
| 21-day | 02, 08, 12 | 100.0% (36/36) | ✅ Perfect |
| 28-day | 01, 03, 04, 05, 07, 11, 13, 14, 16, 18, 19 | 100.0% (132/132) | ✅ Perfect |
| 35-day | 15 | 100.0% (12/12) | ✅ Perfect |

### Why First 5 Were 100%

**Coincidence!** The first 5 schedules (01-05) happened to be:
- Schedule 01: 28-day cycles ✅
- Schedule 02: 21-day cycles ✅
- Schedule 03: 28-day cycles ✅
- Schedule 04: 28-day cycles ✅
- Schedule 05: 28-day cycles ✅

**None of them had 7-day cycles!**

---

## The 7-Day Cycle Bug

All 5 failing schedules (06, 09, 10, 17, 20) show the **exact same error pattern**:

| Window | Ground Truth | Extracted | Error |
|--------|--------------|-----------|-------|
| Screening | 2 | **7** | +5 |
| 1 Month | 5 | **12** | +7 |
| 3 Months | 14 | **20** | +6 |
| 6 Months | 28 | **32** | +4 |
| 9 Months | 29 | **34** | +5 |
| 12 Months | 30 | **35** | +5 |

### Root Cause

The model is **confusing cycle length with screening days**:

```json
{
  "special_visits": {
    "screening_days": 7,  // ❌ WRONG! Should be 2
    ...
  }
}
```

When the cycle length is 7 days, the model incorrectly sets `screening_days: 7` instead of `screening_days: 2`.

This cascades through all calculations:
- Screening window: +5 error
- All cumulative windows: +5 to +7 error (outside ±3 threshold)

---

## Performance Breakdown

### Including 7-Day Cycles (All 20 Schedules)
- **Clinical Accuracy:** 75.0% (180/240)
- **MAE:** 2.02 days

### Excluding 7-Day Cycles (15 Schedules)
- **Clinical Accuracy:** **100.0%** (180/180) ✅
- **MAE:** 0.83 days
- **Exact Match:** 26.7% (48/180)

---

## Why This Happens

### 7-Day Cycle Protocols Are Different

These are **radiation-based protocols** with:
- Weekly treatment visits (7-day cycles)
- Different scheduling patterns
- The model sees "7" in multiple places and gets confused

### The Confusion

When extracting structure, the model sees:
- Cycle length: 7 days
- Screening period: Could be 7 days?
- Model incorrectly infers: `screening_days = cycle_length = 7`

---

## Solution

### Option 1: Fix the Prompt (Recommended)
Add explicit instruction in Stage 1 prompt:
```
IMPORTANT: screening_days is the NUMBER OF DAYS for screening visits,
NOT the cycle length. Screening is typically 1-2 days regardless of cycle length.
```

### Option 2: Post-Processing Rule
Add validation:
```python
if structure['special_visits']['screening_days'] == structure['arms'][0]['cycle_length_days']:
    # Likely confusion - set to default 2
    structure['special_visits']['screening_days'] = 2
```

### Option 3: Special Handling for RT Protocols
Detect 7-day cycles and use specialized extraction logic.

---

## Key Insights

1. **First 5 were lucky** - No 7-day cycles in that sample
2. **7-day cycles are the problem** - All 5 fail identically
3. **Other cycles work perfectly** - 21, 28, 35-day cycles = 100% accuracy
4. **Excluding RT protocols** - Pipeline achieves 100% clinical accuracy

---

## Recommendation

**Fix the Stage 1 prompt** to explicitly distinguish screening days from cycle length. This should resolve all 5 failing schedules and restore 100% clinical accuracy across all 20 schedules.

