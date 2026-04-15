# Notebook 04 — Fold Regime Diagnosis

**Purpose:** Determine whether the consistent failure of specific folds (LONG-4, SHORT-5, LONG-1) is regime-driven, and identify which regime characteristics distinguish good folds from bad ones.

**Output:** A clear answer to: *"What is structurally different about the periods where the model fails?"*

**Time budget:** 2-3 hours including running. Don't over-engineer this. The goal is diagnosis, not polish.

---

## Predictions (write these BEFORE running anything)

This step matters. Without a written prediction, you can rationalize any result.

Open a markdown cell at the top of the notebook and write your honest guesses for:

1. **What was EURUSD doing in Fold 4 (LONG bad)?** (chop / strong trend / reversal / low-vol grind / shock)
2. **What was EURUSD doing in Fold 5 (SHORT bad)?**
3. **Why might LONG fail but SHORT work in the same periods (or vice versa)?**
4. **Which feature do you predict will show the biggest distribution shift between good and bad folds?**

After running the notebook, come back and grade yourself. If you were right, you understand the system. If you were wrong, you've learned something — write down what.

---

## Setup

### Cell 1: Imports and load

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from pathlib import Path

# Match the conventions used in 03_walk_forward
DATA_PATH = Path("../data/DataCollector_EURUSD_M5_20230101_220400.csv")
OUTPUT_DIR = Path("../notebooks/outputs/phase2_fold_diagnosis")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(DATA_PATH, parse_dates=['timestamp'])
df = df.sort_values('timestamp').reset_index(drop=True)
print(f"Loaded {len(df):,} rows from {df.timestamp.min()} to {df.timestamp.max()}")
```

### Cell 2: Reconstruct the fold boundaries

You need to know exactly which calendar dates belong to each fold. Reproduce the same split logic from your CV code (`src/cv.py`). If your `PurgedWalkForward` uses `n_splits=5` over the train/CV portion (Jan 2023 - Sep 2025, ~204k rows), the folds are roughly:

```python
# Filter to train/CV window only (must match what walk-forward used)
train_cv_end = pd.Timestamp('2025-09-30 23:59:59')
df_cv = df[df.timestamp <= train_cv_end].reset_index(drop=True)
n_rows = len(df_cv)
n_splits = 5

# Each fold's TEST window (this is what walk-forward evaluates on)
# Walk-forward: training expands, test slides forward
fold_size = n_rows // (n_splits + 1)  # +1 because first chunk is min train

fold_boundaries = []
for i in range(n_splits):
    test_start_idx = (i + 1) * fold_size
    test_end_idx   = (i + 2) * fold_size if i < n_splits - 1 else n_rows
    fold_boundaries.append({
        'fold': i + 1,
        'test_start_idx': test_start_idx,
        'test_end_idx': test_end_idx,
        'test_start_date': df_cv.timestamp.iloc[test_start_idx],
        'test_end_date':   df_cv.timestamp.iloc[test_end_idx - 1],
        'n_rows': test_end_idx - test_start_idx,
    })

fold_df = pd.DataFrame(fold_boundaries)
print(fold_df)
```

**IMPORTANT:** If your actual CV uses different splitting (different test_size, different embargo, etc.), reproduce that exactly. The dates must match what the model actually saw. If unsure, add a print statement to your existing CV code that dumps fold boundaries, run it once, and copy the dates here verbatim.

### Cell 3: Tag each row with its fold and good/bad status

```python
df_cv['fold'] = -1
for _, fb in fold_df.iterrows():
    mask = (df_cv.index >= fb.test_start_idx) & (df_cv.index < fb.test_end_idx)
    df_cv.loc[mask, 'fold'] = fb.fold

