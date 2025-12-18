# JSON Output Improvement - Forced Structured Output

## Problem

Previously, we were **only asking** for JSON in the prompt text:
```
Return ONLY JSON:
[
  {
    "arm_name": "...",
    ...
  }
]
```

This relied on the model following instructions, which could lead to:
- Inconsistent formatting
- Code blocks wrapping JSON
- Parsing failures
- Missing fields

## Solution: Force JSON Output

Gemini API supports **structured output** via `response_mime_type`:

```python
config = types.GenerateContentConfig(temperature=temp)
config.response_mime_type = "application/json"  # Forces JSON output
```

## Changes Made

### 1. Updated `call_api()` function
- Added `force_json` parameter
- Sets `response_mime_type = "application/json"` when enabled

### 2. Updated `parse_json()` function
- Tries direct JSON parsing first (for forced JSON mode)
- Falls back to code block extraction (backward compatible)
- More robust error handling

### 3. Applied to Both Stages
- **Stage 1**: Structure extraction now forces JSON
- **Stage 2**: Calculation results now forces JSON

## Benefits

1. **Guaranteed JSON format** - No more parsing failures from markdown/code blocks
2. **Consistent structure** - API enforces valid JSON
3. **Better error handling** - Clearer failures if JSON is malformed
4. **Reduced parsing complexity** - Direct JSON.parse() works

## Backward Compatibility

The `parse_json()` function still handles:
- Direct JSON (from forced mode)
- Code blocks (from old prompt-based mode)
- Raw JSON extraction (fallback)

So existing results still work, but new runs will be more reliable.

## Testing

To verify the improvement:
1. Run a few schedules with the updated code
2. Check that JSON parsing succeeds 100%
3. Verify no code block wrapping in responses
4. Confirm both arms are always extracted

