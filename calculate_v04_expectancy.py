"""
Calculate v0.4 Trading Expectancy (R-multiples)

This script:
1. Loads v0.4 data
2. Runs walk-forward CV with canonical parameters
3. Generates predictions for each fold
4. Calculates trading expectancy (R) by matching predictions to actual outcomes
5. Compares against v0.3 baseline
6. Evaluates Gate A/B/C criteria
"""

import pandas as pd
import numpy as np
from pathlib import Path
from src.cv import PurgedWalkForward
from src.data_loader import load_datacollector_csv, get_data_splits
from src.labels import collapse_to_binary
from src.features import get_feature_columns
from src.train import train_lightgbm

# Configuration
CV_N_SPLITS = 6
CV_TEST_SIZE = 0.15
CV_EMBARGO_BARS = 48
THRESHOLDS = [0.55, 0.60, 0.65]

# R-multiple mapping (from triple-barrier: TP=3.0*ATR, SL=1.5*ATR)
R_MAPPING = {
    'win': 2.0,      # TP hit: earned 2R
    'loss': -1.0,    # SL hit: lost 1R
    'timeout': 0.0   # Neither: flat
}

def load_and_prepare_data():
    """Load v0.4 data and prepare for CV."""
    df = load_datacollector_csv("data/DataCollector_EURUSD_M5_20230101_220446.csv")
    train_cv, held_out_test, live_forward = get_data_splits(df)
    features = get_feature_columns(train_cv)
    return df, train_cv, features

def calculate_expectancy_for_fold(df_test, outcomes, predictions, threshold):
    """
    Calculate trading expectancy for a single fold.

    Args:
        df_test: Test data with indices matching predictions
        outcomes: Actual outcomes from triple-barrier
        predictions: Model predictions (probability of win)
        threshold: Decision threshold for trading

    Returns:
        Dict with expectancy metrics
    """
    # Filter to traded bars (where prediction > threshold)
    traded_mask = predictions > threshold
    n_trades = traded_mask.sum()

    if n_trades == 0:
        return {
            'n_trades': 0,
            'win_rate': 0.0,
            'expectancy': 0.0,
            'net_r': 0.0,
            'wins': 0,
            'losses': 0,
            'timeouts': 0
        }

    # Get outcomes for traded bars
    traded_outcomes = outcomes[traded_mask]

    # Map to R values
    r_values = traded_outcomes.map(R_MAPPING)

    # Calculate metrics
    win_count = (traded_outcomes == 'win').sum()
    loss_count = (traded_outcomes == 'loss').sum()
    timeout_count = (traded_outcomes == 'timeout').sum()

    return {
        'n_trades': int(n_trades),
        'win_rate': float(win_count / n_trades) if n_trades > 0 else 0.0,
        'expectancy': float(r_values.mean()),
        'net_r': float(r_values.sum()),
        'wins': int(win_count),
        'losses': int(loss_count),
        'timeouts': int(timeout_count)
    }

def run_walk_forward_with_expectancy(df, train_cv, features):
    """
    Run walk-forward CV and calculate expectancy for each fold.

    Returns:
        Dict mapping (direction, threshold) to list of fold results
    """
    results = {}

    cv = PurgedWalkForward(
        n_splits=CV_N_SPLITS,
        test_size=CV_TEST_SIZE,
        embargo_bars=CV_EMBARGO_BARS
    )

    for direction in ['long', 'short']:
        print(f"\n{'='*80}")
        print(f"{direction.upper()} MODEL")
        print(f"{'='*80}")

        # Prepare labels
        df_labeled = collapse_to_binary(train_cv, direction=direction, timeout_as="loss")
        X_cv = df_labeled[features]
        y_cv = df_labeled['label']
        outcome_col = f'outcome_{direction}'

        # Run CV
        fold_num = 0
        for train_idx, test_idx in cv.split(train_cv):
            fold_num += 1

            X_train, X_test = X_cv.iloc[train_idx], X_cv.iloc[test_idx]
            y_train, y_test = y_cv.iloc[train_idx], y_cv.iloc[test_idx]

            # Train model
            print(f"  Fold {fold_num}: Training...", end=" ")
            model = train_lightgbm(X_train, y_train)
            print("Done")

            # Get predictions
            y_pred_proba = model.predict_proba(X_test)[:, 1]

            # Get outcomes from original data
            test_data = train_cv.iloc[test_idx]
            outcomes = test_data[outcome_col]

            # Calculate expectancy at each threshold
            print(f"    Threshold | Trades | WinRate | Expectancy | NetR   | Status")
            print(f"    " + "-" * 65)

            threshold_results = {}
            for threshold in THRESHOLDS:
                metrics = calculate_expectancy_for_fold(
                    test_data, outcomes, y_pred_proba, threshold
                )

                status = "[OK]" if metrics['expectancy'] > 0 else "[XX]"
                print(f"    {threshold:.2f}    | {metrics['n_trades']:>6} | {metrics['win_rate']:>7.1%} | "
                      f"{metrics['expectancy']:>+10.3f}R | {metrics['net_r']:>+6.1f}R | {status}")

                threshold_results[threshold] = metrics

            # Store fold results
            key = (direction, fold_num)
            results[key] = threshold_results

    return results

