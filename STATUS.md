# Status

**Current phase:** Phase 2 — Feature Engineering (Branch C)
**Last completed:** MTF feature experiment (v0.3) with walk-forward CV
**Decision:** Both models trigger Branch C - Feature Engineering Required
**Next step:** Choose feature engineering approach or proceed with current model despite risks

---

## Phase 2 MTF Experiment Results (v0.3 - Apr 15, 2026)

**Dataset:** 244,482 rows with 44 features (39 original + 5 MTF from v4.6.0)

**Full details:** See `PHASE2_MTF_EXPERIMENT.md`

### Summary

Added 5 multi-timeframe alignment features from JCAMP_FxScalper v4.6.0:
- `mtf_alignment_score` (-4 to +4) - Net TF alignment
- `mtf_stacking_score` (-3 to +3) - SMA ordering strength
- `bars_since_tf_fast_flip` (0-200) - Recency of M15 crossover ⭐ **Highest MTF importance**
- `tf_fast_flip_direction` (-1/0/+1) - Flip direction
- `mtf_alignment_duration` (-200 to +200) - Regime persistence

### Walk-Forward CV Results (Threshold 0.55)

**LONG Model:**
- Mean expectancy: **+0.071R** (was +0.013R, **+0.058R improvement**)
- Positive folds: **3/5** (60%, unchanged)
- Worst fold: **-0.095R** (was -0.297R, **+0.202R improvement**)

**SHORT Model:**
- Mean expectancy: **+0.071R** (was +0.083R, -0.012R decline)
- Positive folds: **2/5** (40%, **WORSENED** from 3/5)
- Worst fold: **-0.268R** (was -0.368R, +0.100R improvement)

### Decision Tree Verdict

**Both models trigger Branch C: Feature Engineering Required**

**Failures:**
- ❌ Fold consistency < 4/5 (both at 2-3/5)
- ❌ Mean expectancy < 0.10R (both at +0.071R)
- ❌ SHORT worst fold < -0.15R (-0.268R)

**What MTF Features Fixed:**
- ✓ LONG worst-fold improved significantly (-0.297R → -0.095R)
- ✓ LONG expectancy improved (+0.013R → +0.071R)
- ✓ All 5 MTF features in top 20 importance (model uses them)

**What MTF Features Did NOT Fix:**
- ✗ Fold consistency (still only 60% or worse)
- ✗ Mean expectancy still below 0.10R threshold
- ✗ Bad folds (Fold 4 LONG, Fold 5 SHORT) still bad across ALL thresholds
- ✗ SHORT consistency actually worsened

**Key Insight:** v4.6.0's "fresh flip" concept (`bars_since_tf_fast_flip`) validated as highest MTF feature importance, but MTF alignment alone doesn't capture regime quality. Bad folds are **regime-specific failures** that MTF doesn't address.

---

## Phase 2 Decision - Original Experiment Results (39 Features)

### ⚠️ CRITICAL FINDING: Fold 6 Missing

Walk-forward CV only generated **5 folds** instead of 6. This is Correction 1 from PHASE2_DECISION.md.

**Cause:** With `n_splits=6` and `test_size=0.15`, the 6th fold would extend beyond the train/CV window (Sep 2025).

**Impact:** All results below are **5-fold**, not 6-fold. Adjust decision tree gates accordingly (5/5 = 100%, 4/5 = 80%, 3/5 = 60%).

---

## Multi-Threshold Walk-Forward Results (Steps 2-6 Complete)

### LONG Model

| Threshold | Positive folds | Mean exp  | Worst fold exp | Worst fold net R | Stdev exp | Avg trades/fold |
|-----------|----------------|-----------|----------------|------------------|-----------|-----------------|
| 0.55      | **3/5 (60%)**  | +0.013R   | **-0.297R**    | **-231.2R**      | 0.227     | 481             |
| 0.60      | **3/5 (60%)**  | +0.037R   | **-0.341R**    | **-194.8R**      | 0.283     | 337             |
| 0.65      | **3/5 (60%)**  | +0.034R   | **-0.356R**    | **-128.0R**      | 0.442     | 239             |
| 0.70      | 3/5 (60%)      | -0.097R ❌ | **-0.963R** ❌  | **-84.0R**       | 0.563     | 162             |

**Key observations:**
- Fold consistency does NOT improve with higher thresholds (still 3/5 at all thresholds)
- Mean expectancy peaks at 0.60 (+0.037R), not 0.65 or 0.70
- **Worst fold gets WORSE at higher thresholds** (Fold 5 at 0.70: -0.963R expectancy!)
- High volatility across folds (Stdev increases with threshold)
- Fold 4 is consistently the worst performer

