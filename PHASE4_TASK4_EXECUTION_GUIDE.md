# Phase 4 Task 4: Feature Skew Test Execution Guide

**Status:** Ready to Execute
**Date:** 2026-04-19
**Objective:** Verify that DataCollector and FxScalper_ML compute IDENTICAL features

## Critical Requirement

Max difference per cell must be ≤ **0.000001** (floating point tolerance).

If ANY cell differs by more than this, train/serve consistency is broken and the model will perform poorly in live trading.

## Test Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 4: Feature Skew Test                                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ CSV-A: DataCollector on Jan 2024                            │
│   ├─ Run cTrader backtest (EURUSD, M5)                      │
│   ├─ Date range: Jan 1-31, 2024 (~7000 bars)               │
│   └─ Output: DataCollector_EURUSD_M5_*.csv (46 features)    │
│                                                              │
│ CSV-B: FxScalper_ML on Jan 2024                             │
│   ├─ Run cTrader backtest (EURUSD, M5)                      │
│   ├─ Date range: Jan 1-31, 2024 (~7000 bars)               │
│   ├─ EnableTrading: false (simulation mode)                 │
│   └─ Output: FxScalper_features_debug.csv (46 features)     │
│                                                              │
│ Comparison Python Script                                    │
│   ├─ Load both CSVs                                         │
│   ├─ Extract 46 feature columns                             │
│   ├─ Calculate max absolute difference per cell             │
│   └─ Report: PASS (max diff ≤ 0.000001) or FAIL            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Execution Steps

### Step 1: Prepare DataCollector Backtest

1. **Open cTrader Automate**
   - File → Open Backtest Project
   - Navigate to: `.worktrees/phase4-cbot/cbot/JCAMP_DataCollector.cs`

2. **Configure Backtest Parameters**
   ```
   Symbol:         EURUSD
   Timeframe:      M5 (CRITICAL: must be M5)
   Start Date:     2024-01-01 00:00
   End Date:       2024-01-31 23:59
   Initial Balance: 10000 USD (any amount, DataCollector doesn't trade)
   Mode:           Backtest (no live trading)
   ```

3. **Verify Parameters**
   - Output Folder: `C:\Users\Jcamp_Laptop\Documents\JCAMP_Data\`
   - SL ATR Multiplier: 1.5
   - TP ATR Multiplier: 4.5
   - Max Bars To Outcome: 72 (6 hours)

4. **Run Backtest**
   - Click "Start" or "Run"
   - Wait for backtest to complete (should take 1-3 minutes)
   - Monitor logs for "DataCollector started" and "DataCollector stopped"

5. **Verify Output**
   - Check: `C:\Users\Jcamp_Laptop\Documents\JCAMP_Data\`
   - Should find: `DataCollector_EURUSD_M5_20240101_*.csv` (timestamp in filename)
   - Expected rows: ~7000 (one per M5 bar after warmup)
   - Expected columns: `timestamp, symbol, [46 features], outcome_long, bars_to_outcome_long, outcome_short, bars_to_outcome_short`

### Step 2: Prepare FxScalper_ML Backtest

1. **Open cTrader Automate**
   - File → Open Backtest Project
   - Navigate to: `.worktrees/phase4-cbot/cbot/JCAMP_FxScalper_ML/JCAMP_FxScalper_ML.cs`

2. **Configure Backtest Parameters**
   ```
   Symbol:         EURUSD
   Timeframe:      M5 (CRITICAL: must be M5)
   Start Date:     2024-01-01 00:00
   End Date:       2024-01-31 23:59
   Initial Balance: 10000 USD
   Mode:           Backtest (no live trading)
   ```

3. **Verify cBot Parameters**
   - ML Threshold: 0.65 (any value, we're not trading)
   - Enable Trading: **false** (CRITICAL: disable trading, we only want feature logging)
   - API URL: http://localhost:8000/predict (API won't be called in backtest)

4. **Run Backtest**
   - Click "Start" or "Run"
   - Wait for backtest to complete (should take 1-3 minutes)
   - Monitor logs for "JCAMP FxScalper ML v1.0.0" and "STOPPED"

5. **Verify Output**
   - Check: `C:\Users\Jcamp_Laptop\Documents\JCAMP_Data\`
   - Should find: `FxScalper_features_debug.csv` (fresh, timestamped from backtest)
   - Expected rows: ~7000 (same as DataCollector)
   - Expected columns: 46 feature columns (in same order as FeatureComputer.FEATURE_NAMES)

### Step 3: Run Comparison Script

1. **Open Terminal/Command Prompt**
   ```bash
   cd D:\JCAMP_FxScalper_ML\.worktrees\phase4-cbot
   ```

2. **Run Comparison**
   ```bash
   python compare_feature_skew.py ^
     "C:\Users\Jcamp_Laptop\Documents\JCAMP_Data\DataCollector_EURUSD_M5_20240101_*.csv" ^
     "C:\Users\Jcamp_Laptop\Documents\JCAMP_Data\FxScalper_features_debug.csv"
   ```

3. **Expected Output**
   ```
   ======================================================================
   FEATURE SKEW TEST - COMPARISON REPORT
   ======================================================================

   Loading DataCollector CSV: ...
     - Rows: 7000
     - Columns: ...

   Loading FxScalper_ML CSV: ...
     - Rows: 7000
     - Columns: 46

   Extracting feature columns...
     - DataCollector: 46 features extracted
     - FxScalper_ML: 46 features extracted

   Aligning CSVs: comparing first 7000 rows

   ======================================================================
   COMPARISON RESULTS
   ======================================================================

   Total cells compared: 7000 rows × 46 features = 322,000

   Max absolute difference:     0.000000000000000e+00
   Mean absolute difference:    0.000000000000000e+00
   Median absolute difference:  0.000000000000000e+00
   Tolerance (acceptance):      1.000000000000000e-06

   ======================================================================
   STATUS: ✅ PASS - Features are identical within tolerance!
   ======================================================================
   ```

### Step 4: Interpret Results

#### If PASS (max difference ≤ 0.000001)

```
STATUS: ✅ PASS - Features are identical within tolerance!

