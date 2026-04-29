# Phase 2 Step 1 (SHORT) - v05 Model Retraining Results

**Date:** 2026-04-25T12:11:56.568853
**Status:** FAILED

## Configuration

- CSV: `data/DataCollector_EURUSD_M5_20230101_220446.csv`
- TP multiplier: 4.5xATR
- Risk/reward: 3.0R on win
- CV folds: 6
- Thresholds tested: [0.6, 0.65, 0.7]

## Threshold Comparison

| Threshold | Mean AUC | Mean Exp (R) | Positive Folds | Worst Fold Exp | Worst Fold Net R |
|---:|---:|---:|---:|---:|---:|
| 0.6 | 0.5378 | +0.063 | 3/6 | -0.347 | -124.0 |
| 0.65 | 0.5378 | +0.063 | 3/6 | -0.347 | -124.0 |
| 0.7 | 0.5378 | +0.063 | 3/6 | -0.347 | -124.0 |

## Per-Fold Results - Threshold 0.6

|   fold |   roc_auc |   accuracy |   win_rate |   profit_factor |   expectancy_r |   net_profit_r |   n_trades |
|-------:|----------:|-----------:|-----------:|----------------:|---------------:|---------------:|-----------:|
|      1 |  0.542109 |   0.728482 |     0.1676 |          0.6038 |        -0.3298 |           -124 |        376 |
|      2 |  0.601911 |   0.778756 |     0.3333 |          1.5    |         0.3333 |             95 |        285 |
|      3 |  0.527214 |   0.722027 |     0.2842 |          1.1908 |         0.1366 |             25 |        183 |
|      4 |  0.528755 |   0.735133 |     0.3804 |          1.8421 |         0.5217 |             48 |         92 |
|      5 |  0.489093 |   0.721049 |     0.1633 |          0.5854 |        -0.3469 |           -119 |        343 |

## Per-Fold Results - Threshold 0.65

|   fold |   roc_auc |   accuracy |   win_rate |   profit_factor |   expectancy_r |   net_profit_r |   n_trades |
|-------:|----------:|-----------:|-----------:|----------------:|---------------:|---------------:|-----------:|
|      1 |  0.542109 |   0.728482 |     0.1676 |          0.6038 |        -0.3298 |           -124 |        376 |
|      2 |  0.601911 |   0.778756 |     0.3333 |          1.5    |         0.3333 |             95 |        285 |
|      3 |  0.527214 |   0.722027 |     0.2842 |          1.1908 |         0.1366 |             25 |        183 |
|      4 |  0.528755 |   0.735133 |     0.3804 |          1.8421 |         0.5217 |             48 |         92 |
|      5 |  0.489093 |   0.721049 |     0.1633 |          0.5854 |        -0.3469 |           -119 |        343 |

## Per-Fold Results - Threshold 0.7

|   fold |   roc_auc |   accuracy |   win_rate |   profit_factor |   expectancy_r |   net_profit_r |   n_trades |
|-------:|----------:|-----------:|-----------:|----------------:|---------------:|---------------:|-----------:|
|      1 |  0.542109 |   0.728482 |     0.1676 |          0.6038 |        -0.3298 |           -124 |        376 |
|      2 |  0.601911 |   0.778756 |     0.3333 |          1.5    |         0.3333 |             95 |        285 |
|      3 |  0.527214 |   0.722027 |     0.2842 |          1.1908 |         0.1366 |             25 |        183 |
|      4 |  0.528755 |   0.735133 |     0.3804 |          1.8421 |         0.5217 |             48 |         92 |
|      5 |  0.489093 |   0.721049 |     0.1633 |          0.5854 |        -0.3469 |           -119 |        343 |

## Recommendation

v0.4 features did not lift SHORT to Gate A on 2023 data. Defer SHORT until v0.6 retrain on 2024-2026 data, where the current bearish regime will provide more SHORT-favourable training samples.