# Tag fold quality based on Phase 2 results (threshold 0.55, v0.3 MTF)
fold_status = {
    1: {'long': 'bad',  'short': 'bad'},   # both negative
    2: {'long': 'good', 'short': 'good'},
    3: {'long': 'good', 'short': 'bad'},   # SHORT marginal negative
    4: {'long': 'bad',  'short': 'good'},  # LONG worst, SHORT actually good
    5: {'long': 'good', 'short': 'bad'},   # SHORT catastrophic
}

# Print the calendar windows
print("\nFold calendar windows:")
for _, fb in fold_df.iterrows():
    s = fold_status[fb.fold]
    print(f"  Fold {fb.fold}: {fb.test_start_date.date()} → {fb.test_end_date.date()} "
          f"({fb.n_rows:,} bars) | LONG: {s['long']}, SHORT: {s['short']}")
```

After this cell runs, screenshot the output and paste the date ranges into your prediction notes. Now you know exactly what calendar periods you're investigating.

---

## Section 1: What was EURUSD doing in each fold? (Visual)

### Cell 4: Daily price chart with fold overlays

This is the most important visual in the whole notebook. You want to see at a glance which folds were trends, ranges, reversals.

```python
# Resample to daily for readability (M5 is too dense to plot 2.5 years cleanly)
daily = df_cv.set_index('timestamp').resample('1D').agg({
    'dist_sma_m5_200': 'last',   # any column will do; we just need a price proxy
}).dropna()

# Get actual close prices — derive from your features or load separately
# If your CSV doesn't have raw close price, reconstruct an approximation from
# dist_sma_m5_200 + atr_m5 isn't great. BETTER: ensure DataCollector logs
# 'close_price' as a column going forward, or reload raw bars from cTrader export.
# For now, if you don't have raw price, just plot a normalized version:

# Hack: cumulative bar0_body * atr gives synthetic price drift
# (NOT perfect but shows shape)
df_cv['synthetic_return'] = df_cv['bar0_body'] * df_cv['atr_m5']
df_cv['synthetic_price'] = df_cv['synthetic_return'].cumsum()

daily_price = df_cv.set_index('timestamp')['synthetic_price'].resample('1D').last().dropna()

fig, ax = plt.subplots(figsize=(16, 7))
ax.plot(daily_price.index, daily_price.values, color='black', lw=0.8)

# Overlay fold windows with color by status
colors = {'good': 'green', 'bad': 'red'}
for _, fb in fold_df.iterrows():
    s = fold_status[fb.fold]
    # LONG status on top half, SHORT on bottom — or just pick one for clarity
    ax.axvspan(fb.test_start_date, fb.test_end_date,
               alpha=0.15, color=colors[s['long']],
               label=f"Fold {fb.fold} LONG-{s['long']}")
    ax.text(fb.test_start_date + (fb.test_end_date - fb.test_start_date)/2,
            ax.get_ylim()[1]*0.95, f"F{fb.fold}\nL:{s['long']}\nS:{s['short']}",
            ha='center', fontsize=10, fontweight='bold')

