"""
Phase 2 Re-run with Corrected Metrics
Fixes Bug 1, 2, 3 from PHASE2_CORRECTIONS.md
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split

from src.data_loader import load_datacollector_csv, get_data_splits
from src.labels import collapse_to_binary
from src.features import get_feature_columns
from src.cv import PurgedWalkForward
from src.train import train_lightgbm, evaluate_model
from src.evaluate import calculate_trading_metrics, plot_threshold_sensitivity, simulate_equity_curve
import matplotlib.pyplot as plt

print("="*70)
print("Phase 2 - CORRECTED Analysis with Fixed Metrics")
print("="*70)

# Load data
print("\n1. Loading data...")
csv_path = 'data/DataCollector_EURUSD_M5_20230101_220400.csv'
df = load_datacollector_csv(csv_path)
train_cv, held_out_test, live_forward = get_data_splits(df)
print(f"   Train/CV: {len(train_cv):,} rows")

# Get features
features = get_feature_columns(train_cv)
print(f"   Features: {len(features)}")

#==============================================================================
# BASELINE 70/30 SPLIT - LONG Model
#==============================================================================

print("\n" + "="*70)
print("2. LONG Model - Baseline 70/30 Split")
print("="*70)

df_long = collapse_to_binary(train_cv, direction="long", timeout_as="loss")
X_long = df_long[features]
y_long = df_long['label']

X_long_tr, X_long_te, y_long_tr, y_long_te = train_test_split(
    X_long, y_long, test_size=0.3, random_state=42, shuffle=False
)
X_long_tr_sub, X_long_val, y_long_tr_sub, y_long_val = train_test_split(
    X_long_tr, y_long_tr, test_size=0.2, random_state=42, shuffle=False
)

print(f"\nTraining LONG model (tuned hyperparameters)...")
model_long = train_lightgbm(X_long_tr_sub, y_long_tr_sub, X_long_val, y_long_val)

# Evaluate
metrics_long = evaluate_model(model_long, X_long_te, y_long_te, verbose=True)

# Get probabilities
y_pred_proba_long = model_long.predict_proba(X_long_te)[:, 1]

# Trading metrics at multiple thresholds
print("\n--- LONG - Trading Metrics at Various Thresholds (CORRECTED) ---")
print(f"{'threshold':>10} {'trades':>8} {'win_rate':>9} {'pf':>7} {'expectancy':>11} {'net_R':>10}")
print("-" * 70)

for thr in [0.50, 0.55, 0.60, 0.65, 0.70]:
    m = calculate_trading_metrics(
        y_long_te.values,
        y_pred_proba_long,
        threshold=thr,
        risk_reward=2.0,
        commission_r=0.04,  # ~4% of R for FP Markets Raw
    )
    print(f"{thr:>10.2f} {m['total_trades']:>8} {m['win_rate']:>9.2%} "
          f"{m['profit_factor']:>7.2f} {m['expectancy_r']:>11.3f} "
          f"{m['net_profit_r']:>10.1f}")

# Threshold sensitivity plot
print("\nGenerating threshold sensitivity plot for LONG...")
fig_long, sens_df_long = plot_threshold_sensitivity(
    y_long_te.values,
    y_pred_proba_long,
    risk_reward=2.0,
    commission_r=0.04,
    title="LONG - Threshold Sensitivity (70/30 hold-out)",
)
plt.savefig('long_threshold_sensitivity.png', dpi=150, bbox_inches='tight')
print("   Saved to: long_threshold_sensitivity.png")

# Identify profitable region
profitable_long = sens_df_long[
    (sens_df_long["expectancy_r"] > 0) & (sens_df_long["n_trades"] > 100)
]
if len(profitable_long) > 0:
    print(f"\nProfitable threshold range: "
          f"{profitable_long['threshold'].min():.2f} to {profitable_long['threshold'].max():.2f}")
    print(f"Plateau width: {profitable_long['threshold'].max() - profitable_long['threshold'].min():.2f}")
else:
    print("\n[WARN]  No profitable threshold range found with >100 trades")

#==============================================================================
# BASELINE 70/30 SPLIT - SHORT Model
#==============================================================================

print("\n" + "="*70)
print("3. SHORT Model - Baseline 70/30 Split")
print("="*70)

df_short = collapse_to_binary(train_cv, direction="short", timeout_as="loss")
X_short = df_short[features]
y_short = df_short['label']

X_short_tr, X_short_te, y_short_tr, y_short_te = train_test_split(
    X_short, y_short, test_size=0.3, random_state=42, shuffle=False
)
X_short_tr_sub, X_short_val, y_short_tr_sub, y_short_val = train_test_split(
    X_short_tr, y_short_tr, test_size=0.2, random_state=42, shuffle=False
)

print(f"\nTraining SHORT model (tuned hyperparameters)...")
model_short = train_lightgbm(X_short_tr_sub, y_short_tr_sub, X_short_val, y_short_val)

# Evaluate
metrics_short = evaluate_model(model_short, X_short_te, y_short_te, verbose=True)

# Sanity check: metrics should NOT be identical
if abs(metrics_long['roc_auc'] - metrics_short['roc_auc']) < 0.0001:
    print("\n[WARN]  WARNING: LONG and SHORT metrics are identical! Scope bug!")
else:
    print(f"\n[OK] Sanity check passed: LONG AUC={metrics_long['roc_auc']:.4f}, SHORT AUC={metrics_short['roc_auc']:.4f}")

# Get probabilities
y_pred_proba_short = model_short.predict_proba(X_short_te)[:, 1]

# Trading metrics at multiple thresholds
print("\n--- SHORT - Trading Metrics at Various Thresholds (CORRECTED) ---")
print(f"{'threshold':>10} {'trades':>8} {'win_rate':>9} {'pf':>7} {'expectancy':>11} {'net_R':>10}")
print("-" * 70)

for thr in [0.50, 0.55, 0.60, 0.65, 0.70]:
    m = calculate_trading_metrics(
        y_short_te.values,
        y_pred_proba_short,
        threshold=thr,
        risk_reward=2.0,
        commission_r=0.04,
    )
    print(f"{thr:>10.2f} {m['total_trades']:>8} {m['win_rate']:>9.2%} "
          f"{m['profit_factor']:>7.2f} {m['expectancy_r']:>11.3f} "
          f"{m['net_profit_r']:>10.1f}")

# Threshold sensitivity plot
print("\nGenerating threshold sensitivity plot for SHORT...")
fig_short, sens_df_short = plot_threshold_sensitivity(
    y_short_te.values,
    y_pred_proba_short,
    risk_reward=2.0,
    commission_r=0.04,
    title="SHORT - Threshold Sensitivity (70/30 hold-out)",
)
plt.savefig('short_threshold_sensitivity.png', dpi=150, bbox_inches='tight')
print("   Saved to: short_threshold_sensitivity.png")

# Identify profitable region
profitable_short = sens_df_short[
    (sens_df_short["expectancy_r"] > 0) & (sens_df_short["n_trades"] > 100)
]
if len(profitable_short) > 0:
    print(f"\nProfitable threshold range: "
          f"{profitable_short['threshold'].min():.2f} to {profitable_short['threshold'].max():.2f}")
    print(f"Plateau width: {profitable_short['threshold'].max() - profitable_short['threshold'].min():.2f}")
else:
    print("\n[WARN]  No profitable threshold range found with >100 trades")

#==============================================================================
# WALK-FORWARD CV - LONG (CORRECTED)
#==============================================================================

print("\n" + "="*70)
print("4. Walk-Forward CV - LONG (CORRECTED METRICS)")
print("="*70)

cv = PurgedWalkForward(n_splits=6, embargo_bars=48, test_size=0.15)

df_long_full = collapse_to_binary(train_cv, direction="long", timeout_as="loss")
X_cv = df_long_full[features]
y_cv = df_long_full['label']
bars_cv = df_long_full['bars_to_outcome_long']

# Test at threshold = 0.55
threshold_test = 0.55
print(f"\nRunning 6-fold CV at threshold = {threshold_test}...")

cv_results_long = []

for fold_idx, (train_idx, test_idx) in enumerate(cv.split(X_cv, y_cv, bars_cv), 1):
    print(f"\n--- Fold {fold_idx}/6 ---")

    X_train_fold = X_cv.iloc[train_idx]
    y_train_fold = y_cv.iloc[train_idx]
    X_test_fold = X_cv.iloc[test_idx]
    y_test_fold = y_cv.iloc[test_idx]

    # Train
    model = train_lightgbm(X_train_fold, y_train_fold)

    # Evaluate
    metrics = evaluate_model(model, X_test_fold, y_test_fold, verbose=False)

    # CORRECTED trading metrics
    y_pred_proba_fold = model.predict_proba(X_test_fold)[:, 1]
    trading_metrics = calculate_trading_metrics(
        y_test_fold.values,
        y_pred_proba_fold,
        threshold=threshold_test,
        risk_reward=2.0,
        commission_r=0.04
    )

    cv_results_long.append({
        'fold': fold_idx,
        'roc_auc': metrics['roc_auc'],
        'n_trades': trading_metrics['total_trades'],
        'win_rate': trading_metrics['win_rate'],
        'profit_factor': trading_metrics['profit_factor'],
        'expectancy_r': trading_metrics['expectancy_r'],
        'net_profit_r': trading_metrics['net_profit_r'],
    })

    print(f"  ROC-AUC: {metrics['roc_auc']:.4f}")
    print(f"  Trades: {trading_metrics['total_trades']:,}")
    print(f"  Win rate: {trading_metrics['win_rate']*100:.1f}%")
    print(f"  PF: {trading_metrics['profit_factor']:.2f}")
    print(f"  Expectancy: {trading_metrics['expectancy_r']:+.3f}R")

cv_df_long = pd.DataFrame(cv_results_long)
print("\n" + "="*70)
print("LONG - Walk-Forward CV Summary (CORRECTED)")
print("="*70)
print(cv_df_long.to_string(index=False))
print(f"\nMean ROC-AUC: {cv_df_long['roc_auc'].mean():.4f} ± {cv_df_long['roc_auc'].std():.4f}")
print(f"Mean Expectancy: {cv_df_long['expectancy_r'].mean():+.3f}R")
print(f"Positive folds: {(cv_df_long['expectancy_r'] > 0).sum()}/6")

#==============================================================================
# WALK-FORWARD CV - SHORT (CORRECTED)
#==============================================================================

print("\n" + "="*70)
print("5. Walk-Forward CV - SHORT (CORRECTED METRICS)")
print("="*70)

df_short_full = collapse_to_binary(train_cv, direction="short", timeout_as="loss")
X_cv = df_short_full[features]
y_cv = df_short_full['label']
bars_cv = df_short_full['bars_to_outcome_short']

print(f"\nRunning 6-fold CV at threshold = {threshold_test}...")

cv_results_short = []

for fold_idx, (train_idx, test_idx) in enumerate(cv.split(X_cv, y_cv, bars_cv), 1):
    print(f"\n--- Fold {fold_idx}/6 ---")

    X_train_fold = X_cv.iloc[train_idx]
    y_train_fold = y_cv.iloc[train_idx]
    X_test_fold = X_cv.iloc[test_idx]
    y_test_fold = y_cv.iloc[test_idx]

    # Train
    model = train_lightgbm(X_train_fold, y_train_fold)

    # Evaluate
    metrics = evaluate_model(model, X_test_fold, y_test_fold, verbose=False)

    # CORRECTED trading metrics
    y_pred_proba_fold = model.predict_proba(X_test_fold)[:, 1]
    trading_metrics = calculate_trading_metrics(
        y_test_fold.values,
        y_pred_proba_fold,
        threshold=threshold_test,
        risk_reward=2.0,
        commission_r=0.04
    )

    cv_results_short.append({
        'fold': fold_idx,
        'roc_auc': metrics['roc_auc'],
        'n_trades': trading_metrics['total_trades'],
        'win_rate': trading_metrics['win_rate'],
        'profit_factor': trading_metrics['profit_factor'],
        'expectancy_r': trading_metrics['expectancy_r'],
        'net_profit_r': trading_metrics['net_profit_r'],
    })

    print(f"  ROC-AUC: {metrics['roc_auc']:.4f}")
    print(f"  Trades: {trading_metrics['total_trades']:,}")
    print(f"  Win rate: {trading_metrics['win_rate']*100:.1f}%")
    print(f"  PF: {trading_metrics['profit_factor']:.2f}")
    print(f"  Expectancy: {trading_metrics['expectancy_r']:+.3f}R")

cv_df_short = pd.DataFrame(cv_results_short)
print("\n" + "="*70)
print("SHORT - Walk-Forward CV Summary (CORRECTED)")
print("="*70)
print(cv_df_short.to_string(index=False))
print(f"\nMean ROC-AUC: {cv_df_short['roc_auc'].mean():.4f} ± {cv_df_short['roc_auc'].std():.4f}")
print(f"Mean Expectancy: {cv_df_short['expectancy_r'].mean():+.3f}R")
print(f"Positive folds: {(cv_df_short['expectancy_r'] > 0).sum()}/6")

#==============================================================================
# FINAL ASSESSMENT
#==============================================================================

print("\n" + "="*70)
print("FINAL ASSESSMENT - Phase 2 with CORRECTED Metrics")
print("="*70)

print("\nLONG Model:")
print(f"  ROC-AUC: {cv_df_long['roc_auc'].mean():.4f}")
print(f"  Expectancy: {cv_df_long['expectancy_r'].mean():+.3f}R")
print(f"  Positive folds: {(cv_df_long['expectancy_r'] > 0).sum()}/6")
if len(profitable_long) > 0:
    print(f"  Plateau width: {profitable_long['threshold'].max() - profitable_long['threshold'].min():.2f}")

print("\nSHORT Model:")
print(f"  ROC-AUC: {cv_df_short['roc_auc'].mean():.4f}")
print(f"  Expectancy: {cv_df_short['expectancy_r'].mean():+.3f}R")
print(f"  Positive folds: {(cv_df_short['expectancy_r'] > 0).sum()}/6")
if len(profitable_short) > 0:
    print(f"  Plateau width: {profitable_short['threshold'].max() - profitable_short['threshold'].min():.2f}")

print("\n" + "="*70)
print("Analysis complete. Review results above.")
print("="*70)
