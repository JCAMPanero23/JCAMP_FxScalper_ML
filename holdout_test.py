"""
HOLDOUT TEST — LONG Model Final Evaluation
=============================================

This script runs the final generalization test on unseen data (Oct 2025 – Mar 2026).
The model trained here will be the same as what passed Gate A in walk-forward CV.

CRITICAL RULES:
- Run this ONCE. No re-runs with different parameters.
- Use EXACT hyperparameters from src/train.py
- Handle timeouts as losses (matching CV: timeout_as="loss")
- Use threshold 0.65 (the Gate A threshold)
- Train on ALL data Jan 2023 – Sep 2025
"""

import pandas as pd
import numpy as np
import lightgbm as lgb
from lightgbm import LGBMClassifier
from joblib import dump
from pathlib import Path
import json
from datetime import datetime

# ============================================================================
# STEP 0: SETUP
# ============================================================================

print("="*70)
print("HOLDOUT TEST — LONG MODEL FINAL EVALUATION")
print("="*70)
print(f"Started: {datetime.now().isoformat()}\n")

DATA_PATH = Path("data/DataCollector_EURUSD_M5_20230101_220446.csv")
MODEL_OUTPUT_DIR = Path("models")
OUTPUT_DIR = Path("outputs/holdout_test")

MODEL_OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# STEP 1: LOAD AND SPLIT DATA
# ============================================================================

print("Loading data...")
df = pd.read_csv(DATA_PATH, parse_dates=['timestamp'])
df = df.sort_values('timestamp').reset_index(drop=True)

# Define splits
TRAIN_END = pd.Timestamp('2025-09-30 23:59:59')
HOLDOUT_END = pd.Timestamp('2026-03-31 23:59:59')

df_train = df[df.timestamp <= TRAIN_END].reset_index(drop=True)
df_holdout = df[(df.timestamp > TRAIN_END) & (df.timestamp <= HOLDOUT_END)].reset_index(drop=True)

print(f"Train set:   {len(df_train):,} rows  ({df_train.timestamp.min().date()} to {df_train.timestamp.max().date()})")
print(f"Holdout set: {len(df_holdout):,} rows ({df_holdout.timestamp.min().date()} to {df_holdout.timestamp.max().date()})")

# Verify holdout integrity
assert len(df_holdout) > 30000, f"Holdout too small: {len(df_holdout)}"
assert df_holdout.timestamp.min() > TRAIN_END, "Holdout overlaps training!"
print("[OK] Holdout integrity verified\n")

# ============================================================================
# STEP 2: FEATURE COLUMNS
# ============================================================================

# Label columns to exclude
LABEL_COLS = ['timestamp', 'symbol',
              'outcome_long', 'bars_to_outcome_long',
              'outcome_short', 'bars_to_outcome_short']

FEATURE_COLS = [c for c in df.columns if c not in LABEL_COLS]
print(f"Features extracted: {len(FEATURE_COLS)}")
assert len(FEATURE_COLS) == 46, f"Expected 46 features, got {len(FEATURE_COLS)}"
print(f"Feature list: {FEATURE_COLS[:5]}... (showing first 5)\n")

# ============================================================================
# STEP 3: PREPARE TRAINING DATA
# ============================================================================

print("Preparing training data...")

# Handle timeouts: timeout_as="loss" (match CV behavior)
# This means: win=1, loss=0, timeout=0
train_mask = df_train['outcome_long'].isin(['win', 'loss', 'timeout'])
df_train_filtered = df_train[train_mask].reset_index(drop=True)

# Convert to binary labels (matching timeout_as="loss" from CV)
X_train = df_train_filtered[FEATURE_COLS]
y_train = (df_train_filtered['outcome_long'] == 'win').astype(int)

print(f"Training samples: {len(X_train):,}")
print(f"Label distribution: {y_train.mean():.1%} wins, {(1-y_train.mean()):.1%} losses/timeouts")
print(f"Timeout count in training: {(df_train_filtered['outcome_long'] == 'timeout').sum():,}\n")

# ============================================================================
# STEP 4: TRAIN FINAL MODEL (EXACT HYPERPARAMS FROM src/train.py)
# ============================================================================

print("Training final model on full train set (Jan 2023 – Sep 2025)...")
print("Using hyperparameters from src/train.py lines 36-51...\n")

