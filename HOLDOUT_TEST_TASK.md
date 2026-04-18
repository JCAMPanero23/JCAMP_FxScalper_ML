# HOLDOUT TEST — LONG Model Final Evaluation

**Priority:** This is the single most important step in the entire project.
**Date:** 2026-04-18
**Rule:** This test runs ONCE. No re-runs. No parameter changes after seeing results.

---

## Context

The LONG model passed Gate A on walk-forward CV (v0.4, 46 features):
- Mean expectancy: +0.269R at threshold 0.65
- Positive folds: 4/5 (80%)
- Worst fold: -0.060R
- Avg trades/fold: 228

The holdout set (Oct 2025 – Mar 2026, ~36,845 bars) has NEVER been used
for training, tuning, feature selection, or any decision. This is its
one and only use.

---

## What This Test Answers

One question: **"Does the LONG model's edge generalize to data it has
never seen, from a time period after all training data?"**

If yes → proceed to Phase 3 (FastAPI inference service) and live deployment.
If no → the CV estimate was optimistic and the model needs more work.

---

## Step 1: Train Final Model on Full Train/CV Set

**CRITICAL:** The model used for holdout evaluation must be trained on ALL
training data (Jan 2023 – Sep 2025), not on any single fold's training
portion. Walk-forward CV used expanding windows where each fold only saw
a subset. The final model gets everything.

```python
import pandas as pd
import numpy as np
import lightgbm as lgb
from joblib import dump
from pathlib import Path

# Load v0.4 dataset
DATA_PATH = Path("data/DataCollector_EURUSD_M5_20230101_220446.csv")
df = pd.read_csv(DATA_PATH, parse_dates=['timestamp'])
df = df.sort_values('timestamp').reset_index(drop=True)

# Define splits
TRAIN_END    = pd.Timestamp('2025-09-30 23:59:59')
HOLDOUT_END  = pd.Timestamp('2026-03-31 23:59:59')

df_train   = df[df.timestamp <= TRAIN_END].reset_index(drop=True)
df_holdout = df[(df.timestamp > TRAIN_END) & (df.timestamp <= HOLDOUT_END)].reset_index(drop=True)

print(f"Train set:   {len(df_train):,} rows  ({df_train.timestamp.min().date()} to {df_train.timestamp.max().date()})")
print(f"Holdout set: {len(df_holdout):,} rows ({df_holdout.timestamp.min().date()} to {df_holdout.timestamp.max().date()})")

# Verify holdout has never been touched
assert len(df_holdout) > 30000, f"Holdout too small: {len(df_holdout)}"
assert df_holdout.timestamp.min() > TRAIN_END, "Holdout overlaps training!"

# ---- Feature columns (must match CV exactly) ----
# List all 46 feature columns. Exclude: timestamp, symbol,
# outcome_long, outcome_short, bars_to_outcome_long, bars_to_outcome_short
LABEL_COLS = ['timestamp', 'symbol',
              'outcome_long', 'bars_to_outcome_long',
              'outcome_short', 'bars_to_outcome_short']
FEATURE_COLS = [c for c in df.columns if c not in LABEL_COLS]
print(f"Features: {len(FEATURE_COLS)}")
assert len(FEATURE_COLS) == 46, f"Expected 46 features, got {len(FEATURE_COLS)}"

# ---- Binary labels (same as CV) ----
# LONG model: win=1, loss=0, timeout=excluded (or 0, match your CV code)
# CHECK: How did your CV handle timeouts? If excluded, exclude here too.
# If treated as loss (0), do the same. MUST MATCH.

# Option A: Exclude timeouts (if that's what CV did)
train_mask = df_train['outcome_long'].isin(['win', 'loss'])
df_train_filtered = df_train[train_mask].reset_index(drop=True)

X_train = df_train_filtered[FEATURE_COLS]
y_train = (df_train_filtered['outcome_long'] == 'win').astype(int)

print(f"Training samples (excl timeouts): {len(X_train):,}")
print(f"Label balance: {y_train.mean():.1%} wins")

# ---- Train with SAME hyperparameters as CV ----
# IMPORTANT: Use the EXACT same LightGBM params from your CV code.
# Do NOT tune anything here. Copy-paste from the training script.

params = {
    'objective': 'binary',
    'metric': 'binary_logloss',
    'num_leaves': 31,        # Must match CV
    'max_depth': 6,          # Must match CV
    'learning_rate': 0.05,   # Must match CV
    'n_estimators': 500,     # Must match CV
    'min_child_samples': 50, # Must match CV — CHECK YOUR ACTUAL VALUE
    'subsample': 0.8,        # Must match CV
    'colsample_bytree': 0.8, # Must match CV
    'reg_alpha': 0.0,        # Must match CV
    'reg_lambda': 0.0,       # Must match CV
    'random_state': 42,
    'verbose': -1,
}

# VERIFY: Open your CV training code and confirm every param above matches.
# If any differ, use YOUR values, not these defaults.

model = lgb.LGBMClassifier(**params)
model.fit(X_train, y_train)

# Save final model
MODEL_PATH = Path("models/eurusd_long_v04_final.joblib")
MODEL_PATH.parent.mkdir(exist_ok=True)
dump(model, MODEL_PATH)
print(f"Model saved to {MODEL_PATH}")
```

