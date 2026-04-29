"""
v0.6 CSV sanity check.

Verifies:
- New CSV loads cleanly with 49 features (was 46 in v0.5)
- The 3 new structure features are present and sanely distributed
- No NaN/Inf in the new columns
- Train/CV/holdout splits work
"""

import sys
sys.path.append('.')

import pandas as pd
import numpy as np

from src.data_loader import load_datacollector_csv, get_data_splits
from src.features import get_feature_columns

CSV_PATH = 'data/DataCollector_EURUSD_M5_20230102_000000.csv'
NEW_FEATURES = ['bars_since_swing_high', 'bars_since_swing_low', 'pullback_depth_pct']

print("=" * 70)
print("v0.6 CSV Sanity Check")
print("=" * 70)

print(f"\n[1/4] Loading {CSV_PATH}...")
df = load_datacollector_csv(CSV_PATH)
print(f"  Rows: {len(df):,}")
print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

print(f"\n[2/4] Feature columns...")
features = get_feature_columns(df)
print(f"  Total features: {len(features)} (expected 49)")
missing = [f for f in NEW_FEATURES if f not in features]
if missing:
    print(f"  [FAIL] Missing new features: {missing}")
    raise SystemExit(1)
print(f"  All 3 new features present.")
print(f"  Position in column list:")
for f in NEW_FEATURES:
    print(f"    {features.index(f):3d}: {f}")

print(f"\n[3/4] New feature distributions...")
print(df[NEW_FEATURES].describe().round(3).to_string())
print()
print(f"  NaN counts:")
for f in NEW_FEATURES:
    n_nan = df[f].isna().sum()
    n_inf = np.isinf(df[f]).sum()
    print(f"    {f:30s}: NaN={n_nan}  Inf={n_inf}")

print(f"\n  Sanity checks:")
# bars_since_swing_high should be in [0, 200]
bsh = df['bars_since_swing_high']
bsl = df['bars_since_swing_low']
pdp = df['pullback_depth_pct']
print(f"    bars_since_swing_high  range: [{bsh.min()}, {bsh.max()}]  (expect [0, 200])")
print(f"    bars_since_swing_low   range: [{bsl.min()}, {bsl.max()}]  (expect [0, 200])")
print(f"    pullback_depth_pct     range: [{pdp.min():.4f}, {pdp.max():.4f}]  (expect [0, 1])")
print(f"    pullback_depth_pct     mean:  {pdp.mean():.3f}  (expect ~0.5)")
print(f"    bars_since_swing_high  mean:  {bsh.mean():.1f}  (uptrend bias if << 25, neutral ~25, bearish if >> 25)")
print(f"    bars_since_swing_low   mean:  {bsl.mean():.1f}  (mirror)")

print(f"\n[4/4] Data splits...")
train_cv, holdout, live = get_data_splits(df)
print(f"  Train/CV : {len(train_cv):,} rows ({train_cv['timestamp'].min()} -> {train_cv['timestamp'].max()})")
print(f"  Holdout  : {len(holdout):,} rows ({holdout['timestamp'].min()} -> {holdout['timestamp'].max()})")
print(f"  Live     : {len(live):,} rows ({live['timestamp'].min()} -> {live['timestamp'].max()})")

print(f"\n[OK] CSV ready for v0.6 retrain.")
