# Phase 2 Fold Regime Diagnosis Results

**Date:** April 16, 2026
**Notebook:** `notebooks/04_fold_regime_diagnosis.ipynb`
**Purpose:** Diagnose why specific folds fail — identify regime characteristics that distinguish good folds from bad.

---

## Executive Summary

The fold regime diagnosis revealed a **surprising finding**: the LONG model fails in MORE bullish regimes, not less. This indicates the model is chasing late entries rather than catching quality setups. The SHORT model fails predictably in uptrending markets.

**Root Cause:** The model lacks a **regime quality filter** — it trades all directionally-aligned setups equally, whether fresh or stale.

**Top Discriminators Identified:**
- `mtf_alignment_duration` — strongest for both directions
- `slope_sma_h1_200` — critical for SHORT success
- `mtf_alignment_score` — direction matters, but quality matters more

---

## Data Summary

| Metric | Value |
|--------|-------|
| Dataset | EURUSD M5, 244,482 bars |
| Analysis Period | Jan 2023 - Sep 2025 (Train/CV) |
| Bars Analyzed | 204,105 (train/CV portion) |
| Folds | 5 (walk-forward CV) |
| Test Size per Fold | ~6,100 bars (~15%) |
| Reference Threshold | 0.55 |

---

## Fold Status Reference

| Fold | Period | LONG | SHORT | Characterization |
|------|--------|------|-------|------------------|
| 1 | Jan-Mar 2023 | Bad | Bad | High vol, mixed alignment |
| 2 | Mar-Jun 2023 | Good | Good | Low vol, bearish aligned |
| 3 | Jun-Sep 2023 | Good | Bad | Low vol, bullish aligned |
| 4 | Sep-Dec 2023 | Bad | Good | Med vol, balanced |
| 5 | Dec 2023 - Sep 2025 | Good | Bad | High vol, bullish aligned |

---

## Per-Fold Regime Statistics

### Volatility Metrics

| Fold | ATR Mean | ATR Std | ATR P90 | BB Width |
|------|----------|---------|---------|----------|
| 1 | 0.000476 | 0.000261 | 0.000792 | 4.25 |
| 2 | 0.000361 | 0.000204 | 0.000612 | 4.63 |
| 3 | 0.000252 | 0.000140 | 0.000420 | 4.44 |
| 4 | 0.000290 | 0.000184 | 0.000484 | 4.50 |
| 5 | 0.000615 | 0.000453 | 0.001215 | 4.57 |

**Observation:** Fold 5 has significantly higher volatility (ATR 2x other folds).

### Trend Metrics

| Fold | ADX Mean | ADX > 25 % | Bull Aligned % | Bear Aligned % | Mixed % |
|------|----------|------------|----------------|----------------|---------|
| 1 | 24.9 | 40.5% | 42.4% | 13.3% | 44.4% |
| 2 | 24.4 | 40.8% | 8.6% | 49.9% | 41.5% |
| 3 | 23.1 | 33.5% | 42.9% | 13.5% | 43.6% |
| 4 | 24.1 | 37.4% | 30.0% | 28.4% | 41.5% |
| 5 | 24.8 | 41.4% | 34.4% | 24.0% | 41.5% |

**Observation:** Fold 2 (both good) has strongest bear alignment (50%). Folds 1 and 3 have strongest bull alignment (~43%).

### Persistence Metrics

| Fold | Avg Alignment Run | Flips per 1000 bars |
|------|-------------------|---------------------|
| 1 | 52.2 | 1.14 |
| 2 | 55.6 | 1.63 |
| 3 | 52.1 | 3.10 |
| 4 | 52.1 | 0.81 |
| 5 | 51.2 | 4.40 |

**Observation:** Fold 5 has highest flip rate (4.4 per 1000 bars) — more choppy.

### Win Rates

