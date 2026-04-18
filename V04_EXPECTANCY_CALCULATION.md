# URGENT: Calculate v0.4 Trading Expectancy (R-Multiples)

**Priority:** BLOCKING — cannot evaluate Gate A/B/C without this
**Date:** 2026-04-18
**Context:** v0.4 walk-forward CV ran successfully but reported classifier
metrics (accuracy, precision, F1) instead of trading expectancy (R).
The gate criteria require R-multiple expectancy. This task computes it.

---

## The Problem

v0.3 results were reported as:
- Mean expectancy: +0.071R per trade
- Positive folds: 3/5 (folds where expectancy > 0)
- Worst fold expectancy: -0.095R

v0.4 results were reported as:
- Accuracy: 0.675
- Precision: 0.371
- These are CLASSIFICATION metrics, not TRADING metrics

**We need the same format as v0.3 to compare.**

---

## What To Calculate

For each fold, at each threshold (0.55, 0.60, 0.65):

### Per-trade R-multiple assignment

The triple-barrier labels in the CSV tell us what happened:

```python
def assign_r(outcome):
    """Convert triple-barrier outcome to R-multiple.
    
    TP = 3.0 * ATR, SL = 1.5 * ATR
    R-multiple = TP/SL = 3.0/1.5 = 2.0R on win, -1.0R on loss
    Timeout = 0R (no P&L, trade expired)
    """
    if outcome == 'win':
        return 2.0    # TP hit: earned 2R
    elif outcome == 'loss':
        return -1.0   # SL hit: lost 1R
    else:  # timeout
        return 0.0    # Neither hit: flat
```

### Per-fold expectancy

```python
# For each fold's TEST set:
# 1. Get model predictions on test bars
# 2. Filter to bars where p_win > threshold ("traded" bars)
# 3. Look up the actual outcome for each traded bar
# 4. Compute mean R across traded bars = expectancy

# For LONG model:
traded_mask = p_win_long > threshold
traded_outcomes = df_test.loc[traded_mask, 'outcome_long']
r_per_trade = traded_outcomes.map({'win': 2.0, 'loss': -1.0, 'timeout': 0.0})
expectancy = r_per_trade.mean()
net_r = r_per_trade.sum()
n_trades = traded_mask.sum()
win_rate = (traded_outcomes == 'win').mean()
```

### Output format (must match v0.3 for comparison)

For each direction (LONG, SHORT) and threshold (0.55, 0.60, 0.65):

```
| Fold | Trades | Win Rate | Expectancy | Net R  | Status |
|------|--------|----------|------------|--------|--------|
| 1    | 764    | 36.4%    | +0.092R    | +70.3R | ✓      |
| 2    | 313    | 39.9%    | +0.198R    | +62.0R | ✓      |
| ...  | ...    | ...      | ...        | ...    | ...    |
```

Where Status = ✓ if expectancy > 0, ✗ if expectancy < 0.

### Summary format

```
| Threshold | Positive Folds | Mean Exp  | Worst Fold Exp | Avg Trades/Fold |
|-----------|----------------|-----------|----------------|-----------------|
| 0.55      | ?/5            | ?R        | ?R             | ?               |
| 0.60      | ?/5            | ?R        | ?R             | ?               |
| 0.65      | ?/5            | ?R        | ?R             | ?               |
```

---

## Implementation

### Option A: Re-use existing walk-forward code

If the walk-forward script from v0.3 (`phase2_multi_threshold_experiment.py`
or `notebooks/03_walk_forward.ipynb`) already computes expectancy, re-run
it on the v0.4 dataset. Just point it at the new CSV:

```python
DATA_PATH = "data/DataCollector_EURUSD_M5_20230101_220446.csv"  # v0.4
```

Make sure it uses the canonical CV params:
```python
cv = PurgedWalkForward(n_splits=6, test_size=0.15, embargo_bars=48)
```

### Option B: Post-process the existing v0.4 predictions

If you saved per-bar predictions from the v0.4 run, you can compute
expectancy without retraining:

```python
import pandas as pd
import numpy as np

# Load v0.4 fold results (should have predictions + outcomes)
# Adapt paths to wherever the predictions were saved

THRESHOLDS = [0.55, 0.60, 0.65]

for direction in ['long', 'short']:
    outcome_col = f'outcome_{direction}'
    pred_col = f'p_win_{direction}'
    
    print(f"\n{'='*60}")
    print(f"{direction.upper()} MODEL")
    print(f"{'='*60}")
    
    for thr in THRESHOLDS:
        print(f"\nThreshold {thr}:")
        print(f"{'Fold':<6} {'Trades':<8} {'WinRate':<10} {'Expectancy':<12} {'NetR':<10} {'Status'}")
        print("-" * 60)
        
        fold_expectations = []
        
        for fold_num in range(1, 6):
            # Get test set predictions for this fold
            # (adapt this to however your data is structured)
            fold_mask = (df['fold'] == fold_num)
            fold_data = df[fold_mask]
            
            # Filter to "traded" bars
            traded = fold_data[fold_data[pred_col] > thr]
            n_trades = len(traded)
            
            if n_trades == 0:
                print(f"  {fold_num:<6} {'0':<8} {'N/A':<10} {'N/A':<12} {'0.0':<10} {'⚠️ no trades'}")
                continue
            
            # Calculate R per trade
            r_values = traded[outcome_col].map({
                'win': 2.0,
                'loss': -1.0,
                'timeout': 0.0
            })
            
            expectancy = r_values.mean()
            net_r = r_values.sum()
            win_rate = (traded[outcome_col] == 'win').mean()
            status = '✓' if expectancy > 0 else '✗'
            
            fold_expectations.append(expectancy)
            
            print(f"  {fold_num:<6} {n_trades:<8} {win_rate:<10.1%} "
                  f"{expectancy:<+12.3f}R {net_r:<+10.1f}R {status}")
        
        if fold_expectations:
            mean_exp = np.mean(fold_expectations)
            worst_exp = min(fold_expectations)
            pos_folds = sum(1 for e in fold_expectations if e > 0)
            
            print(f"\n  Summary: {pos_folds}/5 positive | "
                  f"Mean: {mean_exp:+.3f}R | Worst: {worst_exp:+.3f}R")
```

---

## Gate Evaluation (fill in after running)

### Gate A — Proceed to Holdout

| Criterion | LONG (best thr) | SHORT (best thr) | Pass? |
|-----------|-----------------|-------------------|-------|
| Positive folds ≥ 4/5 | ?/5 at thr=? | ?/5 at thr=? | ? |
| Mean expectancy ≥ +0.09R | ?R | ?R | ? |
| Worst fold exp ≥ -0.15R | ?R | ?R | ? |
| Avg trades/fold ≥ 80 | ? | ? | ? |

### Gate B — Meta-Gating (if improved but not enough)

Triggered if: mean expectancy improved from v0.3 (+0.071R) but still < +0.09R

### Gate C — Pivot (if no improvement)

Triggered if: mean expectancy change < +0.01R for both directions

### Comparison Table (fill in)

| Metric | v0.3 LONG | v0.4 LONG | Change | v0.3 SHORT | v0.4 SHORT | Change |
|--------|-----------|-----------|--------|------------|------------|--------|
| Mean Exp | +0.071R | ? | ? | +0.071R | ? | ? |
| Pos Folds | 3/5 | ? | ? | 2/5 | ? | ? |
| Worst Fold | -0.095R | ? | ? | -0.268R | ? | ? |
| Avg Trades | 466 | ? | ? | 364 | ? | ? |

---

## Success Criteria

- [ ] Expectancy (R-multiple) calculated for all folds × thresholds × directions
- [ ] Results in same table format as v0.3 (PHASE2_MTF_EXPERIMENT.md)
- [ ] Gate A/B/C evaluated with clear pass/fail per criterion
- [ ] Comparison table filled in with v0.3 vs v0.4 deltas
- [ ] STATUS.md updated with v0.4 results and gate decision
- [ ] If Gate A passed: note "READY FOR HOLDOUT TEST"
- [ ] If Gate B: note "META-GATING EXPERIMENT NEXT"
- [ ] If Gate C: note "PIVOT DECISION REQUIRED"
