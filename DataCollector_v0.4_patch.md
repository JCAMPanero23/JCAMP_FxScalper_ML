# DataCollector v0.4 — Regime Features + Fold Verification + Iteration Budget

**Date:** 2026-04-16
**Purpose:** Three things in one document, designed to be executed by Claude Code in order.

---

## PART 1: Verify Fold 5 Sizing (DO THIS FIRST)

### Why This Matters

The fold diagnosis showed Fold 5 covering "Dec 2023 - Sep 2025" — potentially
21 months of a 33-month CV window. If Fold 5 is 3-5× larger than other folds,
the "3/5 good folds" metric is misleading because Fold 5 dominates any average.
The entire regime analysis could be an artifact of uneven fold sizes.

### What To Run

Add this diagnostic cell to the TOP of any notebook (or run as a standalone
script). It must use the EXACT same split logic as `src/cv.py`.

```python
# ============================================================
# FOLD SIZE VERIFICATION
# Run this BEFORE any feature engineering.
# If Fold 5 is >2× the size of other folds, the CV structure
# needs fixing before adding more features.
# ============================================================

import pandas as pd
import numpy as np
from pathlib import Path

# --- Load data (match existing notebook conventions) ---
DATA_PATH = Path("data/DataCollector_EURUSD_M5_20230101_220400.csv")
df = pd.read_csv(DATA_PATH, parse_dates=['timestamp'])
df = df.sort_values('timestamp').reset_index(drop=True)

# Filter to train/CV window (must match what walk-forward used)
train_cv_end = pd.Timestamp('2025-09-30 23:59:59')
df_cv = df[df.timestamp <= train_cv_end].reset_index(drop=True)

print(f"Total train/CV rows: {len(df_cv):,}")
print(f"Date range: {df_cv.timestamp.min()} to {df_cv.timestamp.max()}")
print()

# --- Option A: If using sklearn's TimeSeriesSplit or similar ---
# Reproduce your EXACT splitter. If cv.py uses PurgedWalkForward with
# n_splits=5, test_size=0.15, reproduce that here.
#
# If you wrote a custom splitter, import it:
#   from src.cv import PurgedWalkForward
#   splitter = PurgedWalkForward(n_splits=5, test_size=0.15, embargo=48)
#   for fold_num, (train_idx, test_idx) in enumerate(splitter.split(df_cv), 1):
#       ...
#
# If you used sklearn TimeSeriesSplit:
from sklearn.model_selection import TimeSeriesSplit
tscv = TimeSeriesSplit(n_splits=5, test_size=int(len(df_cv) * 0.15))

print("=" * 70)
print("FOLD SIZE VERIFICATION")
print("=" * 70)

fold_info = []
for fold_num, (train_idx, test_idx) in enumerate(tscv.split(df_cv), 1):
    test_rows = len(test_idx)
    test_start = df_cv.timestamp.iloc[test_idx[0]]
    test_end   = df_cv.timestamp.iloc[test_idx[-1]]
    train_rows = len(train_idx)
    months = (test_end - test_start).days / 30.44

    fold_info.append({
        'fold': fold_num,
        'train_rows': train_rows,
        'test_rows': test_rows,
        'test_start': test_start.date(),
        'test_end': test_end.date(),
        'months': round(months, 1),
    })

    print(f"Fold {fold_num}: train={train_rows:>7,}  test={test_rows:>6,}  "
          f"period={test_start.date()} → {test_end.date()} ({months:.1f} months)")

fi = pd.DataFrame(fold_info)
max_test = fi.test_rows.max()
min_test = fi.test_rows.min()
ratio = max_test / min_test

print()
print(f"Largest fold:  {max_test:,} bars")
print(f"Smallest fold: {min_test:,} bars")
print(f"Ratio:         {ratio:.1f}×")
print()

if ratio > 2.0:
    print("⚠️  WARNING: Fold sizes are uneven (ratio > 2×).")
    print("   The largest fold dominates any averaged metric.")
    print("   RECOMMENDATION: Switch to fixed-size test windows.")
    print()
    print("   Fix: Use explicit 6-month test windows instead of percentage-based splits.")
    print("   Example fix below.")
    print()
    print("   FIXED FOLD BOUNDARIES (6-month windows):")
    # Generate equal-duration folds
    cv_start = df_cv.timestamp.min()
    cv_end   = df_cv.timestamp.max()
    # 5 folds of ~6 months each over ~30 months
    boundaries = pd.date_range(cv_start, cv_end, periods=6)
    for i in range(len(boundaries) - 1):
        mask = (df_cv.timestamp >= boundaries[i]) & (df_cv.timestamp < boundaries[i+1])
        n = mask.sum()
        print(f"   Fold {i+1}: {boundaries[i].date()} → {boundaries[i+1].date()} ({n:,} bars)")
else:
    print("✅ Fold sizes are reasonably balanced (ratio ≤ 2×).")
    print("   Proceed with current CV structure.")
```