Interpretation:
  - DataCollector and FxScalper_ML compute IDENTICAL features
  - Train/serve consistency VERIFIED
  - Shared FeatureComputer module is CORRECT
  - Safe to proceed to demo deployment
```

**Next Action:** Proceed to Task 5 (FastAPI Config Verification) and then demo deployment.

#### If FAIL (max difference > 0.000001)

```
STATUS: ❌ FAIL - Feature skew detected!

Features with differences > tolerance:
  [list of columns with their max differences]
```

**Root Cause Analysis Steps:**

1. **Check indicator initialization order**
   - Both implementations must initialize indicators in identical order
   - Verify warmup bars are skipped identically
   - Verify indicator parameters match (SMA periods, RSI period, etc.)

2. **Verify bar indexing**
   - OnBar() fires when new bar opens
   - Just-closed bar is at index `Count-2` (not `Count-1`)
   - Both must use same index calculation

3. **Check HTF indicator reads**
   - HTF indicators must use `.Last(1)` (most recent closed bar)
   - NOT `.LastValue` (still-forming bar)
   - Both implementations must use same method

4. **Look for floating point rounding**
   - Some features use `/ atr` normalization
   - Small rounding differences can accumulate
   - If differences are very small (< 1e-10), might be acceptable

5. **Verify warmup skipping**
   - Both skip first 300 M5 bars
   - Both skip if `_h4.Count < 200`
   - Verify skip logic is identical

**How to Debug:**

1. Add print statements to FeatureComputer.cs
   ```csharp
   Print($"dist_sma_m5_50 = {f["dist_sma_m5_50"]}");
   ```

2. Compare intermediate values (SMAs, RSI, etc.)

3. Check if issue is in specific feature groups:
   - Distance features (dist_sma_*)
   - Momentum features (rsi_*, adx_*)
   - ATR features (atr_*)
   - MTF features (mtf_alignment_*)
   - Time features (hour_utc, dow, etc.)

### Step 5: Clean Up Temporary Logging

After test complete, remove temporary CSV logging code:

**File:** `.worktrees/phase4-cbot/cbot/JCAMP_FxScalper_ML/JCAMP_FxScalper_ML.cs`

1. Remove field declaration (line ~81):
   ```csharp
   // TEMPORARY: CSV debug output for feature skew test
   private StreamWriter _csvDebug;
   ```

2. Remove using statement (line ~16):
   ```csharp
   using System.IO;
   ```

3. Remove initialization code in OnStart() (lines ~163-168):
   ```csharp
   // TEMPORARY: Log features to CSV for skew test
   string debugPath = @"C:\Users\Jcamp_Laptop\Documents\JCAMP_Data\FxScalper_features_debug.csv";
   Directory.CreateDirectory(Path.GetDirectoryName(debugPath));
   _csvDebug = new StreamWriter(debugPath);
   _csvDebug.WriteLine(string.Join(",", FeatureComputer.FEATURE_NAMES));
   ```

4. Remove logging code in OnBar() (lines ~205-212):
   ```csharp
   // TEMPORARY: Log features for skew test
   if (_csvDebug != null)
   {
       var values = new List<string>();
       foreach (var name in FeatureComputer.FEATURE_NAMES)
           values.Add(feat[name].ToString("G17"));
       _csvDebug.WriteLine(string.Join(",", values));
       _csvDebug.Flush();
   }
   ```

5. Remove cleanup in OnStop() (line ~427):
   ```csharp
   _csvDebug?.Close();
   ```

### Step 6: Document Results

Update `PHASE4_SKEW_TEST_RESULT.md`:

```markdown
## Results