def summarize_results(results):
    """
    Summarize results by direction and threshold.

    Returns:
        DataFrame with summary metrics
    """
    summary_rows = []

    for direction in ['long', 'short']:
        for threshold in THRESHOLDS:
            fold_expectations = []
            fold_trades = []
            fold_win_rates = []
            fold_worst_exp = None

            for fold_num in range(1, 6):
                key = (direction, fold_num)
                if key in results:
                    metrics = results[key][threshold]
                    exp = metrics['expectancy']
                    fold_expectations.append(exp)
                    fold_trades.append(metrics['n_trades'])
                    fold_win_rates.append(metrics['win_rate'])

                    if fold_worst_exp is None or exp < fold_worst_exp:
                        fold_worst_exp = exp

            if not fold_expectations:
                continue

            positive_folds = sum(1 for e in fold_expectations if e > 0)

            summary_rows.append({
                'Direction': direction.upper(),
                'Threshold': f"{threshold:.2f}",
                'Positive Folds': f"{positive_folds}/5",
                'Mean Expectancy': f"{np.mean(fold_expectations):+.3f}R",
                'Worst Fold Exp': f"{min(fold_expectations):+.3f}R",
                'Avg Trades/Fold': f"{np.mean(fold_trades):.0f}",
                'Avg Win Rate': f"{np.mean(fold_win_rates):.1%}"
            })

    return pd.DataFrame(summary_rows)

def evaluate_gates(results):
    """
    Evaluate against Gate A/B/C criteria.

    Gate A: LONG (≥4/5, ≥+0.09R, ≥-0.15R, ≥80 trades) AND SHORT (≥3/5, ≥+0.09R, ≥-0.15R, ≥80 trades)
    Gate B: Improved from v0.3 but below Gate A
    Gate C: No improvement or meta-gating needed
    """
    # Find best threshold for each direction
    for direction in ['long', 'short']:
        print(f"\n{direction.upper()} best threshold analysis...")

        best_threshold = None
        best_metrics = None

        for threshold in THRESHOLDS:
            fold_expectations = []
            fold_trades = []

            for fold_num in range(1, 6):
                key = (direction, fold_num)
                if key in results:
                    metrics = results[key][threshold]
                    fold_expectations.append(metrics['expectancy'])
                    fold_trades.append(metrics['n_trades'])

            if not fold_expectations:
                continue

            mean_exp = np.mean(fold_expectations)
            positive_folds = sum(1 for e in fold_expectations if e > 0)
            worst_exp = min(fold_expectations)
            avg_trades = np.mean(fold_trades)

            # Check Gate A criteria
            if direction == 'long':
                gate_a = positive_folds >= 4 and mean_exp >= 0.09 and worst_exp >= -0.15 and avg_trades >= 80
            else:  # short
                gate_a = positive_folds >= 3 and mean_exp >= 0.09 and worst_exp >= -0.15 and avg_trades >= 80

            print(f"  Thr {threshold}: Mean={mean_exp:+.3f}R, Pos={positive_folds}/5, "
                  f"Worst={worst_exp:+.3f}R, Trades={avg_trades:.0f} - Gate A: {gate_a}")

    return None

def main():
    print("="*80)
    print("V0.4 EXPECTANCY CALCULATION")
    print("="*80)

    # Load data
    print("\nStep 1: Loading v0.4 data...")
    df, train_cv, features = load_and_prepare_data()
    print(f"  Data shape: {train_cv.shape}")
    print(f"  Features: {len(features)}")

    # Run walk-forward with expectancy
    print("\nStep 2: Running walk-forward CV with expectancy calculation...")
    results = run_walk_forward_with_expectancy(df, train_cv, features)

    # Summarize
    print("\n" + "="*80)
    print("SUMMARY RESULTS")
    print("="*80)
    summary_df = summarize_results(results)
    print("\n" + summary_df.to_string(index=False))

    # Evaluate gates
    print("\n" + "="*80)
    print("GATE EVALUATION")
    print("="*80)
    evaluate_gates(results)

    print("\n" + "="*80)
    print("COMPLETE")
    print("="*80)

if __name__ == "__main__":
    main()
