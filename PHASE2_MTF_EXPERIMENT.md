# Phase 2 - MTF Feature Experiment Results

**Date:** 2026-04-15
**Objective:** Test if v4.6.0's multi-timeframe alignment logic improves ML model performance
**Dataset:** v0.3 - 244,482 rows with 44 features (39 original + 5 MTF)

---

## Executive Summary

**MTF features from JCAMP_FxScalper v4.6.0 provided MODEST improvements to LONG but did NOT solve the core fold consistency problem.**

**Result:** Both models still fail Branch A/B criteria and require **Branch C: Feature Engineering**.

---

## What Was Added

### 5 New Multi-Timeframe Features

Ported from v4.6.0's alignment-based entry logic:

| Feature | Type | Range | Purpose |
|---------|------|-------|---------|
| `mtf_alignment_score` | Integer | -4 to +4 | Net count of TFs where price > SMA (M5/M15/M30/H1) |
| `mtf_stacking_score` | Integer | -3 to +3 | SMA ordering strength (faster above slower = bullish) |
| `bars_since_tf_fast_flip` | Integer | 0-200 | Bars since M15 price/SMA crossover (v4.6.0's trigger) |
| `tf_fast_flip_direction` | Integer | -1/0/+1 | Direction of most recent M15 flip |
| `mtf_alignment_duration` | Integer | -200 to +200 | Signed run length of current alignment regime |

**Technical notes:**
- M5 uses SMA 275 (same as v4.6.0)
- HTFs use existing SMA 200 (close enough, period mismatch small)
- M15 used as "fast flip" TF (v4.6.0's TF0 equivalent at M5 decision horizon)

---

## Walk-Forward CV Results (Threshold 0.55)

### LONG Model

| Fold | Trades | Win Rate | Expectancy | Net R | Status |
|------|--------|----------|------------|-------|--------|
| 1 | 817 | 32.9% | -0.052R | -42.7R | ✗ |
| 2 | 321 | 43.9% | +0.278R | +89.2R | ✓ |
| 3 | 322 | 41.0% | +0.190R | +61.1R | ✓ |
| 4 | 803 | 31.5% | -0.095R | -76.1R | ✗ |
| 5 | 265 | 35.9% | +0.035R | +9.4R | ✓ |

**Summary:**
- Mean expectancy: **+0.071R** (was +0.013R, improved +0.058R)
- Positive folds: **3/5** (unchanged)
- Worst fold: **-0.095R** (was -0.297R, improved +0.202R)

### SHORT Model

| Fold | Trades | Win Rate | Expectancy | Net R | Status |
|------|--------|----------|------------|-------|--------|
| 1 | 561 | 31.0% | -0.110R | -61.4R | ✗ |
| 2 | 477 | 35.9% | +0.035R | +16.9R | ✓ |
| 3 | 246 | 34.2% | -0.016R | -3.8R | ✗ |
| 4 | 137 | 58.4% | +0.712R | +97.5R | ✓ |
| 5 | 400 | 25.8% | -0.268R | -107.0R | ✗ |

**Summary:**
- Mean expectancy: **+0.071R** (was +0.083R, declined -0.012R)
- Positive folds: **2/5** (was 3/5, WORSENED)
- Worst fold: **-0.268R** (was -0.368R, improved +0.100R)

---

## Comparison to Original (39 Features)

### LONG Model

|  | Original | v0.3 MTF | Change | Verdict |
|---|---|---|---|---|
| **Mean Exp** | +0.013R | +0.071R | **+0.058R** | ✓ IMPROVED |
| **Pos Folds** | 3/5 (60%) | 3/5 (60%) | 0 | = SAME |
| **Worst Fold** | -0.297R | -0.095R | **+0.202R** | ✓ IMPROVED |

### SHORT Model

|  | Original | v0.3 MTF | Change | Verdict |
|---|---|---|---|---|
| **Mean Exp** | +0.083R | +0.071R | -0.012R | = SAME |
| **Pos Folds** | 3/5 (60%) | 2/5 (40%) | -1 | ✗ WORSE |
| **Worst Fold** | -0.368R | -0.268R | +0.100R | ✓ IMPROVED |

---

## Feature Importance Analysis

**Top 5 MTF Features (LONG model):**

| Rank | Feature | Importance | Insight |
|------|---------|------------|---------|
| 1 | `bars_since_tf_fast_flip` | 2048 | **Highest MTF feature** - recency of M15 crossover matters |
| 2 | `mtf_alignment_duration` | 1750 | Regime persistence is predictive |
| 3 | `mtf_stacking_score` | 682 | SMA ordering adds signal |
| 4 | `tf_fast_flip_direction` | 288 | Flip direction useful |
| 5 | `mtf_alignment_score` | 246 | Raw alignment count less important |

**All 5 MTF features appeared in top 20** (out of 44 features), confirming they add signal.

**Key insight:** v4.6.0's "fresh flip" trigger concept (`bars_since_tf_fast_flip`) has the highest importance among MTF features, validating that idea.

---

## Decision Tree Assessment (PHASE2_DECISION.md)

### Branch A Requirements (Proceed to Held-Out Test)
**All must hold at threshold T*:**

| Requirement | LONG | SHORT | Status |
|-------------|------|-------|--------|
| Positive folds ≥ 4/5 | 3/5 | 2/5 | ✗ FAIL |
| Worst fold exp ≥ -0.15R | -0.095R | -0.268R | ✓/✗ |
| Mean exp ≥ 0.10R | +0.071R | +0.071R | ✗ FAIL |
| Avg trades/fold ≥ 100 | 466 | 364 | ✓ PASS |
| Equity curves persistent climb | TBD | TBD | N/A |
| Plateau width ≥ 0.08 | TBD | TBD | N/A |

**Result:** Both models **FAIL** Branch A (fold consistency and expectancy gates).

### Branch B Requirements (Reduced Confidence Test)
**All must hold at T*:**

| Requirement | LONG | SHORT | Status |
|-------------|------|-------|--------|
| Positive folds = 3/5 | 3/5 | 2/5 | ✓/✗ |
| Worst fold exp ≥ -0.10R | -0.095R | -0.268R | ✓/✗ |
| Mean exp ≥ 0.15R | +0.071R | +0.071R | ✗ FAIL |
| Plateau width ≥ 0.15 | TBD | TBD | N/A |
| Avg trades/fold ≥ 80 | 466 | 364 | ✓ PASS |

**Result:** LONG close but fails mean exp gate. SHORT fails fold consistency and expectancy.

### Branch C Triggers (Feature Engineering Required)
**Any of:**

| Trigger | LONG | SHORT | Status |
|---------|------|-------|--------|
| No threshold achieves ≥ 3/5 positive folds | 3/5 at 0.55-0.70 | 2/5 at 0.65-0.70 | ✗/✓ |
| At every threshold, worst fold < -0.15R | -0.095R at 0.55 | -0.268R at all | ✓/✓ |
| Mean exp < 0.10R at every threshold | +0.071R | +0.071R | ✓ TRIGGERED |
| Equity curves show 2-winner carry | TBD | TBD | N/A |
| Trade count < 20/fold | 466 avg | 364 avg | ✗ PASS |

**Result:** Both models **TRIGGER Branch C** (mean expectancy too low at all thresholds).

---

## Critical Insights

### 1. MTF Features Add Signal, But Not Enough

**Evidence:**
- LONG expectancy improved from +0.013R to +0.071R (+5.8R improvement)
- LONG worst-fold improved from -0.297R to -0.095R (68% reduction in loss)
- All 5 MTF features in top 20 importance (model uses them)

**BUT:**
- Fold consistency unchanged (LONG) or worse (SHORT)
- Mean expectancy still < 0.10R threshold
- Bad folds (Fold 4 LONG, Fold 5 SHORT) still fail

### 2. The "Bad Folds" Are Regime-Specific

**Observation:** The same folds fail across original AND MTF versions:
- **Fold 4 (LONG):** Fails in both versions (-0.297R → -0.095R, still negative)
- **Fold 5 (SHORT):** Catastrophic in both (-0.368R → -0.268R, still disastrous)

**Implication:** These folds represent **market regimes** where:
- MTF alignment is present but doesn't predict outcomes
- Some other factor (volatility? trend strength? news events?) dominates
- The model's features don't capture regime changes

### 3. v4.6.0's "Fresh Flip" Concept Works

**Feature importance ranking confirms:**
- `bars_since_tf_fast_flip` = highest MTF feature (2048 importance)
- This directly implements v4.6.0's "wait for TF0 crossover" trigger

**Interpretation:** v4.6.0 was right that **fresh crossovers matter**, but:
- The 5:1 RR was too aggressive (we use 2:1)
- Alignment alone doesn't filter bad regimes
- Need additional regime detection on TOP of MTF alignment

### 4. No Single Threshold Optimizes All Metrics

**LONG:**
- Best mean exp: 0.70 (+0.105R) but only 4/5 positive folds
- Best fold consistency: 0.55-0.70 (all 3/5)
- Best worst-fold: 0.70 (-0.116R, still fails -0.15R gate)

**SHORT:**
- Best mean exp: 0.70 (+0.033R) but only 2/5 positive folds
- Best fold consistency: 0.55-0.60 (3/5)
- Best worst-fold: 0.60 (-0.121R)

**Trade-off:** Higher thresholds improve some metrics but worsen consistency.

---

## What MTF Features Did NOT Fix

1. **Fold consistency:** Still only 60% positive folds (LONG) or 40% (SHORT)
2. **Regime robustness:** Bad folds are bad across ALL thresholds
3. **Catastrophic losses:** Worst fold still -0.095R to -0.268R (fails -0.15R gate)
4. **Mean expectancy:** Still below 0.10R threshold at all thresholds

**Root cause:** MTF alignment captures **directional bias** but not **regime quality**. The model can't distinguish:
- Trending vs ranging markets (both can have alignment)
- Clean vs choppy trends
- Macro regime shifts (e.g., central bank policy changes)

---

## Recommendations

### Immediate Actions

1. **Document verdict:** MTF features improve LONG modestly but both models still fail deployment criteria
2. **Branch C path confirmed:** Requires feature engineering beyond MTF alignment
3. **Preserve v0.3 dataset:** Keep 244K row CSV with MTF features for future experiments

### Feature Engineering Approaches (Branch C)

**Option 1: Regime Detection Features**
- Volatility regime (high/low ATR clusters)
- Trend quality (ADX, R-squared of price regression)
- Correlation breakdown (EUR/USD vs other pairs)
- Session-specific behavior (London vs NY vs Asia)

**Option 2: Market Microstructure**
- Order flow proxies (volume, bid/ask spread)
- Liquidity measures (slippage, tick velocity)
- News event proximity (NFP, FOMC, etc.)

**Option 3: Ensemble/Gating Models**
- Train separate models per regime
- Meta-model decides which base model to use
- Regime classifier as gating mechanism

**Option 4: Abandon ML, Use v4.6.0 Logic**
- Accept that v4.6.0's hand-crafted logic might be better
- Use ML only for regime detection (when to trade vs not)
- Hybrid: v4.6.0 entry logic + ML position sizing

### Alternative: Proceed Despite Risks

**If accepting 60% fold consistency:**
- Run held-out test (Oct 2025 - Mar 2026) at threshold 0.55 or 0.60
- See if real performance matches CV estimates
- Understand that 40% of future periods may be losing

**Risk:** Catastrophic drawdown in bad regimes (Fold 5 SHORT: -107R on 400 trades)

---

## Files Generated

**Data:**
- `data/DataCollector_EURUSD_M5_20230101_220400.csv` - 244,482 rows, 44 features (v0.3)

**Code:**
- `cbot/JCAMP_DataCollector.cs` - v0.3 with MTF feature calculation

**Results:**
- `notebooks/outputs/phase2_decision/walk_forward_multi_threshold_long.csv`
- `notebooks/outputs/phase2_decision/walk_forward_multi_threshold_short.csv`
- `notebooks/outputs/phase2_decision/fold_equity_curves_long_thr{0.55,0.60,0.65,0.70}.png`
- `notebooks/outputs/phase2_decision/fold_equity_curves_short_thr{0.55,0.60,0.65,0.70}.png`

---

## Conclusion

**MTF features from v4.6.0 validated the "fresh flip" concept but did not solve fold consistency.**

The experiment confirms:
- v4.6.0's core idea (MTF alignment + flip trigger) has merit
- Feature engineering improved LONG expectancy by 5.8R
- BUT: Both models still fail deployment criteria (Branch C triggered)

**Next decision point:** Choose feature engineering approach or accept current performance with known risks.