### SHORT Model

| Threshold | Positive folds | Mean exp  | Worst fold exp | Worst fold net R | Stdev exp | Avg trades/fold |
|-----------|----------------|-----------|----------------|------------------|-----------|-----------------|
| 0.55      | **3/5 (60%)**  | +0.083R   | -0.368R        | -113.3R          | 0.390     | 374             |
| 0.60      | **3/5 (60%)**  | +0.136R   | -0.344R        | -71.3R           | 0.438     | 252             |
| 0.65      | **2/5 (40%)** ❌ | +0.138R   | **-0.412R**    | -63.1R           | 0.575     | 168             |
| 0.70      | **2/5 (40%)** ❌ | +0.176R   | **-0.411R**    | -47.6R           | 0.663     | 99              |

**Key observations:**
- Fold consistency **WORSENS** at higher thresholds (3/5 → 2/5)
- Mean expectancy improves with threshold (0.083R → 0.176R)
- Worst fold expectancy gets worse at higher thresholds
- Fold 5 is consistently the worst performer
- At 0.70, only 99 trades/fold (approaching statistical unreliability)

---

## Critical Insights

### 1. Raising Threshold Does NOT Fix Fold Consistency ❌

The core assumption in `PHASE2_CORRECTED_RESULTS.md` — that threshold 0.65 would improve fold consistency — is **FALSE**:

- **LONG:** 3/5 positive folds at ALL thresholds (no improvement)
- **SHORT:** 3/5 positive at 0.55-0.60, then **DROPS to 2/5** at 0.65-0.70

**Implication:** The "bad folds" (Fold 4 for LONG, Fold 5 for SHORT) are bad across ALL thresholds. This suggests regime-specific failure, not threshold sensitivity.

### 2. Worst-Fold Performance is Catastrophic

| Direction | Threshold | Worst Fold | Worst Expectancy | Worst Net R |
|-----------|-----------|------------|------------------|-------------|
| LONG      | 0.70      | Fold 5     | **-0.963R**      | -37.6R      |
| LONG      | 0.65      | Fold 5     | -0.356R          | -28.2R      |
| SHORT     | 0.65      | Fold 5     | **-0.412R**      | -63.1R      |
| SHORT     | 0.70      | Fold 5     | -0.411R          | -43.2R      |

A system with -0.96R expectancy in a bad fold would **destroy the account** in that period. This is a fatal flaw for live trading.

### 3. High Fold-to-Fold Volatility

Standard deviation of expectancy increases with threshold:
- **LONG 0.70:** Stdev = 0.563 (one fold at -0.96R, another at +0.53R)
- **SHORT 0.70:** Stdev = 0.663

This indicates the model is **unstable** — performance varies wildly by time period.

### 4. Optimal Threshold Varies by Metric

**For LONG:**
- Best mean expectancy: 0.60 (+0.037R)
- Best worst-fold: 0.55 (-0.297R vs -0.963R at 0.70)
- Lowest volatility: 0.55 (Stdev 0.227)

**For SHORT:**
- Best mean expectancy: 0.70 (+0.176R)
- Best fold consistency: 0.55 or 0.60 (3/5 vs 2/5 at 0.70)
- Best worst-fold: 0.60 (-0.344R vs -0.412R at 0.65)

**There is no single threshold that optimizes all criteria.**

---

## Artifacts Generated (Steps 3-4)

All files saved to `notebooks/outputs/phase2_decision/`:

1. ✓ `walk_forward_multi_threshold_long.csv` - Detailed results
2. ✓ `walk_forward_multi_threshold_short.csv` - Detailed results
3. ✓ `fold_equity_curves_long_thr{0.55,0.60,0.65,0.70}.png` - 4 charts
4. ✓ `fold_equity_curves_short_thr{0.55,0.60,0.65,0.70}.png` - 4 charts
5. ⚠️ `threshold_consistency_summary.md` - Partial (needs manual review)

---

## Decision Tree Assessment (COMPLETE)

### Branch C: Feature Engineering Required ✓ TRIGGERED

**Both LONG and SHORT models fail deployment criteria.**

**LONG Model (v0.3 with MTF):**
- ✗ Positive folds: 3/5 (fails ≥4/5 for Branch A)
- ✗ Mean expectancy: +0.071R (fails ≥0.10R for Branch A)
- ✓ Worst fold: -0.095R (passes ≥-0.15R)
- ✓ Avg trades/fold: 466 (passes ≥100)

