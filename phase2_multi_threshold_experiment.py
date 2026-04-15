"""
Phase 2 Decision - Multi-Threshold Walk-Forward Experiment
Executes the complete experiment from PHASE2_DECISION.md
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

from src.data_loader import load_datacollector_csv, get_data_splits
from src.labels import collapse_to_binary
from src.features import get_feature_columns
from src.cv import PurgedWalkForward
from src.train import train_lightgbm, evaluate_model
from src.evaluate import calculate_trading_metrics

# Create output directory
output_dir = Path("notebooks/outputs/phase2_decision")
output_dir.mkdir(parents=True, exist_ok=True)

print("="*70)
print("Phase 2 Decision - Multi-Threshold Walk-Forward Experiment")
print("="*70)

# Load data
print("\nLoading data...")
csv_path = 'data/DataCollector_EURUSD_M5_20230101_220400.csv'
df = load_datacollector_csv(csv_path)
train_cv, held_out_test, live_forward = get_data_splits(df)
print(f"Train/CV: {len(train_cv):,} rows (Jan 2023 - Sep 2025)")

# Get features
features = get_feature_columns(train_cv)
print(f"Features: {len(features)}")

# Initialize CV
cv = PurgedWalkForward(n_splits=6, embargo_bars=48, test_size=0.15)
print(f"CV: {cv.n_splits} folds, embargo={cv.embargo_bars} bars")

# Thresholds to test
thresholds = [0.55, 0.60, 0.65, 0.70]

print("\n" + "="*70)
print("STEP 2: Fix Fold 6 - Test with single threshold first")
print("="*70)

# Test LONG at 0.55 to verify all 6 folds run
df_long_full = collapse_to_binary(train_cv, direction="long", timeout_as="loss")
X_cv = df_long_full[features]
y_cv = df_long_full['label']
bars_cv = df_long_full['bars_to_outcome_long']

print(f"\nTesting LONG at threshold=0.55 to verify 6 folds...")
test_results = []

for fold_idx, (train_idx, test_idx) in enumerate(cv.split(X_cv, y_cv, bars_cv), 1):
    print(f"  Fold {fold_idx}: {len(train_idx):,} train, {len(test_idx):,} test samples")
    test_results.append({
        'fold': fold_idx,
        'train_size': len(train_idx),
        'test_size': len(test_idx)
    })

if len(test_results) == 6:
    print(f"\n[OK] All 6 folds generated successfully")
else:
    print(f"\n[WARN] Only {len(test_results)} folds generated (expected 6)")

print("\n" + "="*70)
print("STEP 3-4: Multi-Threshold Experiment")
print("="*70)

def run_walk_forward_multi_threshold(direction: str):
    """
    Run 6-fold walk-forward CV at multiple thresholds for one direction.
    """
    print(f"\n{'='*70}")
    print(f"{direction.upper()} - Multi-Threshold Walk-Forward")
    print(f"{'='*70}")

    # Prepare data
    df_dir = collapse_to_binary(train_cv, direction=direction, timeout_as="loss")
    X_cv = df_dir[features]
    y_cv = df_dir['label']
    bars_cv = df_dir[f'bars_to_outcome_{direction}']

    all_results = []
    fold_equity_curves = {thr: {} for thr in thresholds}

    for threshold in thresholds:
        print(f"\n--- Threshold = {threshold} ---")

        for fold_idx, (train_idx, test_idx) in enumerate(cv.split(X_cv, y_cv, bars_cv), 1):
            X_train_fold = X_cv.iloc[train_idx]
            y_train_fold = y_cv.iloc[train_idx]
            X_test_fold = X_cv.iloc[test_idx]
            y_test_fold = y_cv.iloc[test_idx]

            # Train
            model = train_lightgbm(X_train_fold, y_train_fold)

            # Evaluate
            metrics = evaluate_model(model, X_test_fold, y_test_fold, verbose=False)

            # Trading metrics
            y_pred_proba = model.predict_proba(X_test_fold)[:, 1]
            trading_metrics = calculate_trading_metrics(
                y_test_fold.values,
                y_pred_proba,
                threshold=threshold,
                risk_reward=2.0,
                commission_r=0.04
            )

            # Calculate equity curve for this fold
            selected = y_pred_proba >= threshold
            if selected.sum() > 0:
                y_selected = y_test_fold.values[selected]
                pnl_per_trade = np.where(y_selected == 1, 2.0, -1.0) - 0.04  # R:R=2, commission=0.04R
                equity = np.concatenate([[0], np.cumsum(pnl_per_trade)])

                # Calculate max drawdown
                running_max = np.maximum.accumulate(equity)
                drawdowns = running_max - equity
                max_dd_r = drawdowns.max()
            else:
                equity = np.array([0])
                max_dd_r = 0.0

            # Store equity curve
            fold_equity_curves[threshold][fold_idx] = equity

            result = {
                'direction': direction.upper(),
                'threshold': threshold,
                'fold': fold_idx,
                'n_trades': trading_metrics['total_trades'],
                'win_rate': trading_metrics['win_rate'],
                'pf': trading_metrics['profit_factor'],
                'expectancy_r': trading_metrics['expectancy_r'],
                'net_r': trading_metrics['net_profit_r'],
                'max_dd_r': max_dd_r,
                'roc_auc': metrics['roc_auc']
            }
            all_results.append(result)

            print(f"  Fold {fold_idx}: {trading_metrics['total_trades']:4} trades, "
                  f"{trading_metrics['win_rate']*100:5.1f}% WR, "
                  f"PF={trading_metrics['profit_factor']:5.2f}, "
                  f"Exp={trading_metrics['expectancy_r']:+7.3f}R, "
                  f"NetR={trading_metrics['net_profit_r']:+8.1f}")

    # Save results
    results_df = pd.DataFrame(all_results)
    csv_filename = output_dir / f"walk_forward_multi_threshold_{direction}.csv"
    results_df.to_csv(csv_filename, index=False)
    print(f"\n[OK] Saved: {csv_filename}")

    # Plot equity curves for each threshold
    for threshold in thresholds:
        fig, ax = plt.subplots(figsize=(12, 6))

        for fold_idx in range(1, 7):
            if fold_idx in fold_equity_curves[threshold]:
                equity = fold_equity_curves[threshold][fold_idx]
                ax.plot(range(len(equity)), equity, label=f"Fold {fold_idx}", alpha=0.7)

        ax.axhline(0, color='red', linestyle='--', alpha=0.5)
        ax.set_xlabel('Trade Number')
        ax.set_ylabel('Cumulative R')
        ax.set_title(f"{direction.upper()} - Fold Equity Curves (Threshold={threshold})")
        ax.legend()
        ax.grid(True, alpha=0.3)

        png_filename = output_dir / f"fold_equity_curves_{direction}_thr{threshold}.png"
        plt.savefig(png_filename, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"[OK] Saved: {png_filename}")

    return results_df

# Run for both directions
print("\nRunning LONG...")
results_long = run_walk_forward_multi_threshold("long")

print("\nRunning SHORT...")
results_short = run_walk_forward_multi_threshold("short")

# Generate summary table
print("\n" + "="*70)
print("STEP 6: Summary Tables")
print("="*70)

def generate_summary_table(results_df, direction):
    """Generate summary statistics per threshold."""
    summary_rows = []

    for threshold in thresholds:
        thr_data = results_df[results_df['threshold'] == threshold]

        positive_folds = (thr_data['net_r'] > 0).sum()
        mean_exp = thr_data['expectancy_r'].mean()
        worst_exp = thr_data['expectancy_r'].min()
        worst_net_r = thr_data['net_r'].min()
        std_exp = thr_data['expectancy_r'].std()
        avg_trades = thr_data['n_trades'].mean()

        summary_rows.append({
            'Threshold': threshold,
            'Positive folds': f"{positive_folds}/6",
            'Mean exp': f"{mean_exp:+.3f}",
            'Worst fold exp': f"{worst_exp:+.3f}",
            'Worst fold net R': f"{worst_net_r:+.1f}",
            'Stdev exp': f"{std_exp:.3f}",
            'Avg trades/fold': f"{avg_trades:.0f}"
        })

    summary_df = pd.DataFrame(summary_rows)

    print(f"\n### {direction.upper()} — Walk-forward across thresholds\n")
    print(summary_df.to_markdown(index=False))

    return summary_df

summary_long = generate_summary_table(results_long, "LONG")
summary_short = generate_summary_table(results_short, "SHORT")

# Save summary markdown
summary_md = output_dir / "threshold_consistency_summary.md"
with open(summary_md, 'w') as f:
    f.write("# Threshold Consistency Summary\n\n")
    f.write("## LONG — Walk-forward across thresholds\n\n")
    f.write(summary_long.to_markdown(index=False))
    f.write("\n\n## SHORT — Walk-forward across thresholds\n\n")
    f.write(summary_short.to_markdown(index=False))
    f.write("\n")

print(f"\n[OK] Saved: {summary_md}")

print("\n" + "="*70)
print("Experiment Complete")
print("="*70)
print("\nGenerated files:")
print(f"  - {output_dir}/walk_forward_multi_threshold_long.csv")
print(f"  - {output_dir}/walk_forward_multi_threshold_short.csv")
print(f"  - {output_dir}/fold_equity_curves_long_thr*.png (4 files)")
print(f"  - {output_dir}/fold_equity_curves_short_thr*.png (4 files)")
print(f"  - {output_dir}/threshold_consistency_summary.md")
print("\nNext: Review equity curves (Step 5) and apply decision tree (Step 7-8)")