params = {
    'objective': 'binary',
    'metric': 'auc',
    'boosting_type': 'gbdt',
    'num_leaves': 63,
    'max_depth': 9,
    'learning_rate': 0.03,
    'n_estimators': 1000,
    'min_child_samples': 100,
    'subsample': 0.8,
    'colsample_bytree': 0.7,
    'reg_alpha': 1.0,
    'reg_lambda': 1.0,
    'random_state': 42,
    'verbose': -1,
}

print("Hyperparameters:")
for k, v in params.items():
    print(f"  {k}: {v}")
print()

model = LGBMClassifier(**params)
model.fit(X_train, y_train)

model_path = MODEL_OUTPUT_DIR / "eurusd_long_v04_final_holdout.joblib"
dump(model, model_path)
print(f"[OK] Model trained and saved to {model_path}\n")

# ============================================================================
# STEP 5: PREDICT ON HOLDOUT
# ============================================================================

print("Generating predictions on holdout set (Oct 2025 – Mar 2026)...")

X_holdout = df_holdout[FEATURE_COLS]
p_win_long = model.predict_proba(X_holdout)[:, 1]

df_holdout = df_holdout.copy()
df_holdout['p_win_long'] = p_win_long

print(f"\nPrediction distribution:")
print(f"  Mean p_win:    {p_win_long.mean():.4f}")
print(f"  Median:        {np.median(p_win_long):.4f}")
print(f"  Std Dev:       {np.std(p_win_long):.4f}")
print(f"  Min / Max:     {p_win_long.min():.4f} / {p_win_long.max():.4f}")
print(f"\n  P > 0.55:      {(p_win_long > 0.55).sum():,} bars ({(p_win_long > 0.55).mean():.1%})")
print(f"  P > 0.60:      {(p_win_long > 0.60).sum():,} bars ({(p_win_long > 0.60).mean():.1%})")
print(f"  P > 0.65:      {(p_win_long > 0.65).sum():,} bars ({(p_win_long > 0.65).mean():.1%})\n")

# ============================================================================
# STEP 6: CALCULATE EXPECTANCY @ THRESHOLD 0.65
# ============================================================================

THRESHOLD = 0.65

# Filter to "traded" bars
traded = df_holdout[df_holdout['p_win_long'] > THRESHOLD].copy()
n_trades = len(traded)

print("="*70)
print(f"HOLDOUT TEST — LONG MODEL @ THRESHOLD {THRESHOLD}")
print("="*70)
print(f"Period: {df_holdout.timestamp.min().date()} to {df_holdout.timestamp.max().date()}")
print(f"Total bars: {len(df_holdout):,}")
print(f"Traded bars: {n_trades:,} ({n_trades/len(df_holdout):.1%})")
print()

if n_trades == 0:
    print("[ERROR] ERROR: No trades generated. Model may not be calibrated for this period.")
    verdict = "ERROR"
