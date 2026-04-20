# Feature Skew Diagnostic Report
**Date:** 2026-04-20  
**Project:** JCAMP_FxScalper_ML Phase 4  
**Status:** ⚠️ CRITICAL - Feature Divergence Detected

---

## Executive Summary

A critical feature skew was detected when comparing DataCollector and FxScalper_ML computed features. The two systems are producing **significantly different values** for the same bars, indicating a **data alignment or synchronization issue** at the collection level.

**Max Difference:** 200 (bars_since_tf_fast_flip, mtf_alignment_duration)  
**Mean Difference:** 1.84 pips across all 46 features  
**Tolerance:** 1e-06 (floating point precision)  
**Result:** ❌ FAIL

---

## Test Configuration

| Metric | Value |
|--------|-------|
| Test Period | Jan 1, 2024 EURUSD M5 |
| Bars Tested | 6,260 |
| Features Evaluated | 46 |
| Total Comparisons | 287,960 values |
| CSV-A (DataCollector) | DataCollector_EURUSD_M5_20240101_220000.csv |
| CSV-B (FxScalper_ML) | FxScalper_features_debug_20240101-20-04-2026.csv |

---

## Findings

### 1. Feature Category Impact Analysis

| Category | Max Diff | Mean Diff | Affected % | Severity |
|----------|----------|-----------|------------|----------|
| SMA Distance | 70.87 | 2.67 | 100.0% | 🔴 CRITICAL |
| Momentum (RSI/ADX) | 44.25 | 4.98 | 100.0% | 🔴 CRITICAL |
| Bar Patterns | 5.86 | 0.53 | 99.8% | 🔴 CRITICAL |
| Swing Levels | 23.66 | 1.82 | 99.9% | 🔴 CRITICAL |
| Volatility (ATR/BB) | 12.12 | 0.27 | 99.0% | 🔴 CRITICAL |
| Slopes | 0.00017 | 0.000013 | 100.0% | 🟡 MINOR |
| Other | 2.00 | 0.095 | 68.3% | 🟡 MODERATE |
| Time/Session | 23.00 | 0.50 | 18.6% | 🟢 LOW |
| MTF Features | 200.00 | 4.10 | 28.5% | 🟡 MODERATE |

**Key Observation:** Core technical indicators (SMA, RSI, ADX) show 100% affection, while time-based features (hour_utc, dow) show only 18.6% difference, suggesting **positional misalignment** rather than calculation error.

---

### 2. Critical Discovery: Alternating Row Pattern

Analysis of row-by-row differences reveals a **repeating pattern** suggesting CSV misalignment:

#### Example: RSI_M5 Values

```
Row 0: DC=65.49,  FS=70.99  (different)
Row 1: DC=63.35,  FS=63.35  (MATCH ✓)
Row 2: DC=70.99,  FS=65.49  (SWAPPED with row 0!)
Row 3: DC=65.76,  FS=65.76  (MATCH ✓)
Row 4: DC=47.93,  FS=68.40  (different)
Row 5: DC=47.93,  FS=69.66  (different)
Row 6: DC=68.40,  FS=70.67  (different)
Row 7: DC=69.66,  FS=47.93  (swapped with row 5!)
Row 8: DC=70.67,  FS=47.93  (shifted?)
Row 9: DC=41.50,  FS=41.50  (MATCH ✓)
```

#### Example: dist_sma_m5_200 Values

```
Row 0: DC=-4.7917, FS=-4.4673
Row 1: DC=-5.3613, FS=-5.3613 (MATCH ✓)
Row 2: DC=-4.4673, FS=-4.7917 (SWAPPED!)
Row 3: DC=-4.6910, FS=-4.6910 (MATCH ✓)
Row 4: DC=-5.3752, FS=-4.0933
```

**Pattern Interpretation:**
- Some rows match perfectly (rows 1, 3, 9)
- Other rows show **exact value swaps** with adjacent rows
- Some rows contain completely different values
- The pattern is irregular, not a simple N-bar offset

This is **NOT** a simple off-by-N bars error. The data appears to be **out of temporal sync at the row level**.

---

### 3. Hypothesis Testing

#### A. Simple Bar Offset Hypothesis ❌ REJECTED

Tested whether CSVs are offset by N bars:
- Offset 1 bar: max_diff = 200 ✗
- Offset 5 bars: max_diff = 200 ✗
- Offset 10 bars: max_diff = 200 ✗
- Offset 20 bars: max_diff = 200 ✗
- Offset 50 bars: max_diff = 200 ✗

**Conclusion:** Not a simple N-bar shift.

#### B. Partial Row Mismatch Hypothesis ⚠️ POSSIBLE