### Decision After Running

**If ratio > 2×:**
1. Fix the CV splitter BEFORE adding features. Use fixed-duration test windows
   (e.g., 6 months each) instead of percentage-based splits.
2. Re-run the walk-forward CV with v0.3 features (no changes) to get corrected
   baseline metrics.
3. THEN add v0.4 features and compare against corrected baseline.
4. Update `PHASE2_FOLD_DIAGNOSIS.md` to note the structural issue.

**If ratio ≤ 2×:**
Proceed directly to Part 2 (DataCollector v0.4 patch).

---

## PART 2: DataCollector v0.4 Patch — Two Regime Features

### What's Being Added and Why

The fold diagnosis identified two actionable gaps:

1. **Volatility regime context is missing.** The model sees `atr_m5` (current
   volatility) but not "is current volatility high or low relative to recent
   history?" These are different signals. ATR of 0.0008 is normal in one month
   and extreme in another.

2. **The interaction between MTF direction and H1 slope isn't exposed.** Both
   features exist individually. The SHORT model fails when `mtf_alignment_score`
   is positive (bullish) but the individual features don't explicitly say
   "you're about to short against the macro trend." An explicit agreement/
   disagreement feature makes this relationship visible to the model without
   requiring it to discover the interaction from scratch.

### What's NOT Being Added (and Why)

- ❌ `alignment_freshness = 200 - abs(mtf_alignment_duration)` — This is a
  linear transformation of an existing feature. LightGBM is invariant to
  monotonic transforms. Zero new information.

- ❌ `trend_maturity` (categorical bucketing) — Bucketing `mtf_alignment_duration`
  into early/mid/late categories LOSES information. The model can find its own
  thresholds from the continuous version.

- ❌ `h1_slope_regime` (categorical) — `slope_sma_h1_200` is already in the
  dataset as a continuous feature. Categorizing it at hand-picked thresholds
  adds no information and constrains the model to your guesses about where the
  cutoffs should be.

### The Two New Features

| # | Feature | Range | What It Captures |
|---|---------|-------|------------------|
| 1 | `atr_percentile_2000bar` | 0.0 – 1.0 | Current ATR relative to last 2000 bars (~7 trading days). Is vol high or low compared to recent? |
| 2 | `h1_alignment_agreement` | -1, 0, +1 | Does MTF alignment direction agree with H1 slope? +1=agreement, -1=disagreement, 0=one is neutral |

Feature count: 44 → 46.

---

### CHANGE 1 — CHANGELOG (top of JCAMP_DataCollector.cs)

Insert after the v0.3 entry:

```csharp
//   v0.4 (2026-04-16)
//     - FEATURE: Added 2 regime-quality features based on fold diagnosis.
//       atr_percentile_2000bar (rolling ATR percentile for volatility context),
//       h1_alignment_agreement (interaction: MTF direction vs H1 macro slope).
//     - STATE: Added _atrHistory ring buffer for rolling percentile calc.
//     - RATIONALE: Fold diagnosis showed SHORT fails when MTF alignment
//       disagrees with H1 slope. LONG fails partly due to vol regime blindness.
//       See PHASE2_FOLD_DIAGNOSIS.md for full analysis.
```

---

### CHANGE 2 — New private fields

Add near the other MTF state tracking fields (after the v0.3 fields):

```csharp
        // ----- Regime tracking (v0.4) -----------------------------------------
        // Ring buffer for rolling ATR percentile (last 2000 M5 bars ≈ 7 trading days)
        private const int ATR_HISTORY_SIZE = 2000;
        private readonly Queue<double> _atrHistory = new Queue<double>();
```

---

### CHANGE 3 — Add features inside ComputeFeatures

Insert this block AFTER the v0.3 MTF section (after `f["mtf_alignment_duration"]`)
and BEFORE `return f;`:

