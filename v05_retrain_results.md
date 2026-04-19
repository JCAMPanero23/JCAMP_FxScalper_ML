# Phase 2 Step 1 - v05 Model Retraining Results

**Date:** 2026-04-19T17:02:46.098181
**Status:** PASSED

## Configuration

- CSV: `data/DataCollector_EURUSD_M5_20230101_220446.csv`
- TP multiplier: 4.5×ATR
- Risk/reward: 3.0R on win
- CV folds: 6

## CV Results - LONG Direction

|   fold |   roc_auc |   accuracy |   win_rate |   profit_factor |   expectancy_r |   net_profit_r |   n_trades |
|-------:|----------:|-----------:|-----------:|----------------:|---------------:|---------------:|-----------:|
|      1 |  0.528744 |   0.764671 |     0.2973 |          1.2692 |         0.1892 |             98 |        518 |
|      2 |  0.541122 |   0.783842 |     0.455  |          2.5043 |         0.8199 |            173 |        211 |
|      3 |  0.581913 |   0.782864 |     0.3947 |          1.9565 |         0.5789 |             88 |        152 |
|      4 |  0.56484  |   0.73572  |     0.2578 |          1.0419 |         0.0311 |             17 |        547 |
|      5 |  0.535822 |   0.781299 |     0.3554 |          1.6542 |         0.4217 |             70 |        166 |

### Summary

- Mean ROC-AUC: 0.5505
- Mean Expectancy: +0.408R
- Positive expectancy folds: 5/5
- Gate A: **PASSED**

## Model Output

- Saved to: `models/eurusd_long_v05.joblib`
- Trained on: 204,510 samples