Some rows (1, 3, 9) match perfectly while others (0, 2, 4-8) diverge. This suggests:
- The CSVs may have been collected at different sampling rates
- One source may skip bars while the other doesn't
- The synchronization may be at the minute level, not the bar level
- Bar indices may be calculated differently (e.g., including/excluding pre-market bars)

---

### 4. Detailed Feature-Level Analysis

#### 4.1 Largest Individual Differences

| Feature | Max Diff | Example Row | DC Value | FS Value |
|---------|----------|-------------|----------|----------|
| bars_since_tf_fast_flip | 200.00 | 10 | 200.00 | 200.00 |
| mtf_alignment_duration | 200.00 | 11 | 200.00 | 200.00 |
| dist_sma_h4_200 | 70.87 | 4 | 54.96 | 64.22 |
| rsi_m5 | 44.25 | 4 | 47.93 | 68.40 |
| dist_swing_high | 23.66 | 5 | 2.72 | 0.53 |
| dist_sma_h1_200 | 41.39 | 4 | 10.20 | 13.64 |
| adx_m5 | 42.59 | 4 | 39.73 | 41.54 |

#### 4.2 Features with No Difference (Match Perfectly)

- `slope_sma_m5_200` (max diff: 1.74e-04)
- `slope_sma_h1_200` (max diff: 1.12e-04)
- Some instances of `hour_utc`, `dow`, `sess_*` flags
- Some instances of `atr_m5`, `atr_m15`, `atr_h1`

**Insight:** Features that sometimes match suggest the **shared FeatureComputer class works correctly when data is aligned**, but the CSVs themselves are misaligned.

---

## Root Cause Analysis

### Most Likely Causes (in order of probability)

#### 1. **Bar Collection Frequency Mismatch** 🔴 HIGH PROBABILITY
- **Symptom:** Alternating rows match, others don't
- **Mechanism:** One CSV logs every bar, the other logs selected bars (e.g., at 5-minute intervals)
- **Evidence:** Row 1 matches, row 2 doesn't, row 3 matches pattern continues
- **Impact:** Makes train/serve consistency impossible

#### 2. **Temporal Synchronization Issue** 🔴 HIGH PROBABILITY
- **Symptom:** Some values swapped between adjacent rows
- **Mechanism:** CSVs created at different times, market hours, or timezone interpretations
- **Evidence:** Perfect matches at rows 1, 3, 9 suggest occasional sync, then drift
- **Impact:** Model will see training data that differs from live trading data

#### 3. **Bar Indexing Calculation** 🟡 MEDIUM PROBABILITY
- **Symptom:** Consistent off-by-N pattern in some features
- **Mechanism:** DataCollector and FxScalper_ML differ in how they count bars (e.g., including gaps, pre-market, etc.)
- **Evidence:** Some indicator features match (slopes) while others don't (RSI)
- **Impact:** Would require code alignment in both systems

#### 4. **Data Collection Timing** 🟡 MEDIUM PROBABILITY
- **Symptom:** Matches on certain rows but not others
- **Mechanism:** One system starts logging before the other, or resynchronizes at intervals
- **Evidence:** MTF features 28.5% match, time features 18.6% match
- **Impact:** Window of misalignment, but data eventually synchronizes

---

## Implications

### For Training
- ❌ **Cannot use misaligned data for training**
- Misaligned training data → model learns incorrect patterns
- Train/test split becomes meaningless if train and test data are from different time axes
- CV folds would have overlapping bar times despite appearing sequential

### For Live Trading
- ❌ **Live features will NOT match training features**
- Even if model trained successfully, live features computed by FxScalper_ML will diverge from expected inputs
- Will cause prediction degradation or errors
- **Train/Serve Inconsistency = GUARANTEED PERFORMANCE DEGRADATION**

### For Model Reliability
- Even if model achieves good backtest performance, it will fail in production
- The feature divergence suggests data integrity issues upstream

---

## Recommended Actions

### Immediate (Priority 1)

1. **Compare OHLC Timestamps**
   ```python
   # Check if timestamps align between DataCollector and FxScalper outputs
   # Extract time column and compare row-by-row
   ```
   - Do rows represent the same bar times?
   - Are there gaps or duplicates?

2. **Verify Data Collection Timing**
   - When was DataCollector CSV generated?
   - When was FxScalper_ML CSV generated?
   - Were they simultaneous or sequential?

3. **Check Bar Filtering Logic**
   - Does DataCollector filter bars? (e.g., only trade session hours?)
   - Does FxScalper_ML filter bars?
   - Are they using identical bar selection criteria?

### Short-term (Priority 2)

