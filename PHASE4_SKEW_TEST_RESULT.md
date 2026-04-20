# Phase 4 Feature Skew Test Results

**Date:** 2026-04-20
**Test Period:** Jan 1-31, 2024 (EURUSD M5, 6,260 bars)
**Purpose:** Verify FxScalper_ML computes identical features to DataCollector
**Result:** ✅ **PASS** — max diff 5.0e-7 (within 1e-6 tolerance), 6260/6260 bars joined

## Final Results

```
================================================================================
PHASE 4 FEATURE SKEW TEST (timestamp-joined)
================================================================================
CSV-A (DataCollector): DataCollector_EURUSD_M5_20240101_220000.csv
CSV-B (FxScalper_ML):  FxScalper_features_debug_20240101-20-04-2026.csv

CSV-A rows: 6260
CSV-B rows: 6260
Joined rows (inner on timestamp): 6260
Unmatched — CSV-A only: 0
Unmatched — CSV-B only: 0

DIFFERENCE STATISTICS (joined frame):
  Max absolute difference: 4.999999999588667e-07
  Mean difference:         1.775917150544882e-07
  Median difference:       1.428571430000093e-07
  Std deviation:           1.665870292018247e-07
  Tolerance:               1.000000000000000e-06

================================================================================
PASS — Feature Skew Test Successful
================================================================================
```

Residual 5e-7 is pure rounding from DataCollector's `F6` format (6-decimal truncation). FxScalper writes full precision (`G17`). Shared `FeatureComputer` math is bit-identical.

## Investigation Summary

An earlier positional diff reported max 200 pips across 46/46 features with an "alternating row match + adjacent swap" pattern — documented in `FEATURE_SKEW_ANALYSIS.md`. Investigation traced this to a **diagnostic-side bug, not a feature-computation bug**:

1. **`cbot/JCAMP_DataCollector.cs:240`** writes rows only after each bar's trade outcome resolves. Because bar N+1 can resolve before bar N (short-path outcomes hit first), CSV rows land **out of bar-chronological order**.
2. **`cbot/JCAMP_FxScalper_ML/JCAMP_FxScalper_ML.cs`** writes rows immediately on `OnBar()`, so its CSV **is** in bar-chronological order.
3. **`compare_feature_skew.py` (original)** diffed the two frames positionally with no timestamp join. Out-of-order rows on one side collided with in-order rows on the other, producing the alternating-swap signature.
4. FxScalper's debug CSV had no timestamp column, so the diagnostic had no join key to recover with.

## Fix (landed in commit `de6c812`)

1. **FxScalper_ML debug CSV gains `time_utc` column** (`Bars.OpenTimes[closedBarIdx]`). Header and row writes updated.
2. **`compare_feature_skew.py` rewritten** to inner-join on timestamp. Reports unmatched rows from each side and the 5 worst-aligned bars on FAIL.
3. **Debug logging removed post-PASS** (`StreamWriter` field, init block, OnBar write, OnStop close, `System.IO` using) from both worktree and cTrader source copies.

## Verification

Re-run on 2026-04-20: **PASS** with stats above. `FeatureComputer` and `DataCollector.cs` untouched — they were correct throughout.

## Files Involved

- **Shared feature module:** `cbot/JCAMP_FxScalper_ML/JCAMP_Features.cs` (moved from `cbot/` into the cBot folder for cTrader project layout)
- **DataCollector:** `cbot/JCAMP_DataCollector.cs`
- **Trading cBot:** `cbot/JCAMP_FxScalper_ML/JCAMP_FxScalper_ML.cs`
- **Diagnostics:** `compare_feature_skew.py`, `diagnose_feature_skew.py`
- **Detailed investigation log:** `FEATURE_SKEW_ANALYSIS.md`

## Precision Note

DataCollector writes features as `F6` (6-decimal truncation); FxScalper writes `G17` (full precision). Residual ~5e-7 diff is half-ULP of `1e-6` — pure rounding. If tolerance is ever tightened below 5e-7, switch DataCollector to `G17` as well.

## Next Steps

1. ✅ Shared `FeatureComputer` module
2. ✅ DataCollector refactored to use it
3. ✅ FxScalper_ML using it
4. ✅ Skew test PASS
5. ✅ Debug logging removed
6. ✅ Phase 4 documentation updated
7. ⏭ **2-week FP Markets demo deployment** (per `PHASE4_DEPLOYMENT_READY.md`)