else:
    # Assign R per trade (matching CV R calculation)
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

    # Profit factor
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

    # Print results
    print(f"--- RESULTS ---")
    print(f"Trades:           {n_trades}")
    print(f"  Wins:           {n_wins} ({win_rate:.1%})")
    print(f"  Losses:         {n_losses} ({loss_rate:.1%})")
    print(f"  Timeouts:       {n_timeouts} ({timeout_rate:.1%})")
    print(f"")
    print(f"Expectancy:       {expectancy:+.3f}R per trade")
    print(f"Net R:            {net_r:+.1f}R")
    print(f"Profit Factor:    {profit_factor:.2f}")
    print(f"Max Consec Loss:  {max_consec}")
    print(f"Max Drawdown:     {max_dd_r:.1f}R")
    print(f"")

    # ============================================================================
    # STEP 7: VERDICT
    # ============================================================================

    cv_estimate = 0.269  # From Gate A evaluation

    pct_of_cv = expectancy / cv_estimate * 100 if cv_estimate != 0 else 0
    within_30 = abs(expectancy - cv_estimate) / cv_estimate <= 0.30

    print(f"--- VERDICT ---")
    print(f"CV estimate (Gate A):    +{cv_estimate:.3f}R")
    print(f"Holdout result:          {expectancy:+.3f}R")
    print(f"% of CV estimate:        {pct_of_cv:.0f}%")
    print(f"Within ±30% tolerance:   {'YES [OK]' if within_30 else 'NO [FAIL]'}")
    print(f"")

    if expectancy > 0 and within_30:
        print(f"[OK] PASS — Holdout confirms CV estimate.")
        print(f"   Proceed to Phase 3 (FastAPI) and live deployment.")
        verdict = "PASS"
    elif expectancy > 0 and not within_30:
        if pct_of_cv < 100:
            print(f"[WARNING] CAUTIOUS_PASS — Positive but below ±30% tolerance.")
            print(f"   Proceed with tighter risk limits and closer monitoring.")
            verdict = "CAUTIOUS_PASS"
        else:
            print(f"[WARNING] VERIFY — Very positive but well above CV estimate.")
            print(f"   Possible data issue. Verify before proceeding.")
            verdict = "VERIFY"
    elif expectancy <= 0:
        print(f"[FAIL] FAIL — Holdout shows no edge.")
        print(f"   Do NOT deploy. Return to diagnosis.")
        verdict = "FAIL"

    # ============================================================================
    # STEP 8: MONTHLY BREAKDOWN
    # ============================================================================

    print(f"\n--- MONTHLY BREAKDOWN ---")
    traded['month'] = traded['timestamp'].dt.to_period('M')
    monthly = traded.groupby('month').agg(
        trades=('r', 'count'),
        wins=('outcome_long', lambda x: (x == 'win').sum()),
        losses=('outcome_long', lambda x: (x == 'loss').sum()),
        timeouts=('outcome_long', lambda x: (x == 'timeout').sum()),
        win_rate=('outcome_long', lambda x: (x == 'win').mean()),
        expectancy=('r', 'mean'),
        net_r=('r', 'sum'),
    )

    print(monthly.to_string())
    print()

    # Flag anomalies
    for idx, row in monthly.iterrows():
        if row['trades'] < 20:
            print(f"  [WARNING] {idx}: Only {int(row['trades'])} trades (low sample)")
        if row['expectancy'] < -0.15:
            print(f"  [WARNING] {idx}: Expectancy {row['expectancy']:+.3f}R (below -0.15R threshold)")

    # ============================================================================
    # STEP 9: SAVE RESULTS
    # ============================================================================

    print(f"\n--- SAVING RESULTS ---")

    # Save traded bars
    traded.to_csv(OUTPUT_DIR / "holdout_traded_bars.csv", index=False)
    print(f"[OK] Saved: holdout_traded_bars.csv ({len(traded):,} rows)")

    # Save equity curve
    traded[['timestamp', 'p_win_long', 'outcome_long', 'r', 'cum_r']].to_csv(
        OUTPUT_DIR / "holdout_equity_curve.csv", index=False)
    print(f"[OK] Saved: holdout_equity_curve.csv")

    # Save summary JSON
    summary = {
        'test_date': datetime.now().isoformat(),
        'test_period': f"{df_holdout.timestamp.min().date()} to {df_holdout.timestamp.max().date()}",
        'threshold': THRESHOLD,
        'n_trades': int(n_trades),
        'n_wins': int(n_wins),
        'n_losses': int(n_losses),
        'n_timeouts': int(n_timeouts),
        'win_rate': f"{win_rate:.1%}",
        'loss_rate': f"{loss_rate:.1%}",
        'timeout_rate': f"{timeout_rate:.1%}",
        'expectancy': f"{expectancy:+.3f}R",
        'net_r': f"{net_r:+.1f}R",
        'profit_factor': f"{profit_factor:.2f}",
        'max_consecutive_losses': int(max_consec),
        'max_drawdown_r': f"{max_dd_r:.1f}R",
        'cv_estimate': f"+{cv_estimate:.3f}R",
        'pct_of_cv': f"{pct_of_cv:.0f}%",
        'within_30pct_tolerance': str(within_30),
        'verdict': verdict,
        'model_path': str(model_path),
    }

    with open(OUTPUT_DIR / "holdout_summary.json", 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"[OK] Saved: holdout_summary.json")

    # Save monthly breakdown
    monthly.to_csv(OUTPUT_DIR / "holdout_monthly_breakdown.csv")
    print(f"[OK] Saved: holdout_monthly_breakdown.csv")

    print(f"\nAll results saved to: {OUTPUT_DIR}/\n")

# ============================================================================
# FINAL STATUS
# ============================================================================

print("="*70)
print(f"Holdout test complete. Verdict: {verdict}")
print("="*70)