**SHORT Model (v0.3 with MTF):**
- ✗ Positive folds: 2/5 (fails ≥3/5 for Branch B)
- ✗ Mean expectancy: +0.071R (fails ≥0.15R for Branch B)
- ✗ Worst fold: -0.268R (fails ≥-0.15R)
- ✓ Avg trades/fold: 364 (passes ≥100)

**Trigger:** Mean expectancy < 0.10R at ALL thresholds (0.55-0.70) for both directions.

---

## Next Steps - Branch C Options

### Option 1: Additional Feature Engineering

**Regime Detection Features:**
- Volatility regime clustering (high/low ATR periods)
- Trend quality (ADX, R-squared)
- Market correlation breakdown
- Session-specific behavior modeling

**Market Microstructure:**
- Order flow proxies (volume patterns)
- Liquidity measures (spread behavior)
- News event proximity filters

**Ensemble/Gating:**
- Train separate models per regime
- Meta-model for regime classification
- Hybrid approach with gating mechanism

### Option 2: Proceed with Current Model (Accept Risks)

**If proceeding despite 60% fold consistency:**
- Run held-out test (Oct 2025 - Mar 2026) at threshold 0.55
- Validate CV estimates against true out-of-sample performance
- Accept that ~40% of future periods may be losing
- **Risk:** Catastrophic drawdown in bad regimes (e.g., SHORT Fold 5: -107R)

### Option 3: Hybrid Approach

**Use v4.6.0 logic + ML enhancements:**
- v4.6.0's hand-crafted entry rules
- ML for regime detection (when to trade vs not trade)
- ML for position sizing/risk management
- Combine rule-based and statistical approaches

---

## Critical Findings

### What We Learned

1. **MTF features from v4.6.0 add signal** - All 5 features in top 20 importance
2. **"Fresh flip" concept validated** - `bars_since_tf_fast_flip` = highest MTF feature
3. **LONG improved modestly** - Expectancy +0.058R, worst-fold loss reduced 68%
4. **SHORT consistency worsened** - Dropped from 3/5 to 2/5 positive folds
5. **Bad folds are regime-specific** - Same folds fail across all thresholds and feature sets
6. **Mean expectancy still too low** - Both at +0.071R, need ≥0.10R for deployment

### What Didn't Work

- ❌ **Raising threshold** - Does NOT improve fold consistency
- ❌ **MTF alignment alone** - Captures directional bias but not regime quality
- ❌ **Higher feature count** - 44 features vs 39 didn't solve core problem

### Root Cause

**Models can't distinguish market regimes:**
- Trending vs ranging (both can have MTF alignment)
- Clean vs choppy trends
- Macro regime shifts (policy changes, etc.)

MTF features tell us **direction** but not **regime quality**.

---

## Files Generated

**Data Collection:**
- `data/DataCollector_EURUSD_M5_20230101_220400.csv` - 244,482 rows, 44 features (v0.3)
- `data/DataCollector_EURUSD_M5_20230101_220400_partial_backup.csv` - 24K rows (test run backup)

**Code:**
- `cbot/JCAMP_DataCollector.cs` - v0.3 with MTF calculation logic
- `phase2_multi_threshold_experiment.py` - Experiment script
- `phase2_experiment_output.txt` - Console output

**Documentation:**
- `PHASE2_MTF_EXPERIMENT.md` - Complete MTF experiment analysis
- `DataCollector_v0.3_patch.md` - MTF patch specification

**Results:**
- `notebooks/outputs/phase2_decision/walk_forward_multi_threshold_long.csv` - v0.3 LONG results
- `notebooks/outputs/phase2_decision/walk_forward_multi_threshold_short.csv` - v0.3 SHORT results
- `notebooks/outputs/phase2_decision/fold_equity_curves_*_thr*.png` - 8 equity curve plots

---

## Dataset Summary (v0.3 - Current)

- **Total rows:** 244,482 M5 bars (EURUSD)
- **Date range:** Jan 2, 2023 → Apr 14, 2026 (3.28 years)
- **Features:** 44 (39 original + 5 MTF)
- **Data splits:**
  - Train/CV: 204,510 rows (Jan 2023 - Sep 2025)
  - Held-out test: 36,845 rows (Oct 2025 - Mar 2026) **[UNTOUCHED]**
  - Live forward: 3,127 rows (Apr 2026+)