```csharp
            // --- Regime quality (v0.4) ------------------------------------------
            // These features address the fold-diagnosis finding: model needs to
            // know (a) whether current volatility is high/low RELATIVE to recent
            // history, and (b) whether MTF direction agrees with H1 macro slope.

            // Feature 1: atr_percentile_2000bar
            // Rolling percentile: what fraction of the last 2000 ATR values are
            // <= the current ATR? Range 0.0 (unusually calm) to 1.0 (unusually hot).
            // During warmup (<2000 bars), uses whatever history is available.
            _atrHistory.Enqueue(atr);
            while (_atrHistory.Count > ATR_HISTORY_SIZE)
                _atrHistory.Dequeue();

            if (_atrHistory.Count >= 50)  // need some minimum history
            {
                int countBelow = 0;
                foreach (var h in _atrHistory)
                    if (h <= atr) countBelow++;
                f["atr_percentile_2000bar"] = (double)countBelow / _atrHistory.Count;
            }
            else
            {
                f["atr_percentile_2000bar"] = 0.5;  // neutral default during warmup
            }

            // Feature 2: h1_alignment_agreement
            // Does MTF alignment direction agree with H1 slope direction?
            //   +1 = agreement (both bullish or both bearish)
            //   -1 = disagreement (MTF says bull, H1 says bear, or vice versa)
            //    0 = one or both are neutral (no strong signal either way)
            //
            // This directly addresses the SHORT fold-failure: SHORT model loses
            // when MTF alignment is bearish but H1 macro slope is positive.
            // The individual features exist but the model struggles to discover
            // the interaction — exposing it explicitly helps.
            double h1Slope = f["slope_sma_h1_200"];
            int mtfSign = 0;
            if (alignScore >= 2)  mtfSign = +1;   // clear bullish alignment
            else if (alignScore <= -2) mtfSign = -1;  // clear bearish alignment

            int h1Sign = 0;
            if (h1Slope > 0.00005)  h1Sign = +1;    // H1 trending up
            else if (h1Slope < -0.00005) h1Sign = -1; // H1 trending down

            if (mtfSign == 0 || h1Sign == 0)
                f["h1_alignment_agreement"] = 0;      // one side is neutral
            else
                f["h1_alignment_agreement"] = (mtfSign == h1Sign) ? 1 : -1;
```

---

### CHANGE 4 — No other changes needed

No new indicator handles. No new state to reset in OnStart (the Queue
initializes inline). No changes to WriteRow, ResolvePendingBars, or
PendingBar class.

The `alignScore` variable from v0.3 is reused (it's computed earlier in
the same method). The `h1Slope` is read from the already-computed feature
dictionary.

---

### Smoke Test Checklist (v0.4)

Run on ONE month (Jan 2023) and verify:

1. **`atr_percentile_2000bar`:**
   - First ~50 bars should all be 0.5 (warmup default)
   - After warmup, values should range roughly 0.0 to 1.0
   - Distribution should be roughly uniform (not clustered at 0 or 1)
   - Check: `df['atr_percentile_2000bar'].describe()` — mean should be near 0.5

2. **`h1_alignment_agreement`:**
   - Values should be exactly -1, 0, or +1 (nothing else)
   - Distribution: roughly 30-40% each of -1 and +1, 20-30% zeros
   - If >80% are zeros, the thresholds (±2 for alignment, ±0.00005 for slope)
     are too strict — loosen them
   - If <5% are zeros, the thresholds are too loose — tighten them

3. **No NaN/Inf in either column.**

4. **Total column count = 46** (was 44 in v0.3).

5. **Existing columns unchanged** — spot-check 5 random rows against the v0.3
   CSV to make sure nothing shifted.

---

### Implementation Note: ATR Percentile Performance

The naive loop (`foreach h in _atrHistory: if h <= atr`) is O(2000) per bar.
Over 244k bars that's ~488M comparisons. In C# on modern hardware this takes
<1 second total — not worth optimizing. If it ever matters (e.g., running on
10 pairs simultaneously), replace the Queue with a sorted array and use binary
search for O(log n) per bar.

---

### Thresholds Rationale

**`alignScore >= 2` for "clear bullish"** (not >=1, not >=3):
- ±1 is too loose: 1 TF above and 3 below still counts as bullish = noisy
- ±3 is too strict: only fires when 3+ of 4 TFs agree = too rare for an
  interaction feature
- ±2 is the sweet spot: 3 bullish + 1 bearish = net +2 = meaningfully directional

