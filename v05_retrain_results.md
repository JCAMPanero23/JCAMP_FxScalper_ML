# Phase 2 Step 1 - v05 Model Retraining Results

**Date:** 2026-04-25T12:21:39.508335
**Status:** FAILED

## Configuration

- CSV: `data/DataCollector_EURUSD_M5_20230101_220446.csv`
- TP multiplier: 4.5×ATR
- Risk/reward: 3.0R on win
- CV folds: 6

## CV Results - LONG Direction

|   fold |   roc_auc |   accuracy |   win_rate |   profit_factor |   expectancy_r |   net_profit_r |   n_trades |
|-------:|----------:|-----------:|-----------:|----------------:|---------------:|---------------:|-----------:|
|      1 |  0.528744 |   0.764671 |     0.2474 |          0.9863 |        -0.0103 |             -2 |        194 |
|      2 |  0.541122 |   0.783842 |     0.4605 |          2.561  |         0.8421 |             64 |         76 |
|      3 |  0.581913 |   0.782864 |     0.64   |          5.3333 |         1.56   |             39 |         25 |
|      4 |  0.56484  |   0.73572  |     0.2126 |          0.8102 |        -0.1494 |            -26 |        174 |
|      5 |  0.535822 |   0.781299 |     0.2941 |          1.25   |         0.1765 |              3 |         17 |

### Summary

- Mean ROC-AUC: 0.5505
- Mean Expectancy: +0.484R
- Positive expectancy folds: 3/5
- Gate A: **FAILED**

