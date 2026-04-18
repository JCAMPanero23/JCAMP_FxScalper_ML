# Phase 2 Fold Regime Diagnosis - Implementation Guide

## Overview

**Notebook:** `notebooks/04_fold_regime_diagnosis.ipynb`

This notebook implements a comprehensive diagnosis of why certain folds fail in the Phase 2 walk-forward cross-validation. The analysis identifies regime-specific characteristics that favor or hinder LONG and SHORT trading strategies.

## Problem Statement

The Phase 2 multi-threshold walk-forward experiment revealed inconsistent performance across 5 folds:

```
Fold Status (at threshold 0.55):
┌────────┬──────────┬───────────┐
│ Fold   │ LONG     │ SHORT     │
├────────┼──────────┼───────────┤
│ 1      │ ❌ Bad   │ ❌ Bad    │
│ 2      │ ✓ Good   │ ✓ Good    │
│ 3      │ ✓ Good   │ ❌ Bad    │
│ 4      │ ❌ Bad   │ ✓ Good    │
│ 5      │ ✓ Good   │ ❌ Bad    │
└────────┴──────────┴───────────┘
```

**Question:** Why do certain folds fail? What market regimes cause strategy breakdown?

## Data

- **Dataset:** `data/DataCollector_EURUSD_M5_20230101_220400.csv`
- **Period:** Jan 2023 - Sep 2025 (204,105 bars)
- **Timeframe:** M5 (5-minute)
- **Asset:** EURUSD
- **Features:** 44 (technical, MTF alignment, time-based)
- **Folds:** 5 walk-forward splits (~20% test size each)

## Notebook Structure

### Cell 1: Imports and Setup
- Load required libraries: pandas, numpy, matplotlib, seaborn, scipy.stats
- Set up output directory: `outputs/phase2_fold_diagnosis/`
- Configure plotting style

**Key functions available:**
```python
from src.data_loader import load_datacollector_csv, get_data_splits
from src.features import get_feature_columns
from src.cv import PurgedWalkForward
```

### Cell 2: Load Data
- Load full dataset from CSV (244,482 rows)
- Filter to train/CV window (Jan 2023 - Sep 2025)
- Verify data integrity

**Output:**
```
Train/CV set: 204,105 rows
Date range: 2023-01-02 06:15:00 to 2025-09-30 00:00:00
Columns: 44
```

### Cell 3: Reconstruct Fold Boundaries
Implements the same walk-forward logic as Phase 2:
- n_splits=5, embargo_bars=48, test_size=0.15
- Fold size: 40,821 bars
- Test size per fold: 6,123 bars
- Calculates fold indices and date ranges

**Output table:**
```
Fold 1: Test [    0 :  6123] => 2023-01-02 to 2023-01-31
Fold 2: Test [ 6123 : 12246] => 2023-02-01 to 2023-03-02
Fold 3: Test [12246 : 18369] => 2023-03-03 to 2023-04-01
Fold 4: Test [18369 : 24492] => 2023-04-02 to 2023-05-01
Fold 5: Test [24492 : 30615] => 2023-05-02 to 2025-09-30
```

### Cell 4: Tag Rows with Fold and Status
- Assigns `fold_num` (1-5) to each bar
- Tags fold region: train, embargo, test, or other
- Applies LONG/SHORT performance status to all bars in fold
- Enables analysis of entire fold period, not just test set

**Result columns added:**
- `fold_num`: Fold number (1-5)
- `fold_region`: Train/embargo/test/other
- `long_status`: good/bad/unknown
- `short_status`: good/bad/unknown

### Cell 5: Daily Price Chart with Fold Overlays
Creates publication-quality visualization:
- Synthetic price from cumsum(bar0_body × atr_m5)
- Daily resampling for readability
- Color-coded folds:
  - **Green shade:** Good LONG folds
  - **Red shade:** Bad LONG folds
- Labels show both LONG and SHORT status per fold

**Output file:** `fold_overview_chart.png`

This chart provides immediate visual insight into:
- Which periods support uptrends (LONG-friendly)
- Which periods support downtrends (SHORT-friendly)
- Transition points between regimes

### Cell 6: Eyeball Assessment Template
Markdown template for manual observation:
- Space to write observations for each fold
- Questions about price trend, volatility, alignment
- User fills in based on visual inspection of chart

