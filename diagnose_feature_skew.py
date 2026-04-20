"""
Feature Skew Diagnostic - Detailed Analysis
Analyzes the nature and pattern of feature differences
"""

import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict

# Load CSVs
outputs_dir = Path("outputs")
collector = pd.read_csv(outputs_dir / "DataCollector_EURUSD_M5_20240101_220000.csv")
fxscalper = pd.read_csv(outputs_dir / "FxScalper_features_debug_20240101-20-04-2026.csv")

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

# Calculate differences
diff = collector[FEATURE_NAMES].values - fxscalper[FEATURE_NAMES].values
abs_diff = np.abs(diff)

print("=" * 80)
print("FEATURE SKEW DIAGNOSTIC ANALYSIS")
print("=" * 80)
print()

# Categorize features by type
categories = {
    'SMA Distance': ["dist_sma_m5_50", "dist_sma_m5_100", "dist_sma_m5_200",
                     "dist_sma_m5_275", "dist_sma_m15_200", "dist_sma_m30_200",
                     "dist_sma_h1_200", "dist_sma_h4_200"],
    'Slopes': ["slope_sma_m5_200", "slope_sma_h1_200"],
    'Momentum (RSI/ADX)': ["rsi_m5", "rsi_m15", "rsi_m30", "adx_m5", "di_plus_m5", "di_minus_m5"],
    'Volatility (ATR/BB)': ["atr_m5", "atr_m15", "atr_h1", "atr_ratio_m5_h1", "bb_width"],
    'Bar Patterns': ["bar0_body", "bar0_range", "bar1_body", "bar1_range",
                     "bar2_body", "bar2_range", "bar3_body", "bar3_range",
                     "bar4_body", "bar4_range"],
    'Swing Levels': ["dist_swing_high", "dist_swing_low"],
    'Time/Session': ["hour_utc", "dow", "sess_asia", "sess_london", "sess_ny"],
    'MTF Features': ["mtf_alignment_score", "mtf_stacking_score",
                     "bars_since_tf_fast_flip", "tf_fast_flip_direction",
                     "mtf_alignment_duration"],
    'Other': ["spread_pips", "atr_percentile_2000bar", "h1_alignment_agreement"],
}

# Analyze by category
print("CATEGORY ANALYSIS:")
print()

for cat_name, cat_features in categories.items():
    cat_indices = [FEATURE_NAMES.index(f) for f in cat_features if f in FEATURE_NAMES]
    cat_diff = abs_diff[:, cat_indices]

    max_diff = np.max(cat_diff)
    mean_diff = np.mean(cat_diff)
    non_zero = np.count_nonzero(cat_diff)
    pct_diff = (non_zero / cat_diff.size) * 100

    print(f"{cat_name:25s}: max={max_diff:12.4e}, mean={mean_diff:12.4e}, affected={pct_diff:5.1f}%")

print()
print("=" * 80)
print("ROW-BY-ROW ANALYSIS: Where is skew introduced?")
print("=" * 80)
print()

# Find rows with maximum differences
for i in range(min(20, len(collector))):
    row_max = np.max(abs_diff[i, :])
    if row_max > 0.1:
        print(f"Row {i:4d}: max_diff={row_max:12.4e}")
        for j, feat in enumerate(FEATURE_NAMES):
            if abs_diff[i, j] > 1.0:
                dc_val = collector[feat].iloc[i]
                fs_val = fxscalper[feat].iloc[i]
                print(f"  {feat:30s}: DC={dc_val:10.2f}, FS={fs_val:10.2f}, diff={diff[i, j]:10.2f}")

print()
print("=" * 80)
print("SAMPLE SNAPSHOT")
print("=" * 80)
print()

# Show first few rows of key features
sample_features = ["dist_sma_m5_200", "rsi_m5", "hour_utc", "bars_since_tf_fast_flip"]
print("First 10 rows of selected features:")
print()

for feat in sample_features:
    dc_col = collector[feat].values[:10]
    fs_col = fxscalper[feat].values[:10]
    diff_col = diff[:10, FEATURE_NAMES.index(feat)]

    print(f"{feat}:")
    for i in range(10):
        print(f"  Row {i}: DC={dc_col[i]:10.4f}, FS={fs_col[i]:10.4f}, diff={diff_col[i]:10.4f}")
    print()

print("=" * 80)
print("HYPOTHESIS: Initialization/Warmup Offset")
print("=" * 80)
print()

# Check if there's a pattern suggesting offset
print("Checking if DataCollector might be ahead/behind by N bars...")
for offset in [1, 5, 10, 20, 50]:
    if offset < len(collector):
        shifted_diff = np.abs(collector[FEATURE_NAMES].values[offset:] -
                              fxscalper[FEATURE_NAMES].values[:-offset])
        if len(shifted_diff) > 0:
            max_offset_diff = np.max(shifted_diff)
            print(f"  Offset {offset:3d} bars: max_diff = {max_offset_diff:.4e}")
