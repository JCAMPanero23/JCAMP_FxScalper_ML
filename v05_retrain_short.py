"""
Phase 2 Step 1 (SHORT): v05 Model Retraining with Walk-Forward CV

Mirrors v05_retrain.py but for SHORT direction. SHORT failed Gate A on v0.3
features (only 2/5 folds positive — see notebooks/outputs/phase2_decision/
walk_forward_multi_threshold_short.csv). v0.4 added `h1_alignment_agreement`
specifically to filter the H1-uptrend regime that was killing SHORT folds 1/3/5.
This script re-runs the SHORT walk-forward at three thresholds to test whether
the new feature actually fixes fold consistency.

Gate A (per PHASE2_DECISION.md): positive_folds >= 4/5 at the chosen threshold.

Output:
  - eurusd_short_v05.joblib (only if Gate A passes at any threshold)
  - v05_retrain_short_results.md
"""

import sys
sys.path.append('.')

import pandas as pd
from datetime import datetime
from pathlib import Path

from src.data_loader import load_datacollector_csv, get_data_splits
from src.labels import collapse_to_binary, print_label_summary
from src.features import get_feature_columns
from src.cv import PurgedWalkForward
from src.train import train_lightgbm, evaluate_model, save_model, get_feature_importance
from src.evaluate import calculate_trading_metrics

# =============================================================================
# Configuration
# =============================================================================

CSV_PATH = 'data/DataCollector_EURUSD_M5_20230101_220446.csv'
OUTPUT_DIR = Path('models')
OUTPUT_DIR.mkdir(exist_ok=True)

MODEL_NAME = 'eurusd_short_v05.joblib'
RESULTS_FILE = 'v05_retrain_short_results.md'

V05_PARAMS = {
    'tp_atr_mult': 4.5,
    'sl_atr_mult': 1.5,
    'risk_reward': 3.0,
    'monthly_dd_pct': 6.0,
    'consec_loss_limit': 8,
    'daily_loss_limit_r': -2.0,
}

CV_PARAMS = {
    'n_splits': 6,
    'embargo_bars': 72,
    'test_size': 0.15,
}

# Test multiple thresholds — SHORT v0.3 only flipped 2/5 folds positive at any
# threshold, so threshold-only is not enough. We need to confirm the feature
# fix (h1_alignment_agreement) actually moves the fold-positive count.
THRESHOLDS_TO_TEST = [0.60, 0.65, 0.70]

GATE_A = {
    'min_roc_auc': 0.55,
    'min_positive_folds': 4,
    'min_expectancy_r': 0.09,
}

print("=" * 70)
print("Phase 2 Step 1 (SHORT): v05 Model Retraining")
print("=" * 70)
print(f"CSV: {CSV_PATH}")
print(f"Direction: SHORT (failed Gate A on v0.3, retesting with v0.4 features)")
print(f"Thresholds tested: {THRESHOLDS_TO_TEST}")
print(f"Gate A: ROC-AUC > {GATE_A['min_roc_auc']}, "
      f"positive folds >= {GATE_A['min_positive_folds']}/5, "
      f"expectancy > +{GATE_A['min_expectancy_r']}R")
print()

# =============================================================================
# 1. Load Data
# =============================================================================

print("\n[1/4] Loading DataCollector CSV...")
df = load_datacollector_csv(CSV_PATH)
print(f"  Loaded {len(df):,} rows")
print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

train_cv, held_out_test, live_forward = get_data_splits(df)
print(f"\n  Train/CV: {len(train_cv):,} rows "
      f"({train_cv['timestamp'].min()} to {train_cv['timestamp'].max()})")
print(f"  Holdout:  {len(held_out_test):,} rows "
      f"({held_out_test['timestamp'].min()} to {held_out_test['timestamp'].max()})")
print(f"  WARNING: Holdout is NOT used here (single-use for Step 2)")

print_label_summary(train_cv)

# =============================================================================
# 2. Setup Cross-Validation
# =============================================================================

print("\n[2/4] Setting up walk-forward CV...")
cv = PurgedWalkForward(
    n_splits=CV_PARAMS['n_splits'],
    embargo_bars=CV_PARAMS['embargo_bars'],
    test_size=CV_PARAMS['test_size'],
)
print(f"  Folds: {cv.n_splits}")
print(f"  Embargo: {cv.embargo_bars} bars")

# =============================================================================
# 3. Walk-Forward CV - SHORT Direction
# =============================================================================

print("\n[3/4] Running walk-forward CV for SHORT direction...")

df_short = collapse_to_binary(train_cv, direction="short", timeout_as="loss")
features = get_feature_columns(df_short)

X = df_short[features]
y = df_short['label']
bars_to_outcome = df_short['bars_to_outcome_short']

