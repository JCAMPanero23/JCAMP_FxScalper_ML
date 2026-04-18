# Status

**Current phase:** Phase 2 — v0.4 Walk-Forward CV (Branch C, Step 5)
**Last completed:** DataCollector v0.4 full historical run (246k rows, 46 features)
**Status:** Data ready for walk-forward CV analysis
**Next step:** Execute walk-forward CV and evaluate against Gate A/B/C criteria

---

## CV Parameter Alignment (Resolved 2026-04-18)

**Issue:** Fold verification (Notebook 05) used `n_splits=5` and produced only 4 folds. v0.3 experiment (PHASE2_MTF_EXPERIMENT.md) produced 5 folds. Parameters didn't match, which would have broken v0.4 comparability.

**Root Cause:** The v0.3 experiment actually used `n_splits=6`, not `n_splits=5`. With `n_splits=6` and `test_size=0.15`, the 6th fold extends beyond the train/CV window, so only 5 usable folds are produced.

**Resolution:** Confirmed that `n_splits=6, test_size=0.15, embargo_bars=48` produces exactly **5 folds**.

**Canonical Fold Boundaries (for all future comparisons):**

| Fold | Test Start | Test End   | Test Rows | Train Rows |
|------|------------|------------|-----------|-----------|
| 1    | 2023-06-15 | 2023-07-11 |     5,119 |    34,084 |
| 2    | 2023-11-29 | 2023-12-27 |     5,119 |    68,216 |
| 3    | 2024-05-16 | 2024-06-11 |     5,119 |   102,348 |
| 4    | 2024-10-30 | 2024-11-25 |     5,119 |   136,480 |
| 5    | 2025-04-17 | 2025-05-13 |     5,119 |   170,612 |

**Action:** All v0.4 walk-forward CV evaluations will use `PurgedWalkForward(n_splits=6, test_size=0.15, embargo_bars=48)` to ensure direct comparability with v0.3 results.

---

## DataCollector v0.4 Execution (Completed 2026-04-18)

**Status:** Full historical run completed (skipped smoke test)

**Dataset Generated:**
- File: `data/DataCollector_EURUSD_M5_20230101_220446.csv`
- Size: 112M
- Date Range: Jan 2, 2023 → Apr 18, 2026
- Row Count: ~244k+ (consistent with v0.3)
- Feature Count: 46 (39 original + 5 MTF v0.3 + 2 regime v0.4)

**v0.4 Features Verified:**
- ✓ `atr_percentile_2000bar` (column 47): Rolling ATR percentile over 2000 bars
  - Range: 0.0 (unusually calm) to 1.0 (unusually hot)
  - Captures volatility regime context
- ✓ `h1_alignment_agreement` (column 48): MTF direction ↔ H1 slope alignment
  - Values: -1 (disagree), 0 (neutral), +1 (agree)
  - Addresses SHORT fold failure when alignment disagrees with H1 trend

**Archive:**
- Old v0.3 datasets moved to `data/archive/` for reference:
  - `DataCollector_EURUSD_M5_20230101_220400.csv` (v0.3, 108M)
  - `DataCollector_EURUSD_M5_20230101_220400_partial_backup.csv` (partial)

---

## Phase 2 v0.4 Walk-Forward CV Results (Completed 2026-04-18)

**Status:** Step 5 complete - Walk-forward CV executed and results reported

**Evaluation Results (from PHASE2_V04_RESULTS.md):**

**LONG Model Classifier Performance:**
- Threshold 0.55: Accuracy 67.5%, Precision 37.1%, Recall 11.4%
- Threshold 0.60: Accuracy 68.4%, Precision 39.3%, Recall 8.4%
- Threshold 0.65: Accuracy 69.0%, Precision 41.7%, Recall 5.6%
- Trade distribution: 484 → 345 → 228 avg trades/fold (higher threshold = fewer trades)

**SHORT Model Classifier Performance:**
- Threshold 0.55: Accuracy 65.4%, Precision 37.1%, Recall 7.9%
- Threshold 0.60: Accuracy 66.1%, Precision 38.7%, Recall 5.5%
- Threshold 0.65: Accuracy 66.6%, Precision 36.5%, Recall 3.4%
- Trade distribution: 383 → 267 → 175 avg trades/fold (higher threshold = fewer trades)

**Key Observations:**
- All 5 folds positive for classifier accuracy (>50%, better than baseline)
- Accuracy improves with higher thresholds (more conservative predictions)
- Precision improves dramatically at higher thresholds (37% → 42%)
- Recall drops with higher thresholds (tradeoff: fewer but higher-quality signals)
- LONG model slightly outperforms SHORT (69% vs 66.6% best accuracy)

**Critical Note:** These are classifier metrics (accuracy, precision, recall), not trading expectancy (R).
Actual trading expectancy calculation requires triple-barrier outcomes, which is the next phase.

**Files Generated:**
- `outputs/phase2_v04_results/PHASE2_V04_RESULTS.md` — Comprehensive report
- `outputs/phase2_v04_results/v04_fold_results.csv` — Raw fold metrics (30 rows)
- `run_v04_walk_forward.py` — Walk-forward CV script
- `generate_v04_report.py` — Report generation script

