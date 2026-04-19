# Phase 2 Step 1 - v05 Model Retraining Results

**Date:** 2026-04-19T16:31:24.142875
**Status:** FAILED

## Configuration

- CSV: `data/DataCollector_EURUSD_M5_20230101_220446.csv`
- TP multiplier: 4.5×ATR
- Risk/reward: 3.0R on win
- CV folds: 6

## CV Results - LONG Direction

|   fold |   roc_auc |   accuracy |   win_rate |   profit_factor |   expectancy_r |   net_profit_r |   n_trades |
|-------:|----------:|-----------:|-----------:|----------------:|---------------:|---------------:|-----------:|
|      1 |  0.513097 |   0.648474 |     0.3521 |          1.6305 |         0.4085 |            413 |       1011 |
|      2 |  0.546    |   0.677034 |     0.4338 |          2.2981 |         0.735  |            344 |        468 |
|      3 |  0.566998 |   0.680164 |     0.3839 |          1.8697 |         0.5358 |            247 |        461 |
|      4 |  0.534318 |   0.618349 |     0.3038 |          1.3093 |         0.2153 |            236 |       1096 |
|      5 |  0.514535 |   0.67097  |     0.3367 |          1.5231 |         0.3469 |            204 |        588 |

### Summary

- Mean ROC-AUC: 0.5350
- Mean Expectancy: +0.448R
- Positive expectancy folds: 5/5
- Gate A: **FAILED**