---

## Step 2: Generate Holdout Predictions

```python
# ---- Predict on holdout ----
X_holdout = df_holdout[FEATURE_COLS]
p_win_long = model.predict_proba(X_holdout)[:, 1]

df_holdout = df_holdout.copy()
df_holdout['p_win_long'] = p_win_long

print(f"\nHoldout prediction distribution:")
print(f"  Mean p_win: {p_win_long.mean():.3f}")
print(f"  Median:     {np.median(p_win_long):.3f}")
print(f"  > 0.55:     {(p_win_long > 0.55).sum():,} bars ({(p_win_long > 0.55).mean():.1%})")
print(f"  > 0.60:     {(p_win_long > 0.60).sum():,} bars")
print(f"  > 0.65:     {(p_win_long > 0.65).sum():,} bars")
```

---

## Step 3: Calculate Holdout Expectancy

**Use threshold 0.65 (the threshold that passed Gate A).**

```python
THRESHOLD = 0.65

# Filter to "traded" bars
traded = df_holdout[df_holdout['p_win_long'] > THRESHOLD].copy()
n_trades = len(traded)
print(f"\n{'='*60}")
print(f"HOLDOUT TEST — LONG MODEL @ THRESHOLD {THRESHOLD}")
print(f"{'='*60}")
print(f"Period: {df_holdout.timestamp.min().date()} to {df_holdout.timestamp.max().date()}")
print(f"Total bars: {len(df_holdout):,}")
print(f"Traded bars: {n_trades:,} ({n_trades/len(df_holdout):.1%})")

if n_trades == 0:
    print("ERROR: No trades generated. Model may not be calibrated for this period.")
else:
    # Assign R per trade
    r_map = {'win': 2.0, 'loss': -1.0, 'timeout': 0.0}
    traded['r'] = traded['outcome_long'].map(r_map)

    # Core metrics
    expectancy = traded['r'].mean()
    net_r = traded['r'].sum()
    win_rate = (traded['outcome_long'] == 'win').mean()
    loss_rate = (traded['outcome_long'] == 'loss').mean()
    timeout_rate = (traded['outcome_long'] == 'timeout').mean()

    # Win/loss counts
    n_wins = (traded['outcome_long'] == 'win').sum()
    n_losses = (traded['outcome_long'] == 'loss').sum()
    n_timeouts = (traded['outcome_long'] == 'timeout').sum()

    # Profit factor (gross wins / gross losses)
    gross_wins = n_wins * 2.0
    gross_losses = n_losses * 1.0
    profit_factor = gross_wins / max(gross_losses, 0.001)

    # Max consecutive losses
    is_loss = (traded['outcome_long'] == 'loss').values
    max_consec = 0
    current = 0
    for l in is_loss:
        if l:
            current += 1
            max_consec = max(max_consec, current)
        else:
            current = 0

    # Equity curve and max drawdown
    traded['cum_r'] = traded['r'].cumsum()
    max_dd_r = 0
    peak = 0
    for r in traded['cum_r']:
        if r > peak:
            peak = r
        dd = peak - r
        if dd > max_dd_r:
            max_dd_r = dd

    print(f"\n--- RESULTS ---")
    print(f"Trades:           {n_trades}")
    print(f"Wins:             {n_wins} ({win_rate:.1%})")
    print(f"Losses:           {n_losses} ({loss_rate:.1%})")
    print(f"Timeouts:         {n_timeouts} ({timeout_rate:.1%})")
    print(f"")
    print(f"Expectancy:       {expectancy:+.3f}R per trade")
    print(f"Net R:            {net_r:+.1f}R")
    print(f"Profit Factor:    {profit_factor:.2f}")
    print(f"Max Consec Loss:  {max_consec}")
    print(f"Max Drawdown:     {max_dd_r:.1f}R")
    print(f"")

    # ---- VERDICT ----
    cv_estimate = 0.269  # from Gate A evaluation

    pct_of_cv = expectancy / cv_estimate * 100 if cv_estimate != 0 else 0
    within_30 = abs(expectancy - cv_estimate) / cv_estimate <= 0.30

    print(f"--- VERDICT ---")
    print(f"CV estimate:      +{cv_estimate:.3f}R")
    print(f"Holdout result:   {expectancy:+.3f}R")
    print(f"% of CV:          {pct_of_cv:.0f}%")
    print(f"Within ±30%:      {'YES' if within_30 else 'NO'}")
    print(f"")

    if expectancy > 0 and within_30:
        print(f"PASS — Holdout confirms CV estimate.")
        print(f"   Proceed to Phase 3 (FastAPI) and live deployment.")
        verdict = "PASS"
    elif expectancy > 0 and not within_30:
        if pct_of_cv < 100:
            print(f"CAUTIOUS PASS — Positive but below ±30% tolerance.")
            print(f"   Proceed with tighter risk limits and closer monitoring.")
            verdict = "CAUTIOUS_PASS"
        else:
            print(f"CONCERNING — Very positive but well above CV.")
            print(f"   Possible data issue. Verify before proceeding.")
            verdict = "VERIFY"
    elif expectancy <= 0:
        print(f"FAIL — Holdout shows no edge.")
        print(f"   Do NOT deploy. Return to diagnosis.")
        verdict = "FAIL"
```

