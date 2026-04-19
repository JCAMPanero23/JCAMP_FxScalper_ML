"""
Phase 2 Step 1: v05 Model Retraining with Walk-Forward CV

Trains LONG-only model using:
- v05 labels: TP=4.5×ATR (win=+3.0R), SL=1.5×ATR (loss=-1.0R)
- Risk params: Monthly DD=6%, Consecutive loss=8
- Purged walk-forward CV with 5 folds (per Errata #6)
- Gate A criteria: mean ROC-AUC > 0.55, positive expectancy ≥4 folds

Output: eurusd_long_v05.joblib (LONG only - SHORT failed Gate A)
"""

import sys
sys.path.append('.')

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from pathlib import Path

from src.data_loader import load_datacollector_csv, get_data_splits
from src.labels import collapse_to_binary, print_label_summary
from src.features import get_feature_columns
from src.cv import PurgedWalkForward
from src.train import train_lightgbm, evaluate_model, save_model, get_feature_importance
from src.evaluate import calculate_trading_metrics, simulate_equity_curve, plot_equity_curve, print_performance_summary

# =============================================================================
# Configuration
# =============================================================================

CSV_PATH = 'data/DataCollector_EURUSD_M5_20230101_220446.csv'
OUTPUT_DIR = Path('models')
OUTPUT_DIR.mkdir(exist_ok=True)

MODEL_NAME = 'eurusd_long_v05.joblib'
RESULTS_FILE = 'v05_retrain_results.md'

# v05 Parameters
V05_PARAMS = {
    'tp_atr_mult': 4.5,         # TP barrier (was 3.0 in v04)
    'sl_atr_mult': 1.5,         # SL barrier
    'risk_reward': 3.0,         # Win=+3.0R (was +2.0R in v04)
    'monthly_dd_pct': 6.0,      # Was 8.0 in v04
    'consec_loss_limit': 8,     # Was 6 in v04
    'daily_loss_limit_r': -2.0  # Unchanged
}

# CV Configuration
CV_PARAMS = {
    'n_splits': 5,              # Errata #6: verify actual fold count
    'embargo_bars': 48,         # Max bars_to_outcome
    'test_size': 0.15
}

# Gate A Acceptance Criteria
GATE_A = {
    'min_roc_auc': 0.55,
    'min_positive_folds': 4,    # Out of 5
    'min_expectancy_r': 0.09
}

print("=" * 70)
print("Phase 2 Step 1: v05 Model Retraining")
print("=" * 70)
print(f"CSV: {CSV_PATH}")
print(f"TP multiplier: {V05_PARAMS['tp_atr_mult']}×ATR (was 3.0)")
print(f"Risk/reward: {V05_PARAMS['risk_reward']}R on win (was 2.0)")
print(f"CV: {CV_PARAMS['n_splits']} folds")
print(f"Gate A: ROC-AUC > {GATE_A['min_roc_auc']}, expectancy > +{GATE_A['min_expectancy_r']}R")
print()

# =============================================================================
# 1. Load Data
# =============================================================================

print("\n[1/4] Loading DataCollector CSV...")
df = load_datacollector_csv(CSV_PATH)
print(f"  Loaded {len(df):,} rows")
print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

# Split into train/CV and holdout
train_cv, held_out_test, live_forward = get_data_splits(df)
print(f"\n  Train/CV: {len(train_cv):,} rows ({train_cv['timestamp'].min()} to {train_cv['timestamp'].max()})")
print(f"  Holdout:  {len(held_out_test):,} rows ({held_out_test['timestamp'].min()} to {held_out_test['timestamp'].max()})")
print(f"  WARNING: Holdout is NOT used in this training (single-use for Step 2)")

# Label summary
print_label_summary(train_cv)

# =============================================================================
# 2. Setup Cross-Validation
# =============================================================================

print("\n[2/4] Setting up walk-forward CV...")
cv = PurgedWalkForward(
    n_splits=CV_PARAMS['n_splits'],
    embargo_bars=CV_PARAMS['embargo_bars'],
    test_size=CV_PARAMS['test_size']
)
print(f"  Folds: {cv.n_splits}")
print(f"  Embargo: {cv.embargo_bars} bars")
print(f"  Test size: {cv.test_size}")