| Fold | LONG Win % | SHORT Win % | LONG Status | SHORT Status |
|------|------------|-------------|-------------|--------------|
| 1 | 34.9% | 31.0% | Bad | Bad |
| 2 | 29.5% | 34.6% | Good | Good |
| 3 | 33.9% | 30.0% | Good | Bad |
| 4 | 32.6% | 32.5% | Bad | Good |
| 5 | 34.3% | 31.5% | Good | Bad |

**Note:** Win rate alone doesn't explain fold performance — expectancy (R-multiples) is what matters.

---

## LONG Model Analysis

### Good vs Bad Fold Comparison

**Good LONG folds:** 2, 3, 5 (18,360 bars)
**Bad LONG folds:** 1, 4 (12,240 bars)

| Feature | Good Mean | Bad Mean | % Difference | Interpretation |
|---------|-----------|----------|--------------|----------------|
| `mtf_alignment_score` | -0.044 | **+0.608** | +1469% | Bad folds MORE bullish |
| `mtf_alignment_duration` | -1.51 | **+11.50** | +860% | Longer bull persistence in bad |
| `dist_sma_m5_200` | -0.186 | +0.331 | +278% | Price above SMA in bad |
| `slope_sma_h1_200` | ~0 | +0.00013 | +238% | H1 uptrend in bad folds |
| `atr_m5` | 0.000409 | 0.000383 | -6.4% | Slightly lower vol in bad |
| `bb_width` | 4.55 | 4.38 | -3.8% | Similar |
| `adx_m5` | 24.08 | 24.47 | +1.6% | Similar |
| `rsi_m5` | 50.37 | 50.54 | +0.3% | Similar |

### Key Insight: LONG Fails in Bullish Regimes

**Counterintuitive finding:** The LONG model performs WORSE when the market is MORE bullish.

**Why this happens:**
1. Model enters too late in established trends (chasing)
2. Bullish MTF alignment doesn't distinguish fresh vs stale setups
3. High alignment duration = trend is mature, reversals more likely
4. Model lacks entry timing quality filter

**What the model needs:**
- Detect FRESH bullish flips vs STALE bullish persistence
- H1 slope as context (is macro trend starting or ending?)
- Alignment freshness feature (bars since alignment established)

---

## SHORT Model Analysis

### Good vs Bad Fold Comparison

**Good SHORT folds:** 2, 4 (12,240 bars)
**Bad SHORT folds:** 1, 3, 5 (18,360 bars)

| Feature | Good Mean | Bad Mean | % Difference | Interpretation |
|---------|-----------|----------|--------------|----------------|
| `slope_sma_h1_200` | -0.00005 | **+0.00015** | +428% | H1 uptrend kills shorts |
| `mtf_alignment_score` | -0.913 | **+0.970** | +206% | Bullish alignment = bad |
| `mtf_alignment_duration` | -23.18 | **+21.61** | +193% | Bull persistence = bad |
| `dist_sma_m5_200` | -1.178 | +0.821 | +170% | Price position matters |
| `atr_m5` | 0.000326 | 0.000447 | +37% | Higher vol in bad folds |
| `di_minus_m5` | 22.57 | 21.63 | -4.2% | Lower -DI in bad folds |
| `bb_width` | 4.56 | 4.42 | -3.0% | Similar |
| `rsi_m5` | 49.77 | 50.89 | +2.2% | Slightly higher in bad |
| `adx_m5` | 24.23 | 24.24 | +0.1% | No difference |

### Key Insight: SHORT Fails in Uptrends (Expected)

**Expected finding:** SHORT model cannot profitably short in bullish-aligned, uptrending markets.

**Key discriminators:**
1. `slope_sma_h1_200` is MOST important — H1 trend direction determines SHORT success
2. Positive MTF alignment = don't short
3. High volatility periods correlate with bad SHORT performance

**What the model needs:**
- H1 slope regime filter (no shorts when H1 slope > threshold)
- Require bear alignment before shorting
- Volatility-adjusted position sizing

---

## Statistical Significance

### Mann-Whitney U Test Results (p-values)