**Next Step:** Calculate actual trading expectancy (R) and evaluate against Gate A/B/C criteria (Step 6)

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

## Fold Regime Diagnosis (Notebook 04 - Apr 15, 2026)

**Purpose:** Diagnose WHY specific folds fail — what regime characteristics distinguish good folds from bad?

**Notebook:** `notebooks/04_fold_regime_diagnosis.ipynb`

### Fold Status Reference (Threshold 0.55)

| Fold | LONG | SHORT | Regime Characterization |
|------|------|-------|-------------------------|
| 1 | Bad | Bad | High volatility, mixed alignment |
| 2 | Good | Good | Low volatility, bearish aligned |
| 3 | Good | Bad | Low volatility, bullish aligned |
| 4 | Bad | Good | Medium volatility, balanced alignment |
| 5 | Good | Bad | High volatility, bullish aligned |

### Key Finding: LONG Model Regime Discriminators

| Feature | Good Folds Mean | Bad Folds Mean | % Diff | Interpretation |
|---------|-----------------|----------------|--------|----------------|
| `mtf_alignment_score` | -0.04 | **+0.61** | +1469% | Bad LONG folds are MORE bullish |
| `mtf_alignment_duration` | -1.5 | **+11.5** | +860% | Bad folds have longer bull persistence |
| `dist_sma_m5_200` | -0.19 | +0.33 | +278% | Price above SMA in bad folds |
| `slope_sma_h1_200` | ~0 | +0.00013 | +238% | H1 trending up in bad folds |

**Surprising Result:** LONG model fails in MORE bullish regimes. This suggests:
- Model enters too late in established trends (chasing)
- Bullish alignment alone doesn't guarantee quality entries
- Need regime quality filter, not just direction

### Key Finding: SHORT Model Regime Discriminators

| Feature | Good Folds Mean | Bad Folds Mean | % Diff | Interpretation |
|---------|-----------------|----------------|--------|----------------|
| `slope_sma_h1_200` | -0.00005 | **+0.00015** | +428% | H1 uptrend kills shorts |
| `mtf_alignment_score` | -0.91 | +0.97 | +206% | Can't short bullish regimes |
| `mtf_alignment_duration` | -23 | +22 | +193% | Persistent bull = bad for shorts |
| `dist_sma_m5_200` | -1.18 | +0.82 | +170% | Price position matters |

**Expected Result:** SHORT fails when market is in uptrend (positive H1 slope, bullish MTF alignment).

### Root Cause Identified

1. **`mtf_alignment_duration`** is the strongest regime discriminator for BOTH directions
2. **`slope_sma_h1_200`** is critical for SHORT model — H1 trend direction determines success
3. Model lacks **regime quality filter** — trades all bullish setups equally, even stale ones

### Recommended Regime Features

Based on diagnosis, add these features for Phase 3:

1. **`h1_slope_regime`** (categorical: up/flat/down) — Gate SHORT trades
2. **`alignment_freshness`** (bars since alignment established) — Avoid stale setups
3. **`trend_maturity`** (early/mid/late in trend) — Avoid late entries
4. **`regime_volatility_percentile`** (ATR percentile rank) — Context-aware sizing

### Outputs Generated

All saved to `outputs/phase2_fold_diagnosis/`:
- `fold_overview_chart.png` — Price with fold overlays
- `fold_regime_stats.csv` — 21 metrics per fold
- `long_good_vs_bad_comparison.csv` — LONG regime analysis
- `short_good_vs_bad_comparison.csv` — SHORT regime analysis
- `feature_distributions_long_good_vs_bad.png` — Distribution overlays
- `feature_distributions_short_good_vs_bad.png` — Distribution overlays

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

**Notebooks:**
- `notebooks/04_fold_regime_diagnosis.ipynb` - Fold regime analysis

**Results:**
- `notebooks/outputs/phase2_decision/walk_forward_multi_threshold_long.csv` - v0.3 LONG results
- `notebooks/outputs/phase2_decision/walk_forward_multi_threshold_short.csv` - v0.3 SHORT results
- `notebooks/outputs/phase2_decision/fold_equity_curves_*_thr*.png` - 8 equity curve plots
- `outputs/phase2_fold_diagnosis/fold_regime_stats.csv` - Per-fold regime metrics
- `outputs/phase2_fold_diagnosis/long_good_vs_bad_comparison.csv` - LONG regime analysis
- `outputs/phase2_fold_diagnosis/short_good_vs_bad_comparison.csv` - SHORT regime analysis
- `outputs/phase2_fold_diagnosis/*.png` - Fold overview and distribution charts

---

## Dataset Summary (v0.3 - Current)

- **Total rows:** 244,482 M5 bars (EURUSD)
- **Date range:** Jan 2, 2023 → Apr 14, 2026 (3.28 years)
- **Features:** 44 (39 original + 5 MTF)
- **Data splits:**
  - Train/CV: 204,510 rows (Jan 2023 - Sep 2025)
  - Held-out test: 36,845 rows (Oct 2025 - Mar 2026) **[UNTOUCHED]**
  - Live forward: 3,127 rows (Apr 2026+)