**Test Date:** [date you ran test]
**Test Period:** January 2024 (2024-01-01 to 2024-01-31)
**Timeframe:** M5
**Symbol:** EURUSD
**Rows Compared:** 7000

### Comparison Statistics
- Max absolute difference: [X.XXXXX e-XX]
- Mean absolute difference: [X.XXXXX e-XX]
- Tolerance: 1.000000 e-06

### Status
[PASS or FAIL]

### Interpretation
[explanation of results]
```

### Step 7: Commit Results

```bash
cd D:\JCAMP_FxScalper_ML\.worktrees\phase4-cbot
git add PHASE4_SKEW_TEST_RESULT.md
git commit -m "test: Phase 4 Task 4 feature skew test results - PASS/FAIL"
```

## Key Files

- **Comparison Script:** `compare_feature_skew.py`
- **Results Document:** `PHASE4_SKEW_TEST_RESULT.md`
- **Feature Module:** `cbot/JCAMP_Features.cs` (shared by both cBots)
- **DataCollector:** `cbot/JCAMP_DataCollector.cs`
- **Trading cBot:** `cbot/JCAMP_FxScalper_ML/JCAMP_FxScalper_ML.cs`

## Success Criteria

- ✓ DataCollector backtest completes on Jan 2024
- ✓ FxScalper_ML backtest completes on Jan 2024
- ✓ Comparison script runs successfully
- ✓ Result: PASS (max difference ≤ 0.000001) OR documented FAIL with root cause
- ✓ Temporary logging code removed
- ✓ Results committed to git

## Next Steps After PASS

1. Task 5: Verify FastAPI configuration and model file
2. Task 6: Deploy demo trading system
3. Monitor live trading performance

## Notes

### Why This Matters

The ML model was trained on features computed by DataCollector v0.4. When FxScalper_ML uses features with ANY differences:
- Model performance degrades (garbage in, garbage out)
- Predictions become unreliable
- Win rate drops, losses increase

The shared FeatureComputer architecture **guarantees** identical computation because:
1. Single source of truth (one file, two imports)
2. Stateful features maintained consistently
3. Indicator initialization identical
4. Bar indexing identical
5. HTF reads (Last(1)) identical

This is the foundation of a production-grade trading system.

### Tolerance Explanation

Floating point precision ≤ 0.000001 (1e-6) is acceptable because:
- C# decimal precision varies by operation
- IEEE 754 double precision can introduce small rounding errors
- ATR normalization (division) may round differently
- Historical data from different sources can have micro-tick differences

However, differences > 1e-6 indicate a real computational difference that will affect predictions.

### Debugging Tips

If test FAILS:

1. Check if difference is in ONE feature or MANY
   - One feature: likely indicator initialization or computation logic
   - Many features: likely bar indexing or warmup skipping issue

2. Check if difference is consistent or varies
   - Consistent (same every bar): likely systematic error in computation
   - Varies: likely floating point rounding or state management issue

3. Add debug prints to FeatureComputer
   ```csharp
   if (closedBarIdx < 5)  // Just after warmup
       Print($"Feature check: {f["dist_sma_m5_50"]}");
   ```

4. Compare intermediate values
   - Check if SMA values match
   - Check if RSI values match
   - Check if ATR values match

5. Verify indicator attachment
   - Both must attach indicators to same series (M5 vs M15 vs M30 vs H1)
   - Both must read from same bars series
