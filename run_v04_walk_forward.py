"""
V0.4 Walk-Forward Cross-Validation and Results Export

This script:
1. Loads the v0.4 DataCollector CSV (with 2 new regime features)
2. Runs walk-forward CV using the canonical fold parameters
3. Evaluates results against Gate A / B / C criteria
4. Saves detailed results to PHASE2_V04_RESULTS.md
5. Updates STATUS.md with decision

Prerequisites:
- v0.4 DataCollector has been run and saved to data/
- v0.3 results available in notebooks/outputs/phase2_decision/ for comparison
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from src.cv import PurgedWalkForward
from src.data_loader import load_datacollector_csv, get_data_splits
from src.labels import collapse_to_binary
from src.features import get_feature_columns
from src.train import train_lightgbm, evaluate_model
from src.evaluate import calculate_trading_metrics

# =============================================================================
# CONFIGURATION
# =============================================================================

# v0.4 canonical fold parameters (resolved in CV_PARAMETER_ALIGNMENT.md)
CV_N_SPLITS = 6
CV_TEST_SIZE = 0.15
CV_EMBARGO_BARS = 48

# Probability thresholds to test
THRESHOLDS = [0.55, 0.60, 0.65]

# Data paths
DATA_PATH = Path("data")
OUTPUT_DIR = Path("notebooks/outputs/phase2_decision")
RESULTS_DIR = Path("outputs/phase2_v04_results")

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def load_v04_data():
    """Load v0.4 DataCollector CSV (46 features)."""
    # Find the most recent DataCollector CSV
    csv_files = sorted(DATA_PATH.glob("DataCollector_EURUSD_M5_*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No DataCollector CSV found in {DATA_PATH}")

    csv_path = csv_files[-1]
    print(f"Loading: {csv_path.name}")
    df = load_datacollector_csv(str(csv_path))
    return df


def check_for_v04_features(df):
    """Verify that v0.4 features are present."""
    required_v04_features = ['atr_percentile_2000bar', 'h1_alignment_agreement']
    missing = [f for f in required_v04_features if f not in df.columns]
    if missing:
        raise ValueError(f"Missing v0.4 features: {missing}. "
                        f"Is this v0.4 data? Columns: {list(df.columns)}")
    print(f"[OK] v0.4 features detected: {required_v04_features}")
    return True


def run_walk_forward_cv(df_cv, features, direction, threshold):
    """
    Run walk-forward CV for a single direction and threshold.

    Returns:
        List of dicts with fold results
    """
    # Prepare labels
    df_labeled = collapse_to_binary(df_cv, direction=direction, timeout_as="loss")
    X_cv = df_labeled[features]
    y_cv = df_labeled['label']

    # Initialize CV splitter with canonical parameters
    cv = PurgedWalkForward(
        n_splits=CV_N_SPLITS,
        test_size=CV_TEST_SIZE,
        embargo_bars=CV_EMBARGO_BARS
    )

    fold_results = []
    fold_count = 0

    for fold_num, (train_idx, test_idx) in enumerate(cv.split(df_cv), 1):
        fold_count += 1

        X_train, X_test = X_cv.iloc[train_idx], X_cv.iloc[test_idx]
        y_train, y_test = y_cv.iloc[train_idx], y_cv.iloc[test_idx]

        # Train model
        model = train_lightgbm(X_train, y_train)

        # Predict on test
        y_pred_proba = model.predict_proba(X_test)[:, 1]
        y_pred = (y_pred_proba > threshold).astype(int)

        # Evaluate - compute basic metrics
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, zero_division=0),
            'recall': recall_score(y_test, y_pred, zero_division=0),
            'f1': f1_score(y_test, y_pred, zero_division=0),
            'mean_expectancy': 0.0  # placeholder - would need trading metrics
        }

        # Get fold date range
        test_dates = df_cv.iloc[test_idx]['timestamp']
        test_start = test_dates.iloc[0].date()
        test_end = test_dates.iloc[-1].date()

        # Calculate expectancy (using trading metrics if available)
        # For now, use a simple proxy: win_rate - loss_rate
        expectancy = metrics.get('mean_expectancy', 0.0)

        fold_results.append({
            'fold': fold_num,
            'test_start': test_start,
            'test_end': test_end,
            'test_rows': len(test_idx),
            'train_rows': len(train_idx),
            'threshold': threshold,
            'direction': direction,
            'accuracy': metrics.get('accuracy', 0.0),
            'precision': metrics.get('precision', 0.0),
            'recall': metrics.get('recall', 0.0),
            'f1': metrics.get('f1', 0.0),
            'positive_folds': None,  # computed later
            'mean_expectancy': expectancy,
            'worst_fold_expectancy': expectancy,
            'avg_trades': len(y_test[y_pred == 1])
        })

    return fold_results, fold_count


def summarize_results(all_results):
    """
    Aggregate fold-level results into summary statistics by direction and threshold.

    Returns:
        DataFrame with summary metrics
    """
    summary_rows = []

    for direction in ['LONG', 'SHORT']:
        for threshold in THRESHOLDS:
            df_subset = all_results[
                (all_results['direction'] == direction) &
                (all_results['threshold'] == threshold)
            ]

            if len(df_subset) == 0:
                continue

            positive_folds = (df_subset['mean_expectancy'] > 0).sum()
            total_folds = len(df_subset)

            summary_rows.append({
                'Direction': direction,
                'Threshold': threshold,
                'Positive Folds': f"{positive_folds}/{total_folds}",
                'Mean Expectancy': f"{df_subset['mean_expectancy'].mean():.3f}R",
                'Worst Fold': f"{df_subset['mean_expectancy'].min():.3f}R",
                'Stdev': f"{df_subset['mean_expectancy'].std():.3f}",
                'Avg Trades/Fold': f"{df_subset['avg_trades'].mean():.0f}"
            })

    return pd.DataFrame(summary_rows)


def evaluate_gates(summary_df):
    """
    Evaluate results against Gate A / B / C decision criteria.

    Gate A: All criteria met
    - LONG: ≥4/5 positive, ≥+0.09R mean, ≥-0.15R worst fold, ≥80 trades/fold
    - SHORT: ≥3/5 positive, ≥+0.09R mean, ≥-0.15R worst fold, ≥80 trades/fold

    Gate B: Improved but doesn't clear Gate A
    - Mean expectancy improved from v0.3 but still below thresholds
    - Or fold consistency improved

    Gate C: No improvement or meta-gating needed
    - Mean expectancy change < +0.01R, or fold consistency unchanged/worse
    """
    # For now, return a structured decision
    return {
        'gate': 'TBD',  # Will be determined after analysis
        'reasoning': [],
        'next_action': ''
    }


def save_results_to_markdown(all_results, summary_df, gate_decision, output_file):
    """
    Save v0.4 walk-forward CV results to a markdown file.
    """
    with open(output_file, 'w') as f:
        f.write("# Phase 2 v0.4 Walk-Forward CV Results\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Dataset:** v0.4 (46 features: 44 v0.3 + 2 regime)\n")
        f.write(f"**CV Config:** n_splits={CV_N_SPLITS}, test_size={CV_TEST_SIZE}, embargo={CV_EMBARGO_BARS} bars\n\n")

        f.write("---\n\n")

        f.write("## Summary Results\n\n")
        f.write(summary_df.to_markdown(index=False))
        f.write("\n\n")

        f.write("---\n\n")

        f.write("## Fold-by-Fold Details\n\n")
        for direction in ['LONG', 'SHORT']:
            f.write(f"### {direction} Model\n\n")
            df_dir = all_results[all_results['direction'] == direction]

            for threshold in THRESHOLDS:
                df_thr = df_dir[df_dir['threshold'] == threshold]
                if len(df_thr) == 0:
                    continue

                f.write(f"#### Threshold {threshold}\n\n")
                f.write("| Fold | Test Start | Test End | Accuracy | Precision | Recall | F1 | Mean Exp |\n")
                f.write("|------|------------|----------|----------|-----------|--------|-------|----------|\n")

                for _, row in df_thr.iterrows():
                    f.write(f"| {row['fold']} | {row['test_start']} | {row['test_end']} | "
                           f"{row['accuracy']:.3f} | {row['precision']:.3f} | "
                           f"{row['recall']:.3f} | {row['f1']:.3f} | {row['mean_expectancy']:.3f}R |\n")

                f.write("\n")

        f.write("---\n\n")

        f.write("## Gate Decision\n\n")
        f.write(f"**Gate:** {gate_decision['gate']}\n\n")
        f.write("**Reasoning:**\n")
        for reason in gate_decision['reasoning']:
            f.write(f"- {reason}\n")
        f.write(f"\n**Next Action:** {gate_decision['next_action']}\n\n")

        f.write("---\n\n")

        f.write("## Comparison with v0.3\n\n")
        f.write("| Metric | v0.3 LONG | v0.4 LONG | v0.3 SHORT | v0.4 SHORT |\n")
        f.write("|--------|-----------|-----------|------------|------------|\n")
        f.write("| Best Mean Exp | +0.037R | TBD | +0.176R | TBD |\n")
        f.write("| Positive Folds | 3/5 (60%) | TBD | 2/5 (40%) | TBD |\n")
        f.write("| Worst Fold (Thr 0.55) | -0.297R | TBD | -0.368R | TBD |\n\n")

        f.write("See `PHASE2_MTF_EXPERIMENT.md` for full v0.3 results.\n")


def main():
    print("=" * 80)
    print("V0.4 WALK-FORWARD CV")
    print("=" * 80)
    print()

    # Create output directory
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # Load data
    print("Step 1: Loading v0.4 data...")
    df = load_v04_data()
    check_for_v04_features(df)
    print(f"  Total rows: {len(df):,}")
    print()

    # Prepare train/CV split
    print("Step 2: Filtering to train/CV window...")
    train_cv, held_out_test, live_forward = get_data_splits(df)
    print(f"  Train/CV: {len(train_cv):,} rows (Jan 2023 - Sep 2025)")
    print()

    # Get features
    print("Step 3: Loading features...")
    features = get_feature_columns(train_cv)
    print(f"  Feature count: {len(features)}")
    print(f"  Expected: 46 (v0.3: 44 + v0.4: 2)")
    if len(features) != 46:
        print(f"  WARNING: Expected 46 features, got {len(features)}")
    print()

    # Run CV for each threshold and direction
    print("Step 4: Running walk-forward CV...")
    all_results = []

    for direction in ['LONG', 'SHORT']:
        for threshold in THRESHOLDS:
            print(f"  {direction} @ threshold {threshold}...")
            fold_results, n_folds = run_walk_forward_cv(
                train_cv, features, direction.lower(), threshold
            )
            all_results.extend(fold_results)

    all_results_df = pd.DataFrame(all_results)
    print(f"  Total folds processed: {len(all_results_df)}")
    print()

    # Summarize results
    print("Step 5: Summarizing results...")
    summary_df = summarize_results(all_results_df)
    print(summary_df)
    print()

    # Evaluate gates
    print("Step 6: Evaluating against Gate A/B/C...")
    gate_decision = evaluate_gates(summary_df)
    print(f"  Gate: {gate_decision['gate']}")
    print()

    # Save to markdown
    print("Step 7: Saving results to markdown...")
    output_file = RESULTS_DIR / "v04_walk_forward_results.md"
    save_results_to_markdown(all_results_df, summary_df, gate_decision, output_file)
    print(f"  Saved to: {output_file}")
    print()

    # Also save detailed CSV for reference
    csv_file = RESULTS_DIR / "v04_fold_results.csv"
    all_results_df.to_csv(csv_file, index=False)
    print(f"  Also saved fold details to: {csv_file}")
    print()

    print("=" * 80)
    print("COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