4. **Regenerate Fresh CSVs**
   - Run DataCollector on the same bar sequence
   - Run FxScalper_ML on the same bar sequence
   - Ensure both start and end at the same bar times

5. **Create Synchronized Test**
   - Feed identical OHLC data to both systems
   - Log features in real-time (not batch)
   - Ensure tick-for-tick synchronization

6. **Audit Bar Indexing**
   - Compare `closedBarIdx` calculation in both systems
   - Verify SMA lookback periods are identical
   - Check indicator warmup logic

### Long-term (Priority 3)

7. **Implement Sanity Checks**
   - Add feature validation before model prediction
   - Log feature values in live trading
   - Compare live features vs expected ranges from training

8. **Establish Monitoring**
   - Alert if live features diverge from training distribution
   - Track feature skew metrics over time
   - Implement feature drift detection

---

## Diagnostic Scripts

Two diagnostic scripts were created:

1. **compare_feature_skew.py**
   - Compares 46 features across 6,260 bars
   - Identifies which features exceed tolerance
   - Status: ❌ FAIL (200 pips max difference)

2. **diagnose_feature_skew.py**
   - Provides detailed row-by-row analysis
   - Shows category-level impact
   - Tests offset hypotheses
   - Reveals alternating row pattern

Both scripts are located in `.worktrees/phase4-cbot/`

---

## Data References

| File | Size | Created | Rows | Columns |
|------|------|---------|------|---------|
| DataCollector_EURUSD_M5_20240101_220000.csv | 2.9M | Apr 20 19:40 | 6,260 | ~50 |
| FxScalper_features_debug_20240101-20-04-2026.csv | 4.4M | Apr 20 19:58 | 6,260 | ~50 |

---

## Conclusion

The feature skew comparison **FAILED** due to significant misalignment between DataCollector and FxScalper_ML outputs. The pattern suggests **temporal desynchronization at the bar level** rather than calculation errors in the FeatureComputer class.

**Do not proceed with Phase 4 deployment until this is resolved.** Using misaligned training data will result in a model that performs well in backtests but fails catastrophically in live trading.

**Next step:** Investigate data collection timing and bar synchronization before regenerating features.

---

## Appendix: Full Feature Difference Report

### Features with max_diff > 1.0

```
dist_sma_m5_50                : max diff = 9.80
dist_sma_m5_100               : max diff = 14.38
dist_sma_m5_200               : max diff = 16.61
dist_sma_m5_275               : max diff = 22.79
dist_sma_m15_200              : max diff = 30.22
dist_sma_m30_200              : max diff = 42.98
dist_sma_h1_200               : max diff = 41.39
dist_sma_h4_200               : max diff = 70.87
rsi_m5                        : max diff = 44.25
rsi_m15                       : max diff = 34.64
rsi_m30                       : max diff = 32.46
adx_m5                        : max diff = 42.59
di_plus_m5                    : max diff = 30.42
di_minus_m5                   : max diff = 35.53
atr_ratio_m5_h1               : max diff = 0.93
bb_width                      : max diff = 12.12
bar0_body                     : max diff = 4.93
bar0_range                    : max diff = 3.75
bar1_body                     : max diff = 4.27
bar1_range                    : max diff = 5.86
bar2_body                     : max diff = 4.15
bar2_range                    : max diff = 5.46
bar3_body                     : max diff = 4.42
bar3_range                    : max diff = 4.85
bar4_body                     : max diff = 4.68
bar4_range                    : max diff = 4.15
dist_swing_high               : max diff = 23.66
dist_swing_low                : max diff = 17.41
hour_utc                      : max diff = 23.00
dow                           : max diff = 5.00
sess_asia                     : max diff = 1.00
sess_london                   : max diff = 1.00
sess_ny                       : max diff = 1.00
mtf_alignment_score           : max diff = 8.00
mtf_stacking_score            : max diff = 4.00
bars_since_tf_fast_flip       : max diff = 200.00
tf_fast_flip_direction        : max diff = 2.00
mtf_alignment_duration        : max diff = 200.00
atr_percentile_2000bar        : max diff = 0.91
h1_alignment_agreement        : max diff = 2.00
```

### Features with max_diff < 0.001

```
slope_sma_m5_200              : max diff = 1.74e-04
slope_sma_h1_200              : max diff = 1.12e-04
atr_m5                        : max diff = 1.08e-03
atr_m15                       : max diff = 1.14e-03
atr_h1                        : max diff = 9.23e-04
spread_pips                   : ~0 (mostly match)
```

---

**Report Generated:** 2026-04-20  
**Analysis Tool:** diagnose_feature_skew.py  
**Status:** ⚠️ CRITICAL - Action Required