print(f"  Features: {len(features)}")
print(f"  Samples: {len(X):,}")
print(f"  Win rate (baseline): {y.mean()*100:.1f}%")

# Train fold models ONCE; score each at every threshold so we don't retrain.
fold_models = []
fold_test_data = []

print("\n  Training fold models...\n")
for fold_idx, (train_idx, test_idx) in enumerate(cv.split(X, y, bars_to_outcome), 1):
    X_train_fold = X.iloc[train_idx]
    y_train_fold = y.iloc[train_idx]
    X_test_fold = X.iloc[test_idx]
    y_test_fold = y.iloc[test_idx]

    model = train_lightgbm(X_train_fold, y_train_fold)
    metrics = evaluate_model(model, X_test_fold, y_test_fold, verbose=False)

    fold_models.append(model)
    fold_test_data.append((X_test_fold, y_test_fold, metrics))

    print(f"  Fold {fold_idx}/{CV_PARAMS['n_splits']}: AUC={metrics['roc_auc']:.4f}")

# Score every fold at every threshold
results_by_threshold = {}

for threshold in THRESHOLDS_TO_TEST:
    print(f"\n  --- Threshold {threshold} ---")
    fold_results = []

    for fold_idx, (X_test_fold, y_test_fold, metrics) in enumerate(fold_test_data, 1):
        model = fold_models[fold_idx - 1]
        # FIX: .predict() returns hard 0/1 labels — use predict_proba so the
        # threshold filter actually does something.
        y_pred = model.predict_proba(X_test_fold)[:, 1]

        trading_metrics = calculate_trading_metrics(
            y_test_fold.values, y_pred,
            risk_reward=V05_PARAMS['risk_reward'],
            threshold=threshold,
        )

        fold_results.append({
            'fold': fold_idx,
            'roc_auc': metrics['roc_auc'],
            'accuracy': metrics['accuracy'],
            'win_rate': trading_metrics['win_rate'],
            'profit_factor': trading_metrics['profit_factor'],
            'expectancy_r': trading_metrics['expectancy_r'],
            'net_profit_r': trading_metrics['net_profit_r'],
            'n_trades': trading_metrics['total_trades'],
        })

        print(f"    Fold {fold_idx}: "
              f"trades={trading_metrics['total_trades']}, "
              f"win%={trading_metrics['win_rate']*100:.1f}, "
              f"exp={trading_metrics['expectancy_r']:+.3f}R, "
              f"PF={trading_metrics['profit_factor']:.2f}")

    df_results = pd.DataFrame(fold_results)
    mean_auc = df_results['roc_auc'].mean()
    mean_exp = df_results['expectancy_r'].mean()
    positive_folds = (df_results['expectancy_r'] > 0).sum()
    worst_exp = df_results['expectancy_r'].min()
    worst_net_r = df_results['net_profit_r'].min()

    results_by_threshold[threshold] = {
        'df': df_results,
        'mean_auc': mean_auc,
        'mean_exp': mean_exp,
        'positive_folds': positive_folds,
        'worst_exp': worst_exp,
        'worst_net_r': worst_net_r,
    }

    print(f"\n    Mean AUC: {mean_auc:.4f} | Mean Exp: {mean_exp:+.3f}R | "
          f"Positive: {positive_folds}/{CV_PARAMS['n_splits']} | "
          f"Worst fold: {worst_exp:+.3f}R ({worst_net_r:+.1f}R net)")

# =============================================================================
# 4. Gate A Check — Pick Best Threshold That Passes
# =============================================================================

print("\n[4/4] Checking Gate A across thresholds...")
print()
print(f"  {'Threshold':<10} {'Mean AUC':>9} {'Mean Exp':>10} "
      f"{'Pos folds':>10} {'Worst Exp':>10} {'Gate A':>8}")
print("  " + "-" * 62)

best_threshold = None
best_score = -float('inf')

for thr, r in results_by_threshold.items():
    auc_ok = r['mean_auc'] > GATE_A['min_roc_auc']
    folds_ok = r['positive_folds'] >= GATE_A['min_positive_folds']
    exp_ok = r['mean_exp'] > GATE_A['min_expectancy_r']
    passed = auc_ok and folds_ok and exp_ok

    print(f"  {thr:<10} {r['mean_auc']:>9.4f} {r['mean_exp']:>+10.3f} "
          f"{r['positive_folds']:>10} {r['worst_exp']:>+10.3f} "
          f"{'PASS' if passed else 'FAIL':>8}")

    # Tiebreak by worst-fold expectancy (per Correction 4 in PHASE2_DECISION)
    if passed and r['worst_exp'] > best_score:
        best_score = r['worst_exp']
        best_threshold = thr

# =============================================================================
# 5. Train Final Model (only if Gate A passed at some threshold)
# =============================================================================

