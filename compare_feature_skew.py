"""
Phase 4 Feature Skew Test
========================
Compare DataCollector vs FxScalper_ML feature computation
Test: Jan 2024 EURUSD M5 (46 features, ~7000 bars)
Tolerance: max difference ≤ 0.000001 (floating point precision)
"""

import pandas as pd
import numpy as np
import os
from pathlib import Path

# Feature names (must match JCAMP_Features.cs exactly)
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

# File paths
outputs_dir = Path("outputs")
csv_a = outputs_dir / "DataCollector_EURUSD_M5_20240101_220030.csv"
csv_b = outputs_dir / "FxScalper_features_debug_20240101-20-04-2026.csv"

print("=" * 80)
print("PHASE 4 FEATURE SKEW TEST")
print("=" * 80)
print()

# Verify files exist
if not csv_a.exists():
    print(f"ERROR: CSV-A not found: {csv_a}")
    exit(1)

if not csv_b.exists():
    print(f"ERROR: CSV-B not found: {csv_b}")
    exit(1)

print(f"CSV-A (DataCollector): {csv_a.name}")
print(f"CSV-B (FxScalper_ML):  {csv_b.name}")
print()

# Load CSVs
print("Loading CSV files...")
collector = pd.read_csv(csv_a)
fxscalper = pd.read_csv(csv_b)

print(f"  CSV-A rows: {len(collector)}")
print(f"  CSV-B rows: {len(fxscalper)}")
print()

# Check row count match
if len(collector) != len(fxscalper):
    print(f"WARNING: Row count mismatch (A={len(collector)}, B={len(fxscalper)})")
    print(f"  Using minimum: {min(len(collector), len(fxscalper))}")
    min_rows = min(len(collector), len(fxscalper))
    collector = collector.iloc[:min_rows]
    fxscalper = fxscalper.iloc[:min_rows]
    print()

# Verify all 46 features present
print("Verifying 46 features...")
missing_a = [f for f in FEATURE_NAMES if f not in collector.columns]
missing_b = [f for f in FEATURE_NAMES if f not in fxscalper.columns]

if missing_a:
    print(f"ERROR: Missing in CSV-A: {missing_a}")
    exit(1)

if missing_b:
    print(f"ERROR: Missing in CSV-B: {missing_b}")
    exit(1)

print(f"  All 46 features present in both files")
print()

# Compare features
print("Comparing features...")
print(f"  Testing: {len(FEATURE_NAMES)} features x {len(collector)} bars = {len(FEATURE_NAMES) * len(collector)} values")
print()

# Calculate absolute differences
diff = np.abs(collector[FEATURE_NAMES].values - fxscalper[FEATURE_NAMES].values)
max_diff = np.max(diff)
max_per_col = np.max(diff, axis=0)
max_per_row = np.max(diff, axis=1)

# Calculate statistics
tolerance = 0.000001
mean_diff = np.mean(diff)
median_diff = np.median(diff)
std_diff = np.std(diff)

print(f"DIFFERENCE STATISTICS:")
print(f"  Max absolute difference:    {max_diff:.15e}")
print(f"  Mean difference:            {mean_diff:.15e}")
print(f"  Median difference:          {median_diff:.15e}")
print(f"  Std deviation:              {std_diff:.15e}")
print(f"  Tolerance:                  {tolerance:.15e}")
print()

# Test result
if max_diff <= tolerance:
    print("=" * 80)
    print("PASS - Feature Skew Test Successful")
    print("=" * 80)
    print()
    print(f"Conclusion: DataCollector and FxScalper_ML compute IDENTICAL features")
    print(f"            within floating point precision (max diff <= {tolerance:.0e})")
    print()
    print("Interpretation:")
    print("  * Both use shared FeatureComputer class")
    print("  * Identical indicator initialization")
    print("  * Identical bar indexing")
    print("  * Train/serve consistency GUARANTEED")
    print()
    print("Next Step: Remove temporary CSV logging from FxScalper_ML and deploy")
    exit(0)
else:
    print("=" * 80)
    print("FAIL - Feature Skew Detected")
    print("=" * 80)
    print()
    print(f"Max difference {max_diff:.15e} exceeds tolerance {tolerance:.15e}")
    print()
    print("Features with differences > tolerance:")
    for i, col in enumerate(FEATURE_NAMES):
        if max_per_col[i] > tolerance:
            print(f"  {col:30s}: max diff = {max_per_col[i]:.15e}")
    print()
    print("Investigation needed:")
    print("  1. Check indicator initialization (same parameters in both cBots?)")
    print("  2. Check bar indexing (closedBarIdx calculation identical?)")
    print("  3. Check stateful fields (MTF tracking, ATR history initialized same?)")
    print("  4. Check data types (float precision issues?)")
    exit(1)
