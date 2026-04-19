#!/usr/bin/env python3
"""
Feature Skew Test - Comparison Script
======================================

Purpose: Compare features computed by DataCollector vs FxScalper_ML.
This script validates that both implementations produce identical features,
which is critical for train/serve consistency.

Usage:
    python compare_feature_skew.py <datacollector_csv> <fxscalper_csv>

Example:
    python compare_feature_skew.py \
        "C:\Users\Jcamp_Laptop\Documents\JCAMP_Data\DataCollector_EURUSD_M5_20240101_*.csv" \
        "C:\Users\Jcamp_Laptop\Documents\JCAMP_Data\FxScalper_features_debug.csv"
"""

import pandas as pd
import numpy as np
import sys
import glob
from pathlib import Path

# Feature names (must match FeatureComputer.FEATURE_NAMES in C#)
FEATURE_NAMES = [
    "dist_sma_m5_50", "dist_sma_m5_100", "dist_sma_m5_200",
    "dist_sma_m5_275", "dist_sma_m15_200", "dist_sma_m30_200",
    "dist_sma_h1_200", "dist_sma_h4_200",
    "slope_sma_m5_200", "slope_sma_h1_200",
    "rsi_m5", "rsi_m15", "rsi_m30",
    "adx_m5", "di_plus_m5", "di_minus_m5",
    "atr_m5", "atr_m15", "atr_h1", "atr_ratio_m5_h1", "bb_width",
    "bar0_body", "bar0_range", "bar1_body", "bar1_range",
    "bar2_body", "bar2_range", "bar3_body", "bar3_range",
    "bar4_body", "bar4_range",
    "dist_swing_high", "dist_swing_low",
    "hour_utc", "dow", "sess_asia", "sess_london", "sess_ny",
    "spread_pips",
    "mtf_alignment_score", "mtf_stacking_score",
    "bars_since_tf_fast_flip", "tf_fast_flip_direction",
    "mtf_alignment_duration",
    "atr_percentile_2000bar", "h1_alignment_agreement",
]

def load_csv_with_glob(pattern: str) -> pd.DataFrame:
    """Load CSV, supporting wildcard patterns."""
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(f"No files matching pattern: {pattern}")
    if len(files) > 1:
        print(f"WARNING: Multiple files found, using first: {files[0]}")
    return pd.read_csv(files[0])

def main():
    if len(sys.argv) != 3:
        print("Usage: python compare_feature_skew.py <datacollector_csv> <fxscalper_csv>")
        sys.exit(1)

    collector_path = sys.argv[1]
    fxscalper_path = sys.argv[2]

    print("=" * 70)
    print("FEATURE SKEW TEST - COMPARISON REPORT")
    print("=" * 70)
    print()

    # Load CSVs
    print(f"Loading DataCollector CSV: {collector_path}")
    try:
        collector = load_csv_with_glob(collector_path)
    except Exception as e:
        print(f"ERROR: Failed to load DataCollector CSV: {e}")
        sys.exit(1)

    print(f"  - Rows: {len(collector)}")
    print(f"  - Columns: {len(collector.columns)}")
    print()

    print(f"Loading FxScalper_ML CSV: {fxscalper_path}")
    try:
        fxscalper = pd.read_csv(fxscalper_path)
    except Exception as e:
        print(f"ERROR: Failed to load FxScalper CSV: {e}")
        sys.exit(1)

    print(f"  - Rows: {len(fxscalper)}")
    print(f"  - Columns: {len(fxscalper.columns)}")
    print()

    # Extract feature columns
    print("Extracting feature columns...")

    # DataCollector has: timestamp, symbol, [features...], outcome_long, bars_to_outcome_long, ...
    # FxScalper_ML has: [features only]

    try:
        collector_features = collector[FEATURE_NAMES]
        print(f"  - DataCollector: {len(FEATURE_NAMES)} features extracted")
    except KeyError as e:
        print(f"ERROR: Missing column in DataCollector: {e}")
        sys.exit(1)

    try:
        fxscalper_features = fxscalper[FEATURE_NAMES]
        print(f"  - FxScalper_ML: {len(FEATURE_NAMES)} features extracted")
    except KeyError as e:
        print(f"ERROR: Missing column in FxScalper_ML: {e}")
        sys.exit(1)

    print()

    # Align by row count
    min_rows = min(len(collector_features), len(fxscalper_features))
    print(f"Aligning CSVs: comparing first {min_rows} rows")

    collector_subset = collector_features.iloc[:min_rows].values.astype(np.float64)
    fxscalper_subset = fxscalper_features.iloc[:min_rows].values.astype(np.float64)

    print()
    print("=" * 70)
    print("COMPARISON RESULTS")
    print("=" * 70)
    print()

    # Calculate differences
    diff = np.abs(collector_subset - fxscalper_subset)
    max_diff = np.max(diff)
    mean_diff = np.mean(diff)
    median_diff = np.median(diff)
    max_per_col = np.max(diff, axis=0)

    # Tolerance
    TOLERANCE = 1e-6

    # Report statistics
    print(f"Total cells compared: {min_rows} rows × {len(FEATURE_NAMES)} features = {min_rows * len(FEATURE_NAMES):,}")
    print()
    print(f"Max absolute difference:     {max_diff:.15e}")
    print(f"Mean absolute difference:    {mean_diff:.15e}")
    print(f"Median absolute difference:  {median_diff:.15e}")
    print(f"Tolerance (acceptance):      {TOLERANCE:.15e}")
    print()

    # Test result
    if max_diff <= TOLERANCE:
        print("=" * 70)
        print("STATUS: ✅ PASS - Features are identical within tolerance!")
        print("=" * 70)
        print()
        print("Interpretation:")
        print("  - DataCollector and FxScalper_ML compute IDENTICAL features")
        print("  - Train/serve consistency VERIFIED")
        print("  - Shared FeatureComputer module is CORRECT")
        print("  - Safe to proceed to demo deployment")
        print()
        return 0
    else:
        print("=" * 70)
        print("STATUS: ❌ FAIL - Feature skew detected!")
        print("=" * 70)
        print()
        print("Features with differences > tolerance:")
        print()

        skewed = []
        for i, col_name in enumerate(FEATURE_NAMES):
            if max_per_col[i] > TOLERANCE:
                skewed.append((col_name, max_per_col[i]))

        if skewed:
            skewed.sort(key=lambda x: -x[1])  # Sort by magnitude (largest first)
            for col_name, max_col_diff in skewed[:10]:  # Show top 10
                print(f"  {col_name:30s}: max diff = {max_col_diff:.15e}")

        print()
        print("Diagnosis:")
        print("  1. Check indicator initialization order (must be identical)")
        print("  2. Verify warmup bar skipping is identical (both skip first 300 bars)")
        print("  3. Check for timezone differences in time-based features")
        print("  4. Verify DataCollector CSV has same bars as cBot processed")
        print("  5. Check for floating point rounding differences")
        print()
        print("Next steps:")
        print("  1. Review FeatureComputer.cs for computation differences")
        print("  2. Add debug logging to isolate which feature diverges")
        print("  3. Verify indicator parameters are identical")
        print()
        return 1

if __name__ == "__main__":
    sys.exit(main())