if best_threshold is not None:
    print(f"\n  [PASSED] Gate A at threshold={best_threshold} "
          f"(best worst-fold exp: {best_score:+.3f}R)")
    print(f"  Training final SHORT model on full train/CV set...")

    df_short_full = collapse_to_binary(train_cv, direction="short", timeout_as="loss")
    X_short_full = df_short_full[features]
    y_short_full = df_short_full['label']

    final_model = train_lightgbm(X_short_full, y_short_full)
    chosen = results_by_threshold[best_threshold]

    model_path = OUTPUT_DIR / MODEL_NAME
    save_model(
        final_model,
        str(model_path),
        metadata={
            'symbol': 'EURUSD',
            'direction': 'short',
            'version': 'v05',
            'trained_date': datetime.now().isoformat(),
            'tp_atr_mult': V05_PARAMS['tp_atr_mult'],
            'sl_atr_mult': V05_PARAMS['sl_atr_mult'],
            'risk_reward': V05_PARAMS['risk_reward'],
            'recommended_threshold': best_threshold,
            'n_features': len(features),
            'n_samples': len(X_short_full),
            'cv_mean_auc': chosen['mean_auc'],
            'cv_mean_expectancy': chosen['mean_exp'],
            'cv_positive_folds': int(chosen['positive_folds']),
            'cv_worst_fold_expectancy': chosen['worst_exp'],
            'gate_a_passed': True,
        },
    )
    print(f"  [OK] Model saved to {model_path}")

    importance = get_feature_importance(final_model, features, top_n=15)
    print(f"\n  Top 15 features:")
    print(importance.to_string(index=False))

    gate_a_status = f"PASSED at threshold={best_threshold}"
else:
    print(f"\n  [FAILED] Gate A at all tested thresholds.")
    print(f"  v0.4 features did not fix SHORT fold-consistency on 2023 data.")
    print(f"  Recommendation: defer SHORT until v0.6 retrain on 2024-2026 data.")
    gate_a_status = "FAILED"

# =============================================================================
# Results Summary (markdown)
# =============================================================================

print("\n" + "=" * 70)
print("PHASE 2 STEP 1 (SHORT) SUMMARY")
print("=" * 70)
print(f"Direction: SHORT")
print(f"Gate A Status: {gate_a_status}")
print(f"Tested thresholds: {THRESHOLDS_TO_TEST}")
print("=" * 70)

with open(RESULTS_FILE, 'w') as f:
    f.write("# Phase 2 Step 1 (SHORT) - v05 Model Retraining Results\n\n")
    f.write(f"**Date:** {datetime.now().isoformat()}\n")
    f.write(f"**Status:** {gate_a_status}\n\n")
    f.write("## Configuration\n\n")
    f.write(f"- CSV: `{CSV_PATH}`\n")
    f.write(f"- TP multiplier: {V05_PARAMS['tp_atr_mult']}xATR\n")
    f.write(f"- Risk/reward: {V05_PARAMS['risk_reward']}R on win\n")
    f.write(f"- CV folds: {CV_PARAMS['n_splits']}\n")
    f.write(f"- Thresholds tested: {THRESHOLDS_TO_TEST}\n\n")

    f.write("## Threshold Comparison\n\n")
    f.write("| Threshold | Mean AUC | Mean Exp (R) | Positive Folds | "
            "Worst Fold Exp | Worst Fold Net R |\n")
    f.write("|---:|---:|---:|---:|---:|---:|\n")
    for thr, r in results_by_threshold.items():
        f.write(f"| {thr} | {r['mean_auc']:.4f} | {r['mean_exp']:+.3f} | "
                f"{r['positive_folds']}/{CV_PARAMS['n_splits']} | "
                f"{r['worst_exp']:+.3f} | {r['worst_net_r']:+.1f} |\n")
    f.write("\n")

    for thr, r in results_by_threshold.items():
        f.write(f"## Per-Fold Results - Threshold {thr}\n\n")
        f.write(r['df'].to_markdown(index=False))
        f.write("\n\n")

    if best_threshold is not None:
        f.write(f"## Model Output\n\n")
        f.write(f"- Saved to: `models/{MODEL_NAME}`\n")
        f.write(f"- Recommended threshold: `{best_threshold}`\n")
        f.write(f"- Trained on: {len(X_short_full):,} samples\n\n")
    else:
        f.write("## Recommendation\n\n")
        f.write("v0.4 features did not lift SHORT to Gate A on 2023 data. "
                "Defer SHORT until v0.6 retrain on 2024-2026 data, where the "
                "current bearish regime will provide more SHORT-favourable "
                "training samples.\n")

print(f"\nDetailed results saved to {RESULTS_FILE}")