# =============================================================================
# 3. Walk-Forward CV - LONG Direction
# =============================================================================

print("\n[3/4] Running walk-forward CV for LONG direction...")

# Prepare LONG data
df_long = collapse_to_binary(train_cv, direction="long", timeout_as="loss")
features = get_feature_columns(df_long)

X = df_long[features]
y = df_long['label']
bars_to_outcome = df_long['bars_to_outcome_long']

print(f"  Features: {len(features)}")
print(f"  Samples: {len(X):,}")
print(f"  Win rate (baseline): {y.mean()*100:.1f}%")

# Run CV
print("\n  Running CV folds...\n")
cv_results_long = []

for fold_idx, (train_idx, test_idx) in enumerate(cv.split(X, y, bars_to_outcome), 1):
    print(f"  Fold {fold_idx}/{CV_PARAMS['n_splits']}:", end=" ")

    X_train_fold = X.iloc[train_idx]
    y_train_fold = y.iloc[train_idx]
    X_test_fold = X.iloc[test_idx]
    y_test_fold = y.iloc[test_idx]

    # Train model
    model = train_lightgbm(X_train_fold, y_train_fold)

    # Evaluate
    metrics = evaluate_model(model, X_test_fold, y_test_fold, verbose=False)

    # Trading metrics (using v05 risk_reward=3.0)
    y_pred = model.predict(X_test_fold)
    trading_metrics = calculate_trading_metrics(
        y_test_fold.values, y_pred,
        risk_reward=V05_PARAMS['risk_reward'],  # v05: 3.0 (not 2.0)
        threshold=0.65  # Gate A threshold
    )

    fold_result = {
        'fold': fold_idx,
        'roc_auc': metrics['roc_auc'],
        'accuracy': metrics['accuracy'],
        'win_rate': trading_metrics['win_rate'],
        'profit_factor': trading_metrics['profit_factor'],
        'expectancy_r': trading_metrics['expectancy_r'],
        'net_profit_r': trading_metrics['net_profit_r'],
        'n_trades': trading_metrics['total_trades']
    }
    cv_results_long.append(fold_result)

    print(f"AUC={metrics['roc_auc']:.4f}, Exp={trading_metrics['expectancy_r']:+.3f}R, PF={trading_metrics['profit_factor']:.2f}")

# Aggregate results
cv_results_long_df = pd.DataFrame(cv_results_long)
mean_auc = cv_results_long_df['roc_auc'].mean()
mean_exp = cv_results_long_df['expectancy_r'].mean()
positive_folds = (cv_results_long_df['expectancy_r'] > 0).sum()

print("\n  " + "=" * 60)
print(f"  LONG Direction - CV Summary")
print("  " + "=" * 60)
print(f"  Mean ROC-AUC: {mean_auc:.4f} ± {cv_results_long_df['roc_auc'].std():.4f}")
print(f"  Mean Expectancy: {mean_exp:+.3f}R")
print(f"  Positive expectancy folds: {positive_folds}/{CV_PARAMS['n_splits']}")
print(f"  Mean Win rate: {cv_results_long_df['win_rate'].mean()*100:.1f}%")
print(f"  Mean Profit factor: {cv_results_long_df['profit_factor'].mean():.2f}")

# =============================================================================
# 4. Gate A Check and Final Model Training
# =============================================================================

print("\n[4/4] Checking Gate A acceptance criteria...")

auc_ok = mean_auc > GATE_A['min_roc_auc']
folds_ok = positive_folds >= GATE_A['min_positive_folds']
exp_ok = mean_exp > GATE_A['min_expectancy_r']

print(f"\n  ROC-AUC > {GATE_A['min_roc_auc']}: {auc_ok} ({mean_auc:.4f})")
print(f"  Positive expectancy >= {GATE_A['min_positive_folds']}/5: {folds_ok} ({positive_folds}/5)")
print(f"  Mean expectancy > +{GATE_A['min_expectancy_r']}R: {exp_ok} ({mean_exp:+.3f}R)")