---

## Step 4: Monthly Breakdown (Diagnostic)

Even if the overall number passes, check month-by-month for consistency:

```python
    # Monthly breakdown
    traded['month'] = traded['timestamp'].dt.to_period('M')
    monthly = traded.groupby('month').agg(
        trades=('r', 'count'),
        win_rate=('outcome_long', lambda x: (x == 'win').mean()),
        expectancy=('r', 'mean'),
        net_r=('r', 'sum'),
    )

    print(f"\n--- MONTHLY BREAKDOWN ---")
    print(monthly.to_string())

    # Flag any month with < 20 trades or < -0.15R expectancy
    for idx, row in monthly.iterrows():
        if row['trades'] < 20:
            print(f"  Warning: {idx}: Only {int(row['trades'])} trades (low sample)")
        if row['expectancy'] < -0.15:
            print(f"  Warning: {idx}: Expectancy {row['expectancy']:+.3f}R (below -0.15R)")
```

---

## Step 5: Save Results

```python
    # Save holdout results
    OUTPUT_DIR = Path("outputs/holdout_test")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Save traded bars with predictions and outcomes
    traded.to_csv(OUTPUT_DIR / "holdout_traded_bars.csv", index=False)

    # Save equity curve data
    traded[['timestamp', 'p_win_long', 'outcome_long', 'r', 'cum_r']].to_csv(
        OUTPUT_DIR / "holdout_equity_curve.csv", index=False)

    # Save summary
    summary = {
        'test_period': f"{df_holdout.timestamp.min().date()} to {df_holdout.timestamp.max().date()}",
        'threshold': THRESHOLD,
        'n_trades': n_trades,
        'win_rate': f"{win_rate:.1%}",
        'expectancy': f"{expectancy:+.3f}R",
        'net_r': f"{net_r:+.1f}R",
        'profit_factor': f"{profit_factor:.2f}",
        'max_drawdown_r': f"{max_dd_r:.1f}R",
        'max_consec_losses': max_consec,
        'cv_estimate': f"+{cv_estimate:.3f}R",
        'pct_of_cv': f"{pct_of_cv:.0f}%",
        'within_30pct': within_30,
        'verdict': verdict,
    }

    import json
    with open(OUTPUT_DIR / "holdout_summary.json", 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\nResults saved to {OUTPUT_DIR}/")
```

---

## Step 6: Update STATUS.md

Add this section to STATUS.md after the results are in:

```markdown
## Holdout Test Results (DATE)

**Model:** LONG v0.4 (46 features)
**Threshold:** 0.65
**Period:** Oct 2025 – Mar 2026 (holdout, FIRST AND ONLY USE)

| Metric | CV Estimate | Holdout Result | Verdict |
|--------|-------------|----------------|---------|
| Expectancy | +0.269R | [RESULT] | [PASS/FAIL] |
| Win Rate | 41.7% | [RESULT] | |
| Profit Factor | N/A | [RESULT] | |
| Max Drawdown | N/A | [RESULT]R | |

**Decision:** [PROCEED TO PHASE 3 / RETURN TO DIAGNOSIS]
```

---

## CRITICAL REMINDERS

1. **Run this ONCE.** Do not re-run with different parameters after seeing
   results. The holdout is now spent regardless of outcome.

2. **Use the EXACT same hyperparameters as CV.** Open the walk-forward
   training code and copy-paste the LightGBM params. Do not "improve"
   them for the final model.

3. **Use threshold 0.65.** This is the threshold that passed Gate A.
   Do not test multiple thresholds on the holdout — that's implicit
   tuning on the test set.

4. **Handle timeouts consistently.** If CV excluded timeouts from
   training labels, exclude them here too. If CV treated them as
   loss (0), do the same. Check the CV code.

5. **Train on ALL train/CV data.** Not on a single fold. The final
   model should use every row from Jan 2023 – Sep 2025.

6. **Do not look at SHORT holdout results in this run.** SHORT didn't
   pass Gate A. Evaluating it on the holdout would burn the holdout
   for SHORT without meeting the prerequisite. SHORT holdout can be
   tested later if/when it passes its own gate.

---

## Success Criteria

- [ ] Final model trained on full train/CV set (Jan 2023 – Sep 2025)
- [ ] Predictions generated on holdout (Oct 2025 – Mar 2026)
- [ ] Expectancy calculated at threshold 0.65
- [ ] Monthly breakdown produced
- [ ] Verdict determined (PASS / CAUTIOUS_PASS / FAIL)
- [ ] Results saved to outputs/holdout_test/
- [ ] STATUS.md updated with holdout results
- [ ] If PASS: note "READY FOR PHASE 3"
- [ ] Holdout set marked as SPENT in STATUS.md (cannot be reused)