| Feature | LONG p-value | SHORT p-value | Significance |
|---------|--------------|---------------|--------------|
| `mtf_alignment_score` | < 0.001 | < 0.001 | *** |
| `mtf_alignment_duration` | < 0.001 | < 0.001 | *** |
| `slope_sma_h1_200` | < 0.001 | < 0.001 | *** |
| `atr_m5` | < 0.001 | < 0.001 | *** |
| `adx_m5` | < 0.001 | 0.89 | LONG only |
| `rsi_m5` | < 0.001 | < 0.001 | *** |

**Note:** With 200k+ bars, statistical significance is easy to achieve. Focus on effect size (% difference) not just p-values.

---

## Root Cause Summary

### What the Models Can See
- Direction (MTF alignment score)
- Persistence (alignment duration)
- Volatility (ATR, BB width)
- Trend strength (ADX)

### What the Models Cannot See
- **Regime quality** — Is this a clean trend or choppy?
- **Entry timing** — Fresh setup or stale/exhausted?
- **Macro context** — Where are we in the H1/H4 cycle?
- **Trend maturity** — Early trend or late reversal risk?

### Core Problem
The model trades ALL directionally-aligned setups equally. It doesn't distinguish:
- Fresh flips (high probability) from stale persistence (lower probability)
- Early trends (room to run) from mature trends (reversal risk)
- Clean trends (good R:R) from choppy trends (stop hunts)

---

## Recommended Regime Features

Based on this diagnosis, add these features to the model:

### 1. H1 Slope Regime (Categorical)
```
h1_slope_regime:
  - 'up' if slope_sma_h1_200 > +0.0001
  - 'down' if slope_sma_h1_200 < -0.0001
  - 'flat' otherwise
```
**Purpose:** Gate SHORT trades when H1 regime is 'up'.

### 2. Alignment Freshness (Numeric)
```
alignment_freshness = 200 - abs(mtf_alignment_duration)
```
**Purpose:** Higher values = fresher alignment = better entry quality.

### 3. Trend Maturity (Categorical)
```
trend_maturity:
  - 'early' if alignment_duration < 50
  - 'mid' if 50 <= alignment_duration < 150
  - 'late' if alignment_duration >= 150
```
**Purpose:** Avoid late entries in mature trends.

### 4. Regime Volatility Percentile (Numeric)
```
regime_vol_pct = rolling_percentile(atr_m5, window=2000)
```
**Purpose:** Context-aware position sizing, avoid trading extreme vol.

---

## Files Generated

| File | Description |
|------|-------------|
| `outputs/phase2_fold_diagnosis/fold_overview_chart.png` | Price chart with fold overlays |
| `outputs/phase2_fold_diagnosis/fold_regime_stats.csv` | 21 metrics per fold |
| `outputs/phase2_fold_diagnosis/long_good_vs_bad_comparison.csv` | LONG regime analysis |
| `outputs/phase2_fold_diagnosis/short_good_vs_bad_comparison.csv` | SHORT regime analysis |
| `outputs/phase2_fold_diagnosis/feature_distributions_long_good_vs_bad.png` | LONG distribution overlays |
| `outputs/phase2_fold_diagnosis/feature_distributions_short_good_vs_bad.png` | SHORT distribution overlays |

---

## Next Steps

1. **Create regime feature spec** — Define exact calculations for recommended features
2. **Update DataCollector** — Add new features to v0.4
3. **Re-run walk-forward CV** — Test if regime features improve fold consistency
4. **Target:** Achieve 4/5 positive folds for LONG, 3/5 for SHORT

---

## Conclusion

The fold regime diagnosis successfully identified WHY the model fails in specific periods:

- **LONG** fails because it chases late entries in established bullish trends
- **SHORT** fails because it shorts against bullish H1 macro trends
- **Both** lack regime quality filters to distinguish good vs bad setups

The path forward is clear: add regime gating features that capture setup quality, not just direction.
