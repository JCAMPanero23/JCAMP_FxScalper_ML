# Phase 2 Fold Regime Diagnosis - Output Files

This directory contains outputs from the fold regime diagnosis analysis (`notebooks/04_fold_regime_diagnosis.ipynb`).

## Generated Files

### Charts (PNG)

#### `fold_overview_chart.png`
Visual timeline of all 5 folds with price action.
- Black line: Synthetic price (cumsum of bar0_body × atr_m5)
- **Green shaded areas:** Folds where LONG model performs well
- **Red shaded areas:** Folds where LONG model performs poorly
- Labels show both LONG and SHORT status for each fold
- Useful for quick visual assessment of regime patterns

**Size:** ~300 KB, Resolution: 150 DPI

#### `feature_distributions_long_good_vs_bad.png`
Histogram comparison of key features for good vs bad LONG folds.
- 5 subplots: atr_m5, adx_m5, bb_width, mtf_alignment_score, rsi_m5
- **Green histogram:** Good LONG folds (2, 3, 5)
- **Red histogram:** Bad LONG folds (1, 4)
- Density normalized for fair comparison
- Shows feature overlap and separation

**Size:** ~400 KB, Resolution: 150 DPI

#### `feature_distributions_short_good_vs_bad.png`
Same as above but for SHORT direction.
- **Green histogram:** Good SHORT folds (2, 4)
- **Red histogram:** Bad SHORT folds (1, 3, 5)

**Size:** ~400 KB, Resolution: 150 DPI

### Data Tables (CSV)

#### `fold_regime_stats.csv`
Comprehensive regime statistics for each fold.

**Columns:**
```
fold                      : Fold number (1-5)
atr_mean                  : Average volatility (M5)
atr_std                   : Volatility variation
atr_p90                   : 90th percentile volatility
bb_width_mean             : Average Bollinger Band width
adx_mean                  : Average trend strength
adx_above_25_pct          : % bars with strong trend (ADX > 25)
bull_aligned_pct          : % bars with bull alignment (score > 0.2)
bear_aligned_pct          : % bars with bear alignment (score < -0.2)
mixed_pct                 : % bars in neutral zone (-0.2 to 0.2)
avg_alignment_run         : Average persistence of alignment
flips_per_1000bar         : Regime change frequency (lower = more persistent)
h1_slope_mean             : Average direction of H1 SMA 200
h1_slope_std              : Variability in H1 trend
win_long                  : Number of winning LONG trades
loss_long                 : Number of losing LONG trades
timeout_long              : Number of LONG timeouts
win_rate_long             : Win % for LONG labels
win_short                 : Number of winning SHORT trades
loss_short                : Number of losing SHORT trades
timeout_short             : Number of SHORT timeouts
win_rate_short            : Win % for SHORT labels
```

**Usage:** Compare rows to identify regime differences between good/bad folds.

#### `long_good_vs_bad_comparison.csv`
Metric comparison for LONG direction.

**Columns:**
```
metric        : Feature name
good_mean     : Mean value in good LONG folds (2,3,5)
bad_mean      : Mean value in bad LONG folds (1,4)
pct_diff      : Percentage difference [(bad-good)/good × 100]
abs_diff      : Absolute difference (bad-good)
```

**Sorted by:** Largest absolute % difference (most discriminative features first)

**Usage:** Identify which metrics most strongly distinguish good from bad LONG folds.

#### `short_good_vs_bad_comparison.csv`
Same analysis for SHORT direction.

**Columns:** Same as long_good_vs_bad_comparison.csv
**Good SHORT folds:** 2, 4
**Bad SHORT folds:** 1, 3, 5

### Analysis Process

1. **Load data:** Train/CV set (204,105 bars, Jan 2023 - Sep 2025)
2. **Reconstruct folds:** Match Phase 2 walk-forward CV boundaries
3. **Tag rows:** Assign fold number and performance status to each bar
4. **Compute statistics:** Per-fold regime metrics
5. **Compare good vs bad:** Identify differentiating features
6. **Statistical testing:** Mann-Whitney U tests for significance
7. **Visualize:** Distribution overlays and price charts

## Key Metrics Explained

### Volatility
- **ATR:** Average True Range (scaled). Higher = more volatile
- **BB Width:** Bollinger Band width. Higher = wider bands = more volatility

### Trend
- **ADX:** Average Directional Index (0-100). >25 indicates strong trend

### Direction
- **MTF Alignment Score:** Multi-timeframe alignment (-1 to 1)
  - Positive (>0.2): Bull aligned
  - Negative (<-0.2): Bear aligned
  - Near 0: Mixed/choppy

### Persistence
- **Alignment Duration:** How many bars the current alignment persists
- **Flips per 1000 bars:** How often alignment direction changes

### Context
- **H1 SMA 200 Slope:** Hourly trend direction (positive = uptrend, negative = downtrend)

## How to Use

### 1. Quick Assessment
- Open `fold_overview_chart.png` first
- Look for visual patterns in good vs bad periods
- Note color patterns and regime transitions

### 2. Statistical Review
- Open `fold_regime_stats.csv`
- Compare metrics across folds
- Look for obvious differences in good vs bad folds

### 3. Detailed Analysis
- Review `long_good_vs_bad_comparison.csv` and `short_good_vs_bad_comparison.csv`
- Top rows show most discriminative features
- Examine percentage differences
- Identify clear thresholds if visible

### 4. Distribution Inspection
- Review `feature_distributions_long_good_vs_bad.png` and `feature_distributions_short_good_vs_bad.png`
- Check for clean separation between good/bad folds
- Identify overlap regions

### 5. Complete Diagnosis Summary
- Use findings to fill in Cell 14 of the notebook
- Write observations about regime characteristics
- List top 3 features per direction
- Provide conclusions and next steps

## Expected Insights

Typical findings from this analysis:

1. **Fold 1 failures:** Often caused by choppy, non-trending market (low ADX, mixed alignment)
2. **Direction-specific failures:** SHORT struggles in strong uptrends, LONG struggles in downtrends
3. **Volatility impact:** Extreme volatility may challenge both directions
4. **Persistence matters:** High flip frequency indicates regime instability
5. **H1 context:** Hourly trend direction provides important macro context

## Interpretation Examples

**High % difference in ATR for LONG comparison:**
- Bad LONG folds have higher volatility
- Implication: LONG model struggles with choppy/volatile markets

**Low ADX percentage for SHORT bad folds:**
- Bad SHORT folds have weak trends
- Implication: SHORT model needs trend confirmation

**High bull_aligned_pct in LONG good folds:**
- Good LONG folds have strong bull alignment
- Implication: Model works well with aligned uptrends

## Troubleshooting

**Q: Why are some metrics NaN?**
- A: Missing columns in source data. Check that all 44 features exist.

**Q: Distribution plots look identical:**
- A: Feature may not differentiate good/bad folds - not significant for fold performance.

**Q: Mann-Whitney p-values all > 0.05:**
- A: Valid finding - those features don't significantly differ between good/bad folds.

**Q: Folds don't match my understanding:**
- A: Verify fold_regime_stats.csv fold column matches expectation.

## References

- Notebook: `notebooks/04_fold_regime_diagnosis.ipynb`
- Implementation guide: `FOLD_DIAGNOSIS_GUIDE.md`
- Phase 2 results: `notebooks/outputs/phase2_decision/`
- Data source: `data/DataCollector_EURUSD_M5_20230101_220400.csv`

---

**Generated:** 2025-04-15
**Analysis Version:** 1.0
**Data Period:** Jan 2023 - Sep 2025 (Train/CV set)