if auc_ok and folds_ok and exp_ok:
    print(f"\n  [PASSED] GATE A - Training final model on full train/CV set")

    # Train final LONG model
    df_long_full = collapse_to_binary(train_cv, direction="long", timeout_as="loss")
    X_long_full = df_long_full[features]
    y_long_full = df_long_full['label']

    print(f"  Training on {len(X_long_full):,} samples...")
    final_model_long = train_lightgbm(X_long_full, y_long_full)

    # Save model
    model_path = OUTPUT_DIR / MODEL_NAME
    save_model(
        final_model_long,
        str(model_path),
        metadata={
            'symbol': 'EURUSD',
            'direction': 'long',
            'version': 'v05',
            'trained_date': datetime.now().isoformat(),
            'tp_atr_mult': V05_PARAMS['tp_atr_mult'],
            'sl_atr_mult': V05_PARAMS['sl_atr_mult'],
            'risk_reward': V05_PARAMS['risk_reward'],
            'n_features': len(features),
            'n_samples': len(X_long_full),
            'cv_mean_auc': mean_auc,
            'cv_mean_expectancy': mean_exp,
            'cv_positive_folds': positive_folds,
            'gate_a_passed': True
        }
    )
    print(f"  [OK] Model saved to {model_path}")

    # Feature importance
    importance_long = get_feature_importance(final_model_long, features, top_n=15)
    print(f"\n  Top 15 features:")
    print(importance_long.to_string(index=False))

    gate_a_status = "PASSED"
else:
    print(f"\n  [FAILED] GATE A - Not training final model")
    gate_a_status = "FAILED"

# =============================================================================
# Results Summary
# =============================================================================

print("\n" + "=" * 70)
print("PHASE 2 STEP 1 SUMMARY")
print("=" * 70)
print(f"Direction: LONG (SHORT failed Gate A in v04)")
print(f"Data: v05 labels (TP=4.5×ATR, risk_reward=3.0R)")
print(f"CV Folds: {CV_PARAMS['n_splits']}")
print(f"Gate A Status: {gate_a_status}")
print(f"\nCV Results:")
print(f"  Mean ROC-AUC: {mean_auc:.4f}")
print(f"  Mean Expectancy: {mean_exp:+.3f}R")
print(f"  Positive folds: {positive_folds}/{CV_PARAMS['n_splits']}")
print(f"\nNext: Step 2 - Run simulate.py on holdout (Oct 2025 - Mar 2026)")
print("=" * 70)

# Write detailed results to markdown
with open(RESULTS_FILE, 'w') as f:
    f.write("# Phase 2 Step 1 - v05 Model Retraining Results\n\n")
    f.write(f"**Date:** {datetime.now().isoformat()}\n")
    f.write(f"**Status:** {gate_a_status}\n\n")
    f.write("## Configuration\n\n")
    f.write(f"- CSV: `{CSV_PATH}`\n")
    f.write(f"- TP multiplier: {V05_PARAMS['tp_atr_mult']}×ATR\n")
    f.write(f"- Risk/reward: {V05_PARAMS['risk_reward']}R on win\n")
    f.write(f"- CV folds: {CV_PARAMS['n_splits']}\n\n")
    f.write("## CV Results - LONG Direction\n\n")
    f.write(cv_results_long_df.to_markdown(index=False))
    f.write(f"\n\n### Summary\n\n")
    f.write(f"- Mean ROC-AUC: {mean_auc:.4f}\n")
    f.write(f"- Mean Expectancy: {mean_exp:+.3f}R\n")
    f.write(f"- Positive expectancy folds: {positive_folds}/5\n")
    f.write(f"- Gate A: **{gate_a_status}**\n\n")
    if auc_ok and folds_ok and exp_ok:
        f.write(f"## Model Output\n\n")
        f.write(f"- Saved to: `models/{MODEL_NAME}`\n")
        f.write(f"- Trained on: {len(X_long_full):,} samples\n\n")

print(f"\nDetailed results saved to {RESULTS_FILE}")
