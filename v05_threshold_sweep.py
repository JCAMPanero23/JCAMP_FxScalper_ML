"""
v05 LONG Multi-Threshold Sweep

Question: Was Gate A failure at threshold=0.65 a calibration issue?
Approach: Run walk-forward CV once, cache per-fold (y_true, y_pred_proba),
then evaluate calculate_trading_metrics at multiple thresholds.

Pass criteria per threshold: >=4/5 folds with positive expectancy.
"""

import sys
sys.path.append('.')

import pandas as pd
import numpy as np
from datetime import datetime

from src.data_loader import load_datacollector_csv, get_data_splits
from src.labels import collapse_to_binary
from src.features import get_feature_columns
from src.cv import PurgedWalkForward
from src.train import train_lightgbm, evaluate_model
from src.evaluate import calculate_trading_metrics

CSV_PATH = 'data/DataCollector_EURUSD_M5_20230101_220446.csv'
RESULTS_FILE = 'v05_threshold_sweep_results.md'

V05_PARAMS = {'risk_reward': 3.0}
CV_PARAMS = {'n_splits': 6, 'embargo_bars': 72, 'test_size': 0.15}
THRESHOLDS = [0.55, 0.60, 0.65, 0.70, 0.75]

print("=" * 70)
print("v05 LONG Multi-Threshold Sweep")
print("=" * 70)

# Load
print("\n[1/3] Loading data...")
df = load_datacollector_csv(CSV_PATH)
train_cv, _, _ = get_data_splits(df)
df_long = collapse_to_binary(train_cv, direction="long", timeout_as="loss")
features = get_feature_columns(df_long)
X = df_long[features]
y = df_long['label']
bars_to_outcome = df_long['bars_to_outcome_long']
print(f"  Samples: {len(X):,}  Features: {len(features)}  Baseline win rate: {y.mean()*100:.1f}%")

# CV — train once per fold, cache predictions
print("\n[2/3] Walk-forward CV (training each fold once)...")
cv = PurgedWalkForward(**CV_PARAMS)
fold_preds = []  # list of (y_true, y_pred_proba, roc_auc) per fold

for fold_idx, (train_idx, test_idx) in enumerate(cv.split(X, y, bars_to_outcome), 1):
    print(f"  Fold {fold_idx}/{CV_PARAMS['n_splits']}:", end=" ")
    X_tr, y_tr = X.iloc[train_idx], y.iloc[train_idx]
    X_te, y_te = X.iloc[test_idx], y.iloc[test_idx]
    model = train_lightgbm(X_tr, y_tr)
    metrics = evaluate_model(model, X_te, y_te, verbose=False)
    y_proba = model.predict_proba(X_te)[:, 1]
    fold_preds.append((y_te.values, y_proba, metrics['roc_auc']))
    print(f"AUC={metrics['roc_auc']:.4f}  proba_range=[{y_proba.min():.3f}, {y_proba.max():.3f}]  >=0.65: {(y_proba >= 0.65).sum()}")

# Sweep thresholds
print("\n[3/3] Evaluating thresholds...")
sweep_rows = []
for thr in THRESHOLDS:
    fold_metrics = []
    for fold_idx, (y_te, y_proba, roc_auc) in enumerate(fold_preds, 1):
        tm = calculate_trading_metrics(y_te, y_proba, threshold=thr, risk_reward=V05_PARAMS['risk_reward'])
        fold_metrics.append(tm)
    n_trades = sum(m['total_trades'] for m in fold_metrics)
    pos_folds = sum(1 for m in fold_metrics if m['expectancy_r'] > 0)
    # Mean only over folds that had trades; folds with 0 trades contribute 0R expectancy by default
    mean_exp = np.mean([m['expectancy_r'] for m in fold_metrics])
    mean_pf = np.mean([m['profit_factor'] for m in fold_metrics if m['total_trades'] > 0]) if n_trades > 0 else 0.0
    mean_wr = np.mean([m['win_rate'] for m in fold_metrics if m['total_trades'] > 0]) if n_trades > 0 else 0.0
    sweep_rows.append({
        'threshold': thr,
        'pos_folds': f"{pos_folds}/5",
        'mean_exp_r': round(mean_exp, 3),
        'mean_pf': round(mean_pf, 2),
        'mean_wr': round(mean_wr, 3),
        'total_trades': n_trades,
        'gate_a': 'PASS' if pos_folds >= 4 else 'FAIL'
    })
    print(f"  thr={thr}: {pos_folds}/5 positive, mean_exp={mean_exp:+.3f}R, total_trades={n_trades}, {sweep_rows[-1]['gate_a']}")

sweep_df = pd.DataFrame(sweep_rows)

# Per-fold detail at each threshold
detail_rows = []
for thr in THRESHOLDS:
    for fold_idx, (y_te, y_proba, roc_auc) in enumerate(fold_preds, 1):
        tm = calculate_trading_metrics(y_te, y_proba, threshold=thr, risk_reward=V05_PARAMS['risk_reward'])
        detail_rows.append({
            'threshold': thr,
            'fold': fold_idx,
            'roc_auc': round(roc_auc, 4),
            'n_trades': tm['total_trades'],
            'win_rate': tm['win_rate'],
            'expectancy_r': tm['expectancy_r'],
            'profit_factor': tm['profit_factor'],
        })
detail_df = pd.DataFrame(detail_rows)

# Write report
print(f"\nWriting {RESULTS_FILE}...")
with open(RESULTS_FILE, 'w') as f:
    f.write("# v05 LONG Multi-Threshold Sweep Results\n\n")
    f.write(f"**Date:** {datetime.now().isoformat()}\n\n")
    f.write("**Question:** Was Gate A failure at thr=0.65 a calibration issue?\n\n")
    f.write("## Summary by Threshold\n\n")
    f.write(sweep_df.to_markdown(index=False))
    f.write("\n\n## Per-Fold Detail\n\n")
    for thr in THRESHOLDS:
        f.write(f"\n### threshold = {thr}\n\n")
        f.write(detail_df[detail_df['threshold'] == thr].drop(columns=['threshold']).to_markdown(index=False))
        f.write("\n")
    f.write("\n## Verdict\n\n")
    passing = sweep_df[sweep_df['gate_a'] == 'PASS']
    if len(passing) == 0:
        f.write("All thresholds FAIL Gate A. Calibration alone does not fix the LONG model — proceed to v0.6 retrain.\n")
    else:
        best = passing.sort_values('mean_exp_r', ascending=False).iloc[0]
        f.write(f"Best threshold: **{best['threshold']}** ({best['pos_folds']} folds, mean_exp={best['mean_exp_r']:+}R, total_trades={best['total_trades']}).\n")

print(f"Done. {RESULTS_FILE}")
