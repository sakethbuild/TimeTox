# TimeTox Extraction Validation Report

Generated: 2025-12-17 21:16:02

## Overall Metrics

| Metric | Value |
|--------|-------|
| Exact Match Accuracy | 43.3% |
| Clinical Accuracy (±3 days) | 90.0% |
| Mean Absolute Error | 1.72 days |
| Total Comparisons | 60 |
| Exact Matches | 26 |
| Within ±3 Days | 54 |

## Accuracy by Time Window

| Window | Exact Match | Within ±3 Days | Mean Error |
|--------|-------------|----------------|------------|
| screening | 100.0% (10/10) | 100.0% (10/10) | 0.00 |
| 1_month | 100.0% (10/10) | 100.0% (10/10) | 0.00 |
| 3_months | 60.0% (6/10) | 100.0% (10/10) | 1.00 |
| 6_months | 0.0% (0/10) | 80.0% (8/10) | 2.60 |
| 9_months | 0.0% (0/10) | 80.0% (8/10) | 3.20 |
| 12_months | 0.0% (0/10) | 80.0% (8/10) | 4.10 |

## Per-Schedule Results

### Schedule 01

**Arm A (Abemaciclib + Fulvestrant)**

| Window | Ground Truth | Extracted | Diff | Match |
|--------|--------------|-----------|------|-------|
| screening | 2 | 2 | 0 | ✓ |
| 1_month | 4 | 4 | 0 | ✓ |
| 3_months | 11 | 10 | -1 | ✗ |
| 6_months | 22 | 16 | -6 | ✗ |
| 9_months | 33 | 23 | -10 | ✗ |
| 12_months | 43 | 28 | -15 | ✗ |

**Arm B (Fulvestrant)**

| Window | Ground Truth | Extracted | Diff | Match |
|--------|--------------|-----------|------|-------|
| screening | 2 | 2 | 0 | ✓ |
| 1_month | 3 | 3 | 0 | ✓ |
| 3_months | 8 | 7 | -1 | ✗ |
| 6_months | 15 | 10 | -5 | ✗ |
| 9_months | 23 | 13 | -10 | ✗ |
| 12_months | 30 | 16 | -14 | ✗ |

### Schedule 02

**Arm A (Nivolumab + Ipilimumab)**

| Window | Ground Truth | Extracted | Diff | Match |
|--------|--------------|-----------|------|-------|
| screening | 2 | 2 | 0 | ✓ |
| 1_month | 4 | 4 | 0 | ✓ |
| 3_months | 9 | 9 | 0 | ✓ |
| 6_months | 19 | 16 | -3 | ✗ |
| 9_months | 20 | 18 | -2 | ✗ |
| 12_months | 21 | 19 | -2 | ✗ |

**Arm B (Pemetrexed + Cisplatin)**

| Window | Ground Truth | Extracted | Diff | Match |
|--------|--------------|-----------|------|-------|
| screening | 2 | 2 | 0 | ✓ |
| 1_month | 2 | 2 | 0 | ✓ |
| 3_months | 5 | 5 | 0 | ✓ |
| 6_months | 10 | 8 | -2 | ✗ |
| 9_months | 11 | 10 | -1 | ✗ |
| 12_months | 12 | 11 | -1 | ✗ |

### Schedule 03

**Arm A (Durvalumab + Tremelimumab)**

| Window | Ground Truth | Extracted | Diff | Match |
|--------|--------------|-----------|------|-------|
| screening | 2 | 2 | 0 | ✓ |
| 1_month | 3 | 3 | 0 | ✓ |
| 3_months | 7 | 7 | 0 | ✓ |
| 6_months | 14 | 13 | -1 | ✗ |
| 9_months | 22 | 20 | -2 | ✗ |
| 12_months | 23 | 21 | -2 | ✗ |

**Arm B (Sorafenib)**

| Window | Ground Truth | Extracted | Diff | Match |
|--------|--------------|-----------|------|-------|
| screening | 2 | 2 | 0 | ✓ |
| 1_month | 2 | 2 | 0 | ✓ |
| 3_months | 4 | 4 | 0 | ✓ |
| 6_months | 8 | 7 | -1 | ✗ |
| 9_months | 12 | 11 | -1 | ✗ |
| 12_months | 13 | 12 | -1 | ✗ |

### Schedule 04

**Arm A (Total Neoadjuvant Therapy (TNT) + Surgery)**

| Window | Ground Truth | Extracted | Diff | Match |
|--------|--------------|-----------|------|-------|
| screening | 2 | 2 | 0 | ✓ |
| 1_month | 2 | 2 | 0 | ✓ |
| 3_months | 5 | 4 | -1 | ✗ |
| 6_months | 9 | 7 | -2 | ✗ |
| 9_months | 10 | 8 | -2 | ✗ |
| 12_months | 11 | 9 | -2 | ✗ |

**Arm B (Chemoradiation + Surgery)**

| Window | Ground Truth | Extracted | Diff | Match |
|--------|--------------|-----------|------|-------|
| screening | 2 | 2 | 0 | ✓ |
| 1_month | 2 | 2 | 0 | ✓ |
| 3_months | 5 | 4 | -1 | ✗ |
| 6_months | 9 | 7 | -2 | ✗ |
| 9_months | 10 | 8 | -2 | ✗ |
| 12_months | 11 | 9 | -2 | ✗ |

### Schedule 05

**Arm A (Olaparib + Abiraterone)**

| Window | Ground Truth | Extracted | Diff | Match |
|--------|--------------|-----------|------|-------|
| screening | 2 | 2 | 0 | ✓ |
| 1_month | 3 | 3 | 0 | ✓ |
| 3_months | 7 | 7 | 0 | ✓ |
| 6_months | 14 | 12 | -2 | ✗ |
| 9_months | 15 | 14 | -1 | ✗ |
| 12_months | 16 | 15 | -1 | ✗ |

**Arm B (Abiraterone)**

| Window | Ground Truth | Extracted | Diff | Match |
|--------|--------------|-----------|------|-------|
| screening | 2 | 2 | 0 | ✓ |
| 1_month | 2 | 2 | 0 | ✓ |
| 3_months | 4 | 4 | 0 | ✓ |
| 6_months | 8 | 6 | -2 | ✗ |
| 9_months | 9 | 8 | -1 | ✗ |
| 12_months | 10 | 9 | -1 | ✗ |

