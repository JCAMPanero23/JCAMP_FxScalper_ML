# Phase 2 Step 1 - v05 Model Retraining Results

**Date:** 2026-04-19T12:52:30.347683
**Status:** FAILED

## Configuration

- CSV: `data/DataCollector_EURUSD_M5_20230101_220446.csv`
- TP multiplier: 4.5×ATR
- Risk/reward: 3.0R on win
- CV folds: 5

## CV Results - LONG Direction

|   fold |   roc_auc |   accuracy |   win_rate |   profit_factor |   expectancy_r |   net_profit_r |   n_trades |
|-------:|----------:|-----------:|-----------:|----------------:|---------------:|---------------:|-----------:|
|      1 |  0.575124 |   0.666993 |     0.3471 |          1.5946 |         0.3882 |            396 |       1020 |
|      2 |  0.565563 |   0.668297 |     0.4175 |          2.1504 |         0.6701 |            260 |        388 |
|      3 |  0.533364 |   0.66683  |     0.3216 |          1.4223 |         0.2865 |            106 |        370 |
|      4 |  0.520393 |   0.651345 |     0.368  |          1.7466 |         0.4719 |            218 |        462 |

### Summary

- Mean ROC-AUC: 0.5486
- Mean Expectancy: +0.454R
- Positive expectancy folds: 4/5
- Gate A: **FAILED**

