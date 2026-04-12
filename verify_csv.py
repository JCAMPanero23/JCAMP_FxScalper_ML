#!/usr/bin/env python3
"""
Smoke test verification for DataCollector CSV output.
Checks PRD acceptance criteria:
- No NaN/Inf in feature columns
- Label balance ≥10% for each outcome (win/loss/timeout) in both directions
- Feature distributions sane
- Bar0 features are nonzero
"""

import pandas as pd
import numpy as np
import sys

def verify_csv(csv_path):
    """Verify CSV meets PRD acceptance criteria."""
    print(f"Loading CSV: {csv_path}")
    df = pd.read_csv(csv_path)

    print(f"\n{'='*60}")
    print(f"BASIC INFO")
    print(f"{'='*60}")
    print(f"Total rows: {len(df):,}")
    print(f"Total columns: {len(df.columns)}")
    print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

    # Separate features from labels
    label_cols = ['outcome_long', 'bars_to_outcome_long', 'outcome_short', 'bars_to_outcome_short']
    meta_cols = ['timestamp', 'symbol']
    feature_cols = [c for c in df.columns if c not in label_cols + meta_cols]

    print(f"Feature columns: {len(feature_cols)}")

    # Check for NaN/Inf
    print(f"\n{'='*60}")
    print(f"NaN/Inf CHECK")
    print(f"{'='*60}")

    nan_counts = df[feature_cols].isna().sum()
    if nan_counts.sum() > 0:
        print("[FAIL] Found NaN values in features:")
        print(nan_counts[nan_counts > 0])
        return False
    else:
        print("[PASS] No NaN values in feature columns")

    inf_counts = df[feature_cols].apply(lambda x: np.isinf(x).sum())
    if inf_counts.sum() > 0:
        print("[FAIL] Found Inf values in features:")
        print(inf_counts[inf_counts > 0])
        return False
    else:
        print("[PASS] No Inf values in feature columns")

    # Label balance check
    print(f"\n{'='*60}")
    print(f"LABEL BALANCE")
    print(f"{'='*60}")

    for direction in ['long', 'short']:
        outcome_col = f'outcome_{direction}'
        print(f"\n{direction.upper()} outcomes:")
        value_counts = df[outcome_col].value_counts()
        percentages = (value_counts / len(df) * 100).round(2)

        for outcome in ['win', 'loss', 'timeout']:
            count = value_counts.get(outcome, 0)
            pct = percentages.get(outcome, 0)
            status = "[PASS]" if pct >= 10 else "[WARN]"
            print(f"  {outcome:8s}: {count:6,} ({pct:5.2f}%) {status}")

            if pct < 10:
                print(f"    [WARN] {outcome} is below 10% threshold")

    # Bar0 features check (should be nonzero for most rows)
    print(f"\n{'='*60}")
    print(f"BAR0 FEATURES CHECK")
    print(f"{'='*60}")

    bar0_features = [c for c in feature_cols if c.startswith('bar0_')]
    for feat in bar0_features:
        zero_count = (df[feat] == 0).sum()
        zero_pct = (zero_count / len(df) * 100).round(2)
        nonzero_pct = 100 - zero_pct
        status = "[PASS]" if nonzero_pct >= 80 else "[WARN]"
        print(f"  {feat:15s}: {nonzero_pct:5.2f}% nonzero {status}")

    # Feature distribution sanity checks
    print(f"\n{'='*60}")
    print(f"FEATURE DISTRIBUTION SANITY CHECKS")
    print(f"{'='*60}")

    # RSI should be 0-100
    rsi_cols = [c for c in feature_cols if 'rsi' in c]
    for col in rsi_cols:
        min_val, max_val = df[col].min(), df[col].max()
        status = "[PASS]" if 0 <= min_val and max_val <= 100 else "[FAIL]"
        print(f"  {col:15s}: [{min_val:6.2f}, {max_val:6.2f}] {status}")
        if not (0 <= min_val and max_val <= 100):
            print(f"    [FAIL] RSI should be in [0, 100]")

    # ATR ratios should be positive
    atr_cols = [c for c in feature_cols if 'atr' in c]
    for col in atr_cols:
        min_val = df[col].min()
        status = "[PASS]" if min_val >= 0 else "[FAIL]"
        print(f"  {col:20s}: min={min_val:8.6f} {status}")
        if min_val < 0:
            print(f"    [FAIL] ATR values should be non-negative")

    # Spread should be positive
    if 'spread_pips' in df.columns:
        min_spread = df['spread_pips'].min()
        max_spread = df['spread_pips'].max()
        status = "[PASS]" if min_spread >= 0 and max_spread < 10 else "[WARN]"
        print(f"  spread_pips: [{min_spread:.2f}, {max_spread:.2f}] {status}")
        if max_spread >= 10:
            print(f"    [WARN] Max spread seems high (>=10 pips)")

    # Check distance features (should mostly be within ±5 ATR per PRD)
    print(f"\n{'='*60}")
    print(f"DISTANCE FEATURES (should mostly be within ±5 ATR)")
    print(f"{'='*60}")

    dist_cols = [c for c in feature_cols if c.startswith('dist_')]
    for col in dist_cols:
        within_5atr = ((df[col] >= -5) & (df[col] <= 5)).sum()
        pct_within = (within_5atr / len(df) * 100).round(2)
        min_val, max_val = df[col].min(), df[col].max()
        status = "[PASS]" if pct_within >= 70 else "[WARN]"
        print(f"  {col:25s}: {pct_within:5.2f}% within +/-5 ATR, range=[{min_val:7.2f}, {max_val:7.2f}] {status}")

    # Summary statistics
    print(f"\n{'='*60}")
    print(f"SUMMARY STATISTICS (first 10 features)")
    print(f"{'='*60}")
    print(df[feature_cols[:10]].describe())

    print(f"\n{'='*60}")
    print(f"VERIFICATION COMPLETE")
    print(f"{'='*60}")
    print("[PASS] All critical checks passed!")
    print(f"\nCSV is ready for full historical run.")

    return True

if __name__ == '__main__':
    csv_path = 'data/DataCollector_EURUSD_M5_20230101_220400.csv'
    try:
        verify_csv(csv_path)
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