ax.set_title("EURUSD price across walk-forward folds (LONG status shaded)")
ax.set_xlabel("Date")
ax.set_ylabel("Synthetic cumulative price")
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "fold_overview_chart.png", dpi=120)
plt.show()
```

**RECOMMENDATION:** If you can, export raw EURUSD daily candles from cTrader and use those instead of the synthetic price. Much cleaner. Even just OHLC daily for the 2.5-year window from any source (Yahoo, Dukascopy, FP Markets MT4) will work — you only need it for visual context, not for ML.

### Cell 5: Eyeball assessment

Look at the chart. For each fold, write down in plain English what you see:

- *"Fold 1: choppy sideways with a slight drift down"*
- *"Fold 2: clean uptrend with one shallow pullback"*
- *"Fold 3: high volatility, two sharp reversals"*
- etc.

Don't skip this. Pattern recognition is what this whole exercise is about.

---

## Section 2: Quantitative regime characterization

### Cell 6: Per-fold summary statistics

For each fold, compute regime descriptors. These are the numbers that will tell you *what* differs between good and bad folds, beyond eyeballing.

```python
def regime_stats(group):
    """Compute regime descriptors for a fold (or any time slice)."""
    return pd.Series({
        # Volatility
        'atr_mean':           group['atr_m5'].mean(),
        'atr_std':            group['atr_m5'].std(),
        'atr_p90':            group['atr_m5'].quantile(0.90),
        'bb_width_mean':      group['bb_width'].mean(),

        # Trend strength
        'adx_mean':           group['adx_m5'].mean(),
        'adx_above_25_pct':   (group['adx_m5'] > 25).mean() * 100,

        # Direction balance
        'bull_aligned_pct':   (group['mtf_alignment_score'] >= 3).mean() * 100,
        'bear_aligned_pct':   (group['mtf_alignment_score'] <= -3).mean() * 100,
        'mixed_pct':          (group['mtf_alignment_score'].abs() < 3).mean() * 100,

        # Regime persistence
        'avg_alignment_run':  group['mtf_alignment_duration'].abs().mean(),
        'flips_per_1000bar':  (group['bars_since_tf_fast_flip'] == 0).sum() / len(group) * 1000,

        # Higher TF context
        'h1_slope_mean':      group['slope_sma_h1_200'].mean(),
        'h1_slope_std':       group['slope_sma_h1_200'].std(),

        # Label balance — this is the smoking gun if regime is the issue
        'long_win_rate':      (group['outcome_long']  == 'win').mean() * 100,
        'long_loss_rate':     (group['outcome_long']  == 'loss').mean() * 100,
        'long_timeout_rate':  (group['outcome_long']  == 'timeout').mean() * 100,
        'short_win_rate':     (group['outcome_short'] == 'win').mean() * 100,
        'short_loss_rate':    (group['outcome_short'] == 'loss').mean() * 100,
        'short_timeout_rate': (group['outcome_short'] == 'timeout').mean() * 100,
    })

fold_regime = df_cv[df_cv.fold > 0].groupby('fold').apply(regime_stats)

# Add status columns
fold_regime['long_status']  = fold_regime.index.map(lambda f: fold_status[f]['long'])
fold_regime['short_status'] = fold_regime.index.map(lambda f: fold_status[f]['short'])

# Save for reference
fold_regime.to_csv(OUTPUT_DIR / "fold_regime_stats.csv")
print(fold_regime.round(2).T)  # transpose for readability
```

### Cell 7: The key question — what differs between good and bad folds?

```python
# Compute mean of each metric for good vs bad folds (LONG perspective)
metrics = [c for c in fold_regime.columns if c not in ['long_status', 'short_status']]

long_good = fold_regime[fold_regime.long_status == 'good'][metrics].mean()
long_bad  = fold_regime[fold_regime.long_status == 'bad'][metrics].mean()

comparison = pd.DataFrame({
    'good_folds_mean': long_good,
    'bad_folds_mean':  long_bad,
    'pct_diff':        ((long_bad - long_good) / long_good.abs() * 100).round(1),
}).sort_values('pct_diff', key=abs, ascending=False)

print("=== LONG perspective: what differs between good and bad folds ===")
print(comparison)
comparison.to_csv(OUTPUT_DIR / "long_good_vs_bad_comparison.csv")

# Same for SHORT
short_good = fold_regime[fold_regime.short_status == 'good'][metrics].mean()
short_bad  = fold_regime[fold_regime.short_status == 'bad'][metrics].mean()

comparison_s = pd.DataFrame({
    'good_folds_mean': short_good,
    'bad_folds_mean':  short_bad,
    'pct_diff':        ((short_bad - short_good) / short_good.abs() * 100).round(1),
}).sort_values('pct_diff', key=abs, ascending=False)