**`h1Slope > 0.00005` for "H1 trending up":**
- The fold diagnosis showed good-SHORT folds had h1_slope mean of -0.00005
  and bad-SHORT folds had +0.00015
- Threshold at +0.00005 sits between those means — a reasonable decision boundary
- The ML can still learn finer distinctions from `slope_sma_h1_200` directly;
  this feature just surfaces the cross-signal interaction

These thresholds define "clearly directional" vs "neutral" for the interaction
feature. They are NOT trading thresholds — the model still makes its own
probability estimate. If the thresholds are slightly off, the model simply
sees more 0s (neutral) or more ±1s. Either way it can learn from the data.

---

## PART 3: Iteration Budget (Non-Negotiable)

### The Rule

This is the LAST feature-engineering iteration before a pivot decision.

After v0.4 walk-forward CV results come back, one of three things happens:

### Gate A — Proceed to Holdout (Best Case)

**ALL of these must hold at the best threshold (0.55, 0.60, or 0.65):**

| Criterion | LONG | SHORT |
|-----------|------|-------|
| Positive folds | ≥ 4/5 | ≥ 3/5 |
| Mean expectancy | ≥ +0.09R | ≥ +0.09R |
| Worst fold expectancy | ≥ -0.15R | ≥ -0.15R |
| Avg trades per fold | ≥ 80 | ≥ 80 |

**Action:** Touch the holdout set (Oct 2025 – Mar 2026) ONCE. If holdout
confirms, proceed to Phase 3 (FastAPI). If holdout diverges by >30% from
CV estimates, return to diagnosis.

**Note:** The mean expectancy gate is relaxed from +0.10R to +0.09R.
Rationale: the original +0.10R was set before the fold-diagnosis work
showed that fold-sizing artifacts may inflate fold-to-fold variance.
+0.09R with 4/5 consistency is a stronger signal than +0.10R with 3/5.

### Gate B — Pivot to Meta-Gating (Middle Case)

**If v0.4 results show improvement but don't clear Gate A:**

Specifically: mean expectancy improved from v0.3 (currently +0.071R) but
still below +0.09R, OR fold consistency still at 3/5.

**Action:** Stop adding features. Pivot to meta-gating model:

1. Train a separate binary classifier whose only job is: "given the current
   regime features (atr_percentile, h1_slope, alignment_duration), is this
   a GOOD period for the LONG/SHORT model to trade?"

2. Labels for the gating model: use per-fold outcomes. A fold where the base
   model had positive expectancy = "good regime" = 1. Negative = "bad" = 0.

3. Trading rule becomes: base model says p_win > threshold AND gating model
   says regime = good.

4. This gets ONE iteration. If it doesn't clear Gate A, proceed to Gate C.

**Budget for meta-gating: ONE experiment, ONE evaluation. No tuning loops.**

### Gate C — Pivot Away (Last Resort)

**If v0.4 doesn't improve meaningfully over v0.3, OR meta-gating doesn't work:**

"Doesn't improve meaningfully" means: mean expectancy change < +0.01R for
both directions, or fold consistency unchanged/worse.

**Action:** Accept that M5 EURUSD scalping entry prediction with this feature
set has a ceiling below the deployment threshold. Pivot options (pick ONE):

- **C1: Move to M15 timeframe.** Re-run DataCollector on M15. Completely new
  feature set. Triple-barrier params scaled to M15 (SL=2×ATR(M15), TP=4×ATR,
  max 24 bars = 6h). Start Phase 2 fresh.

- **C2: ML for exits, not entries.** Keep v4.5.x rule-based entries. Train ML
  to predict optimal exit timing (hold/take-partial/trail-aggressively) instead
  of entry probability. Different label construction.

- **C3: Switch to GBPUSD.** More volatile, potentially more ML-exploitable
  inefficiency. Re-run DataCollector. Same pipeline.

- **C4: Honest abandon.** Accept that ML doesn't add enough to justify the
  complexity over the rule-based system. Archive the project with clean docs.
  No shame in this — the experiment gave clear, honest answers.

**The choice between C1-C4 is made AFTER reaching this gate, not before.**
Don't pre-commit to a pivot direction; the results may inform which pivot
makes the most sense.

---

### Summary: Maximum Remaining Experiments Before Pivot

