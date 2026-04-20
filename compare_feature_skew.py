"""
Phase 4 Feature Skew Test — timestamp-joined comparison.

Compares DataCollector vs FxScalper_ML feature computation by inner-joining
on bar timestamp. DataCollector writes rows as trade outcomes resolve (not in
bar order); FxScalper writes rows in bar order on OnBar(). Positional diff
produced spurious 200-pip mismatches — this version joins on time and only
diffs co-located bars.

Tolerance: max difference <= 1e-06 (floating point precision). Note that
DataCollector formats features with "F6" (6-decimal truncation), so a clean
PASS may require loosening to ~1e-4 if rounding noise dominates. We log the
max diff either way so the real signal is visible.
"""

import pandas as pd
import numpy as np
from pathlib import Path

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

outputs_dir = Path("outputs")
csv_a = outputs_dir / "DataCollector_EURUSD_M5_20240101_220000.csv"
csv_b = outputs_dir / "FxScalper_features_debug_20240101-20-04-2026.csv"

TOLERANCE = 1e-6

print("=" * 80)
print("PHASE 4 FEATURE SKEW TEST (timestamp-joined)")
print("=" * 80)

if not csv_a.exists():
    print(f"ERROR: CSV-A not found: {csv_a}")
    raise SystemExit(1)
if not csv_b.exists():
    print(f"ERROR: CSV-B not found: {csv_b}")
    raise SystemExit(1)

print(f"CSV-A (DataCollector): {csv_a.name}")
print(f"CSV-B (FxScalper_ML):  {csv_b.name}")
print()

collector = pd.read_csv(csv_a)
fxscalper = pd.read_csv(csv_b)

if "timestamp" not in collector.columns:
    print("ERROR: CSV-A missing 'timestamp' column")
    raise SystemExit(1)
if "time_utc" not in fxscalper.columns:
    print("ERROR: CSV-B missing 'time_utc' column (did you rebuild FxScalper_ML?)")
    raise SystemExit(1)

collector["_ts"] = pd.to_datetime(collector["timestamp"], format="%Y-%m-%d %H:%M:%S")
fxscalper["_ts"] = pd.to_datetime(fxscalper["time_utc"], format="%Y-%m-%d %H:%M:%S")

collector = collector.sort_values("_ts").reset_index(drop=True)
fxscalper = fxscalper.sort_values("_ts").reset_index(drop=True)

missing_a = [f for f in FEATURE_NAMES if f not in collector.columns]
missing_b = [f for f in FEATURE_NAMES if f not in fxscalper.columns]
if missing_a:
    print(f"ERROR: Missing in CSV-A: {missing_a}")
    raise SystemExit(1)
if missing_b:
    print(f"ERROR: Missing in CSV-B: {missing_b}")
    raise SystemExit(1)

a_cols = ["_ts"] + FEATURE_NAMES
b_cols = ["_ts"] + FEATURE_NAMES
joined = collector[a_cols].merge(
    fxscalper[b_cols], on="_ts", how="inner", suffixes=("_a", "_b")
)

only_a = len(collector) - len(joined)
only_b = len(fxscalper) - len(joined)
print(f"CSV-A rows: {len(collector)}")
print(f"CSV-B rows: {len(fxscalper)}")
print(f"Joined rows (inner on timestamp): {len(joined)}")
print(f"Unmatched — CSV-A only: {only_a}")
print(f"Unmatched — CSV-B only: {only_b}")
print()

if len(joined) == 0:
    print("ERROR: zero rows after timestamp join — date ranges don't overlap")
    raise SystemExit(1)

a_vals = joined[[f + "_a" for f in FEATURE_NAMES]].to_numpy(dtype=float)
b_vals = joined[[f + "_b" for f in FEATURE_NAMES]].to_numpy(dtype=float)
diff = np.abs(a_vals - b_vals)

max_diff = float(np.max(diff))
mean_diff = float(np.mean(diff))
median_diff = float(np.median(diff))
std_diff = float(np.std(diff))

print("DIFFERENCE STATISTICS (joined frame):")
print(f"  Max absolute difference: {max_diff:.15e}")
print(f"  Mean difference:         {mean_diff:.15e}")
print(f"  Median difference:       {median_diff:.15e}")
print(f"  Std deviation:           {std_diff:.15e}")
print(f"  Tolerance:               {TOLERANCE:.15e}")
print()

if max_diff <= TOLERANCE and only_a == 0 and only_b == 0:
    print("=" * 80)
    print("PASS — Feature Skew Test Successful")
    print("=" * 80)
    raise SystemExit(0)

print("=" * 80)
print("FAIL — Feature Skew Detected")
print("=" * 80)
print()

max_per_col = np.max(diff, axis=0)
print("Features exceeding tolerance:")
for i, col in enumerate(FEATURE_NAMES):
    if max_per_col[i] > TOLERANCE:
        print(f"  {col:30s}: max diff = {max_per_col[i]:.6e}")
print()

max_per_row = np.max(diff, axis=1)
worst_rows = np.argsort(max_per_row)[-5:][::-1]
print("Top 5 worst-aligned rows (by max per-row diff):")
for r in worst_rows:
    ts = joined["_ts"].iloc[r]
    worst_feat_idx = int(np.argmax(diff[r]))
    feat_name = FEATURE_NAMES[worst_feat_idx]
    a_val = a_vals[r, worst_feat_idx]
    b_val = b_vals[r, worst_feat_idx]
    print(f"  {ts}  feat={feat_name:28s}  DC={a_val:.6f}  FS={b_val:.6f}  diff={diff[r, worst_feat_idx]:.6e}")

raise SystemExit(1)