**Note:** This is left for user completion in the interactive notebook.

### Cell 7: Per-Fold Regime Statistics
Implements `regime_stats()` function computing:

#### Volatility
- `atr_mean`: Average ATR (M5)
- `atr_std`: ATR standard deviation
- `atr_p90`: 90th percentile ATR
- `bb_width_mean`: Average Bollinger Band width

#### Trend Strength
- `adx_mean`: Average ADX (M5)
- `adx_above_25_pct`: % bars with ADX > 25 (strong trend threshold)

#### Directional Alignment
- `bull_aligned_pct`: % bars with mtf_alignment_score > 0.2
- `bear_aligned_pct`: % bars with mtf_alignment_score < -0.2
- `mixed_pct`: % bars in neutral zone (-0.2 to 0.2)

#### Persistence
- `avg_alignment_run`: Average duration of alignment streaks
- `flips_per_1000bar`: Regime flip frequency (lower = more persistent)

#### H1 Context
- `h1_slope_mean`: Average slope of H1 SMA 200
- `h1_slope_std`: Slope standard deviation

#### Label Statistics
- Win/loss/timeout counts for LONG and SHORT
- Win rates for both directions

**Output file:** `fold_regime_stats.csv`

Example output:
```
fold  atr_mean  atr_std  adx_mean  adx_above_25_pct  ...
1     0.00045   0.00038  23.5      38.2
2     0.00041   0.00035  24.1      39.8
3     0.00048   0.00041  25.3      42.1
4     0.00052   0.00043  22.8      36.5
5     0.00043   0.00037  23.9      38.7
```

### Cell 8: Good vs Bad Comparison (LONG)
- Filters to good LONG folds: [2, 3, 5]
- Filters to bad LONG folds: [1, 4]
- Computes mean values for each metric
- Calculates % difference
- Ranks by absolute % difference

**Output file:** `long_good_vs_bad_comparison.csv`

Example:
```
metric                    good_mean  bad_mean   pct_diff
atr_m5                    0.000410   0.000480   +17.1%
adx_m5                    24.5       23.2       -5.3%
mtf_alignment_score       0.156      -0.042     -127%
...
```

### Cell 9: Good vs Bad Comparison (SHORT)
Same analysis from SHORT perspective:
- Good SHORT folds: [2, 4]
- Bad SHORT folds: [1, 3, 5]

**Output file:** `short_good_vs_bad_comparison.csv`

### Cell 10: Mann-Whitney U Test
Tests statistical significance of differences between good/bad folds.

For each key feature:
```
Feature            p-value   Significance
atr_m5            0.0042    **
adx_m5            0.0318    *
mtf_alignment     <0.0001   ***
...
```

**Interpretation:**
- `***` (p < 0.001): Highly significant difference
- `**` (p < 0.01): Very significant
- `*` (p < 0.05): Significant
- (none): Not statistically significant

### Cell 11: Distribution Overlays (LONG)
Creates 5 histograms comparing good vs bad LONG folds:
1. ATR (volatility)
2. ADX (trend strength)
3. BB Width (volatility alternative)
4. MTF Alignment Score (directionality)
5. RSI (overbought/oversold)

Each histogram:
- **Green:** Good LONG folds
- **Red:** Bad LONG folds
- Density normalized for fair comparison

**Output file:** `feature_distributions_long_good_vs_bad.png`

### Cell 12: Distribution Overlays (SHORT)
Same analysis from SHORT perspective.

**Output file:** `feature_distributions_short_good_vs_bad.png`

### Cell 13: Equity Curve Analysis
Placeholder for future implementation requiring trained model predictions.

Template provided (commented) for:
- Loading trained models
- Generating predictions on fold test sets
- Plotting equity curves with regime markers
- Identifying regime switches

### Cell 14: Diagnosis Summary
Markdown template with sections for:

1. **Key Findings**
   - Volatility patterns
   - Trend strength impact
   - Directional alignment effects
   - Persistence characteristics
   - H1 context influence

2. **Top 3 Regime Features**
   - LONG perspective (ranked by significance)
   - SHORT perspective (ranked by significance)

3. **Verdict**
   - Root cause of fold failures
   - Strategy-regime mismatch explanation
   - Why Fold 1 is problematic