```
Current state: v0.3 (44 features), Branch C triggered
     │
     ▼
[PART 1] Verify fold sizes
     │
     ├── If uneven → fix CV, re-run v0.3 baseline, THEN proceed
     │
     ▼
[PART 2] Add 2 features → v0.4 (46 features)
     │
     ▼
[Walk-forward CV on v0.4]
     │
     ├── Gate A met    → touch holdout → Phase 3 if confirmed
     │
     ├── Improved but  → ONE meta-gating experiment
     │   not enough    │
     │                 ├── Gate A met → touch holdout
     │                 └── Still not  → Gate C pivot
     │
     └── No improvement → Gate C pivot (skip meta-gating)
```

**Maximum remaining experiments: 2** (v0.4 features + optional meta-gating).
**Maximum remaining feature engineering iterations: 1** (this one).
**Holdout touches: still exactly 1, at the end.**

This budget is written down. It is not negotiable. The temptation to do
"just one more tweak" is the same trap that killed v4.6.0. The discipline
is the product.

---

## PART 4: Checklist for Claude Code

When Claude Code picks up this document, execute in this order:

### Step 1: Run fold verification (Part 1)
- [ ] Execute the fold-size diagnostic script
- [ ] If ratio > 2×: fix CV splitter to use equal-duration windows, re-run v0.3
      baseline, update STATUS.md with corrected metrics
- [ ] If ratio ≤ 2×: note "fold sizes verified" in STATUS.md, proceed

### Step 2: Apply DataCollector patch (Part 2)
- [ ] Add CHANGELOG entry for v0.4
- [ ] Add `_atrHistory` field and `ATR_HISTORY_SIZE` constant
- [ ] Add `atr_percentile_2000bar` computation in ComputeFeatures
- [ ] Add `h1_alignment_agreement` computation in ComputeFeatures
- [ ] Build and verify compilation (no errors, no warnings)

### Step 3: Smoke test
- [ ] Run DataCollector on Jan 2023 only
- [ ] Verify `atr_percentile_2000bar` ranges and distribution
- [ ] Verify `h1_alignment_agreement` values are exactly {-1, 0, +1}
- [ ] Verify no NaN/Inf in new columns
- [ ] Verify total column count = 46
- [ ] Verify existing columns unchanged (spot-check 5 rows vs v0.3)

### Step 4: Full historical run
- [ ] Run DataCollector Jan 2023 → present on EURUSD M5
- [ ] Verify ~244k+ rows in output CSV
- [ ] Save as v0.4 dataset (new filename or overwrite with backup)

### Step 5: Walk-forward CV
- [ ] Run walk-forward at thresholds 0.55, 0.60, 0.65
- [ ] Compare against v0.3 results using same metrics table format
- [ ] Evaluate against Gate A / Gate B / Gate C criteria
- [ ] Document result in STATUS.md and new PHASE2_V04_RESULTS.md

### Step 6: Decision
- [ ] If Gate A → proceed to holdout test
- [ ] If Gate B → design and run ONE meta-gating experiment
- [ ] If Gate C → document pivot decision and rationale

### Step 7: Update documentation
- [ ] Update STATUS.md with v0.4 results and decision
- [ ] Update PRD if pivoting (add notes to Phase 2 section)
- [ ] Commit all changes

---

## Appendix: Complete v0.4 Feature List (46 features)

### Original (39 features, v0.1-v0.2)

**Price vs SMAs (ATR-normalized):**
dist_sma_m5_50, dist_sma_m5_100, dist_sma_m5_200, dist_sma_m5_275,
dist_sma_m15_200, dist_sma_m30_200, dist_sma_h1_200, dist_sma_h4_200

**SMA slopes:**
slope_sma_m5_200, slope_sma_h1_200

**Momentum:**
rsi_m5, rsi_m15, rsi_m30, adx_m5, di_plus_m5, di_minus_m5

**Volatility:**
atr_m5, atr_m15, atr_h1, atr_ratio_m5_h1, bb_width

**Recent bars (ATR-normalized):**
bar0_body, bar0_range, bar1_body, bar1_range, bar2_body, bar2_range,
bar3_body, bar3_range, bar4_body, bar4_range

**Swing structure:**
dist_swing_high, dist_swing_low

**Time/session:**
hour_utc, dow, sess_asia, sess_london, sess_ny

**Cost:**
spread_pips

### MTF features (5 features, v0.3)

mtf_alignment_score, mtf_stacking_score, bars_since_tf_fast_flip,
tf_fast_flip_direction, mtf_alignment_duration

### Regime features (2 features, v0.4)

atr_percentile_2000bar, h1_alignment_agreement