print("\n=== SHORT perspective: what differs between good and bad folds ===")
print(comparison_s)
comparison_s.to_csv(OUTPUT_DIR / "short_good_vs_bad_comparison.csv")
```

**This is the diagnostic table.** The features at the top of each table (largest % difference) are your candidates for what defines the regime. If `atr_mean` is 40% higher in bad folds, that's a volatility regime issue. If `bull_aligned_pct` is 60% higher in bad LONG folds, the model is over-trading bullish setups in conditions where they fail.

### Cell 8: Statistical significance check

The good/bad split has tiny samples (3 vs 2 folds). Don't over-interpret. Use a Mann-Whitney test as a sanity check, but treat anything close to significant as merely suggestive:

```python
from scipy.stats import mannwhitneyu

# For each metric, test: are bar-level distributions different in good vs bad LONG folds?
print("Per-bar Mann-Whitney U test (good vs bad LONG folds):")
print("(p < 0.001 = strong evidence of distribution shift)\n")

bad_fold_ids  = [f for f, s in fold_status.items() if s['long'] == 'bad']
good_fold_ids = [f for f, s in fold_status.items() if s['long'] == 'good']

bad_mask  = df_cv.fold.isin(bad_fold_ids)
good_mask = df_cv.fold.isin(good_fold_ids)

key_features = ['atr_m5', 'adx_m5', 'bb_width', 'mtf_alignment_score',
                'mtf_alignment_duration', 'slope_sma_h1_200', 'rsi_m5']

results = []
for feat in key_features:
    stat, p = mannwhitneyu(df_cv.loc[bad_mask,  feat].dropna(),
                           df_cv.loc[good_mask, feat].dropna(),
                           alternative='two-sided')
    results.append({'feature': feat, 'p_value': p,
                    'bad_median':  df_cv.loc[bad_mask,  feat].median(),
                    'good_median': df_cv.loc[good_mask, feat].median()})

print(pd.DataFrame(results).round(4))
```

---

## Section 3: Visual distribution overlays

A picture beats a table for spotting regime differences. For each suspect feature, plot good-fold vs bad-fold distributions overlaid.

### Cell 9: Distribution overlays for key features

```python
key_features_visual = ['atr_m5', 'adx_m5', 'bb_width',
                       'mtf_alignment_score', 'mtf_alignment_duration',
                       'slope_sma_h1_200', 'atr_ratio_m5_h1']

fig, axes = plt.subplots(3, 3, figsize=(16, 12))
axes = axes.flatten()

for i, feat in enumerate(key_features_visual):
    ax = axes[i]
    ax.hist(df_cv.loc[good_mask, feat].dropna(), bins=60, alpha=0.5,
            color='green', label='good LONG folds', density=True)
    ax.hist(df_cv.loc[bad_mask,  feat].dropna(), bins=60, alpha=0.5,
            color='red', label='bad LONG folds',  density=True)
    ax.set_title(feat)
    ax.legend(fontsize=8)

# Hide unused subplots
for j in range(len(key_features_visual), len(axes)):
    axes[j].axis('off')

plt.tight_layout()
plt.savefig(OUTPUT_DIR / "feature_distributions_long_good_vs_bad.png", dpi=120)
plt.show()
```

Repeat for SHORT (replace `bad_mask` with the SHORT-bad mask). 

**What you're looking for:** Distributions that are clearly *shifted* between green and red — not just slightly fatter tails. If `atr_m5` is centered at 0.0008 in good folds and 0.0014 in bad folds, that's a regime. If they're basically the same shape, that feature isn't the regime axis.

---

## Section 4: Equity curve overlay with regime markers

### Cell 10: Plot equity curve with regime annotation

This ties everything together. Take the LONG equity curve from Phase 2 (you already have it as a plot), reconstruct the cumulative R, and shade by your candidate regime feature.

```python
# Load predictions from Phase 2 if available, otherwise re-score quickly
# (Pseudocode — adapt to your actual structure)
# preds = pd.read_csv("../models/predictions_long_v0.3.csv")  # if you saved them
# Otherwise, run the model on df_cv:

# from joblib import load
# model = load("../models/eurusd_long_v0.3.joblib")
# X = df_cv[FEATURE_COLS]
# df_cv['p_win_long'] = model.predict_proba(X)[:, 1]
# df_cv['traded_long'] = (df_cv.p_win_long > 0.55) & (df_cv.fold > 0)
# df_cv['r_long'] = np.where(df_cv.outcome_long == 'win',  2.0,
#                   np.where(df_cv.outcome_long == 'loss', -1.0, 0.0))
# df_cv.loc[~df_cv.traded_long, 'r_long'] = 0
# df_cv['cum_r_long'] = df_cv['r_long'].cumsum()

# Plot equity with one candidate regime feature shaded
# E.g., shade red where atr_m5 > 90th percentile (high-vol regime)
threshold_atr = df_cv['atr_m5'].quantile(0.90)
df_cv['high_vol'] = df_cv['atr_m5'] > threshold_atr

fig, ax = plt.subplots(figsize=(16, 6))
ax.plot(df_cv.timestamp, df_cv['cum_r_long'], color='black', lw=1)
# Shade high-vol periods
in_high = False
start = None
for t, hv in zip(df_cv.timestamp, df_cv['high_vol']):
    if hv and not in_high:
        start = t; in_high = True
    elif not hv and in_high:
        ax.axvspan(start, t, alpha=0.2, color='red'); in_high = False

ax.set_title("LONG equity curve (R) with high-volatility periods shaded")
ax.set_xlabel("Date"); ax.set_ylabel("Cumulative R")
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "equity_with_regime_overlay.png", dpi=120)
plt.show()
```

If the equity curve consistently turns down during shaded periods → volatility is your regime. If not → try the next candidate (ADX percentile, BB width, alignment duration, etc.).

---

## Section 5: Decision-making cell

After all the above, write a final markdown cell summarizing:

```markdown
## Diagnosis Summary

### 1. What I predicted (from top of notebook)
- ...

### 2. What I actually found
- Fold 4 (LONG bad) was a [trending / choppy / volatile / quiet] period
- Fold 5 (SHORT bad) was a [...] period
- Fold 1 (both bad) was a [...] period

### 3. Top 3 regime features distinguishing good from bad folds
1. `feature_name` — bad folds have X, good folds have Y
2. ...
3. ...

### 4. Verdict
- [ ] STRONG regime signal found → proceed to add 2-3 targeted regime features
- [ ] WEAK regime signal → consider meta-gating model approach
- [ ] NO regime signal → the failure is something else (look at trade timing? specific
      clusters of losses? broker-side issues?)

### 5. Concrete next step
[One specific thing to do next, with success criteria]
```

---

## Anti-patterns to avoid

- **Don't add features yet.** This notebook is purely diagnostic. Adding features is the *next* notebook, informed by what this one finds.
- **Don't run a 50-feature distribution comparison.** You'll find spurious "differences" everywhere. Stick to ~7-10 hypothesis-driven features per chart.
- **Don't trust the Mann-Whitney p-values too much.** With 200k+ bars, *anything* will be "significant." Use it as a sanity check, not a verdict.
- **Don't skip writing your predictions first.** Without them, you'll fool yourself into thinking the result was obvious in hindsight.
- **Don't try to fix it in this notebook.** If you spot something interesting, write it down and stop. The fix belongs in a separate notebook with its own validation.

---

## What "good" looks like at the end of this exercise

You should be able to complete this sentence in one line:

> *"The bad folds (LONG-4, SHORT-5, both-1) all share **[regime characteristic X]**, which the model can't see because it lacks **[feature Y]**. Adding **[feature Y]** to the next training run is the targeted fix."*

If you can't finish that sentence after running the notebook, you haven't found the regime — and that's also useful information (it pushes you toward the meta-gating approach instead).
