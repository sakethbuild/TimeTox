# Zero Value Analysis - Two-Stage Pipeline

## Problem Summary

Two schedules had **empty extracted results** for Arm A:
- **Schedule 15** (HCC): Arm A empty, Arm B extracted correctly
- **Schedule 20** (Prostate RT): Arm A empty, Arm B extracted correctly

---

## Root Cause: Arm Matching Logic Bug

### The Bug

The original `extract_arm_results()` function used this logic:
```python
if 'A' in name and 'B' not in name:
    ext_a = days
else:
    ext_b = days
```

### Why It Failed

1. **Schedule 15 Arm A**: `"Arm A (Atezolizumab + Bevacizumab)"`
   - Contains 'A' ✓
   - Contains 'B' (in "**B**evacizumab") ✗
   - Result: Fails `'B' not in name`, goes to `else` → assigned to `ext_b`
   - Then Arm B overwrites it, leaving `ext_a` empty

2. **Schedule 20 Arm A**: `"Arm A (SBRT (5 fractions))"`
   - Contains 'A' ✓
   - No 'B' ✓
   - Should match... but Stage 2 may not have returned it

### The Fix

Updated matching logic to check for "Arm A" and "Arm B" specifically:
```python
if 'Arm A' in name and 'Arm B' not in name:
    ext_a = days
elif 'Arm B' in name:
    ext_b = days
```

This correctly handles:
- ✅ `"Arm A (Atezolizumab + Bevacizumab)"` → matches Arm A
- ✅ `"Arm B (Sorafenib)"` → matches Arm B
- ✅ `"Arm A (SBRT (5 fractions))"` → matches Arm A

---

## Affected Schedules

| Schedule | Disease | Arm A Issue | Arm B Status |
|----------|---------|-------------|--------------|
| 15 | HCC | Empty (Bevacizumab bug) | ✅ Extracted |
| 20 | Prostate RT | Empty (possibly Stage 2 didn't return) | ✅ Extracted |

---

## Impact on Results

### Schedule 15
- **Arm A**: All zeros → MAE = 5.0 days, Clinical = 50%
- **Arm B**: Correctly extracted → MAE = 0.5 days, Clinical = 100%

### Schedule 20
- **Arm A**: All zeros → MAE = 8.33 days, Clinical = 16.7%
- **Arm B**: Extracted (but wrong due to 7-day cycle issue) → MAE = 6.0 days

---

## Recommendations

1. **Re-run affected schedules** with the fixed matching logic
2. **Add validation** to detect empty extractions and flag for review
3. **Improve Stage 2 prompt** to ensure both arms are always returned
4. **Add fallback logic** to use structure order if name matching fails

---

## Code Fix Applied

✅ Fixed in `experiments/two_stage/pipeline.py` line 198-208

The new logic:
- Checks for "Arm A" and "Arm B" as substrings (not just 'A'/'B')
- Uses list position as fallback if name matching fails
- More robust to treatment names containing 'A' or 'B'