4. **Next Steps**
   - Regime detection
   - Ensemble approaches
   - Fold-specific models
   - Feature engineering
   - Dynamic thresholds

### Cell 15: Session Summary
Prints output directory and generated files.

## Generated Outputs

All files saved to `outputs/phase2_fold_diagnosis/`:

| File | Purpose |
|------|---------|
| `fold_overview_chart.png` | Price chart with fold overlays |
| `fold_regime_stats.csv` | Per-fold statistics |
| `long_good_vs_bad_comparison.csv` | LONG: good vs bad metrics |
| `short_good_vs_bad_comparison.csv` | SHORT: good vs bad metrics |
| `feature_distributions_long_good_vs_bad.png` | LONG: feature distributions |
| `feature_distributions_short_good_vs_bad.png` | SHORT: feature distributions |

## Key Metrics Used

### Volatility Indicators
- **ATR (M5):** 5-minute Average True Range, scaled
- **Bollinger Band Width:** Distance between upper/lower bands

### Trend Strength
- **ADX (M5):** Average Directional Index (0-100, >25 = strong trend)

### Directional Alignment
- **MTF Alignment Score:** Multi-timeframe alignment (-1 to 1, >0.2 = strong bull, <-0.2 = strong bear)
- **MTF Alignment Duration:** How long current alignment has persisted (bars)

### Price Action
- **RSI (M5):** Relative Strength Index (0-100, >70 = overbought, <30 = oversold)
- **Distance to Moving Averages:** Bull/bear bias indicators

### Macro Context
- **H1 SMA 200 Slope:** Hourly trend direction and strength

## Usage Instructions

### 1. Run the notebook end-to-end
```bash
jupyter notebook notebooks/04_fold_regime_diagnosis.ipynb
```

### 2. Review generated files
- Check `fold_overview_chart.png` for visual regime patterns
- Examine CSV files for specific metrics
- Look at distribution plots for feature overlap

### 3. Complete the Diagnosis Summary
In Cell 14, fill in the template based on:
- Visual inspection of charts
- CSV statistics
- Mann-Whitney test results
- Distribution overlays

### 4. Interpret findings
Consider:
- Which features most strongly predict good/bad fold performance?
- Are there clear regime thresholds?
- Do good LONG folds have common characteristics?
- Do good SHORT folds differ from good LONG folds?

## Expected Findings

Based on preliminary analysis, we may discover:

**For LONG Failures (Folds 1, 4):**
- Higher volatility or lower trend strength
- Strong bear alignment or persistent downtrends
- Lower win rates in historical labels

**For SHORT Failures (Folds 1, 3, 5):**
- Strong bull alignment or persistent uptrends
- High directional conviction
- Structural uptrend in H1 context

**Fold 1 (Consistently Bad):**
- Likely choppy, mean-reverting period
- High volatility, low trend
- Mixed alignment (no clear direction)

## Next Phase (Phase 3)

Findings from this analysis inform:

1. **Regime Detection System:** Real-time classification of current market regime
2. **Adaptive Trading:** Switch thresholds or models based on regime
3. **Ensemble Methods:** Weight models by regime fitness
4. **Feature Engineering:** Create regime interaction features
5. **Separate Models:** Train regime-specific classifiers

## Technical Notes

- Uses `scipy.stats.mannwhitneyu` for non-parametric significance testing
- Density normalization in histograms enables fair feature comparison across different scales
- Fold boundaries exactly match `src/cv.py` PurgedWalkForward logic
- All calculations exclude NaN values
- Graphs use consistent color scheme: green=good, red=bad

## Troubleshooting

**Issue:** Missing columns error
- **Solution:** Verify data includes all 44 features from CSV header

**Issue:** Empty fold data
- **Solution:** Check that timestamp filter in Cell 2 includes all train/CV period

**Issue:** Distribution plots overlap too much
- **Solution:** Consider log scale for right-skewed features like ATR

**Issue:** Statistical tests not significant
- **Solution:** This is valid - not all features differentiate good/bad folds equally

## References

- Phase 2 Results: `notebooks/outputs/phase2_decision/`
- Label definitions: `src/labels.py`
- CV implementation: `src/cv.py`
- Feature columns: `src/features.py`

---

**Created:** 2025-04-15
**Status:** Complete and ready for interactive analysis
**Dependencies:** pandas, numpy, matplotlib, seaborn, scipy
