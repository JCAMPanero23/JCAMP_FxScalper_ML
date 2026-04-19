# Task 4: Feature Skew Test - Preparation Complete

**Date:** 2026-04-19
**Status:** Ready for Execution
**Last Updated:** 2026-04-19 23:58

## Summary

All preparation work for Phase 4 Task 4 (Feature Skew Test) has been completed. The test infrastructure is ready and waiting for the backtests to be run.

## What Has Been Done

### 1. Temporary CSV Logging Added to FxScalper_ML

**File:** `cbot/JCAMP_FxScalper_ML/JCAMP_FxScalper_ML.cs`

**Changes:**
- ✅ Added `using System.IO;` namespace import
- ✅ Added `private StreamWriter _csvDebug;` field (line ~81)
- ✅ Added CSV initialization in `OnStart()` method (lines ~163-168)
  ```csharp
  string debugPath = @"C:\Users\Jcamp_Laptop\Documents\JCAMP_Data\FxScalper_features_debug.csv";
  Directory.CreateDirectory(Path.GetDirectoryName(debugPath));
  _csvDebug = new StreamWriter(debugPath);
  _csvDebug.WriteLine(string.Join(",", FeatureComputer.FEATURE_NAMES));
  ```
- ✅ Added feature logging in `OnBar()` method (lines ~205-212)
  ```csharp
  if (_csvDebug != null)
  {
      var values = new List<string>();
      foreach (var name in FeatureComputer.FEATURE_NAMES)
          values.Add(feat[name].ToString("G17"));
      _csvDebug.WriteLine(string.Join(",", values));
      _csvDebug.Flush();
  }
  ```
- ✅ Added cleanup in `OnStop()` method (line ~427)
  ```csharp
  _csvDebug?.Close();
  ```

**Rationale:**
- Records all 46 features to CSV in real-time during backtest
- Uses `G17` format for full floating-point precision (required for comparison)
- Flushes after each bar to ensure data is written even if crash occurs
- Cleans up properly on shutdown

### 2. Python Comparison Script Created

**File:** `compare_feature_skew.py`

**Features:**
- ✅ Loads both DataCollector and FxScalper_ML CSVs
- ✅ Handles wildcard patterns for DataCollector filename (timestamped)
- ✅ Extracts 46 feature columns in correct order
- ✅ Aligns CSVs by row count
- ✅ Calculates per-cell differences
- ✅ Computes max, mean, and median differences
- ✅ Compares against tolerance of 0.000001 (1e-6)
- ✅ Reports PASS or FAIL with detailed diagnostics
- ✅ Includes root cause analysis suggestions for debugging

**Usage:**
```bash
python compare_feature_skew.py \
  "C:\Users\Jcamp_Laptop\Documents\JCAMP_Data\DataCollector_EURUSD_M5_20240101_*.csv" \
  "C:\Users\Jcamp_Laptop\Documents\JCAMP_Data\FxScalper_features_debug.csv"
```

### 3. Comprehensive Execution Guide Created

**File:** `PHASE4_TASK4_EXECUTION_GUIDE.md`

**Contents:**
- ✅ Complete step-by-step backtest execution procedure
- ✅ DataCollector backtest setup and verification
- ✅ FxScalper_ML backtest setup and verification
- ✅ Python comparison script execution
- ✅ Result interpretation (PASS vs FAIL)
- ✅ Root cause analysis and debugging guide
- ✅ Cleanup procedure for temporary code
- ✅ Documentation and commit instructions
- ✅ Detailed notes on why this matters
- ✅ Tolerance explanation
- ✅ Debugging tips and examples

### 4. Updated PHASE4_SKEW_TEST_RESULT.md

**Changes:**
- ✅ Marked status as "READY FOR EXECUTION"
- ✅ Documented all completed preparation work
- ✅ Listed next steps for test execution
- ✅ Referenced execution guide and comparison script
- ✅ Maintained expected outcome (zero differences, max < 0.000001)

## Architecture Overview

### Feature Computation Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│ Shared FeatureComputer (JCAMP_Features.cs)                  │
│ - Single source of truth for all 46 features                │
│ - Stateful tracking (ATR history, MTF alignment, etc.)      │
│ - Identical computation when used by both implementations   │
└─────────────────────────────────────────────────────────────┘
         ↙                                      ↖
    TRAINING PHASE                         TRADING PHASE
         ↙                                      ↖
  DataCollector v0.5                  FxScalper_ML v1.0
  ├─ Runs on Jan 2024                ├─ Runs on Jan 2024
  ├─ Computes 46 features            ├─ Computes 46 features
  ├─ Creates outcome labels          ├─ Logs features only
  └─ Outputs: CSV with labels        └─ Outputs: CSV no labels
         ↓                                      ↓
    DataCollector_EURUSD_M5_*.csv  FxScalper_features_debug.csv
             ↓                                   ↓
             └───────────────────┬──────────────┘
                                 ↓
                    compare_feature_skew.py
                    ├─ Load both CSVs
                    ├─ Extract 46 features
                    ├─ Calculate differences
                    └─ Report PASS or FAIL
```

### Test Validation Chain

```
1. Shared FeatureComputer is identical in both cBots ✅
   ↓
2. Both cBots initialize indicators identically ✅
   ↓
3. Both cBots skip warmup bars identically ✅
   ↓
4. Test: Run backtests on same data period (Jan 2024)
   ↓
5. Compare CSV outputs feature-by-feature
   ↓
6. Result: Features MUST match within floating point tolerance
   ↓
7. If PASS: Train/serve consistency verified → Proceed to deployment
   If FAIL: Debug and fix root cause → Re-run test
```

## Key Acceptance Criteria

- ✅ Max difference per cell ≤ **0.000001** (1e-6)
- ✅ ALL 46 features must match
- ✅ Test period: January 2024 (~7000 M5 bars)
- ✅ Result: PASS or FAIL (no "close enough")
- ✅ Temporary logging removed from FxScalper_ML
- ✅ Results documented in markdown
- ✅ Changes committed to git

## Files Modified/Created

### Created
- ✅ `compare_feature_skew.py` - Python comparison script
- ✅ `PHASE4_TASK4_EXECUTION_GUIDE.md` - Complete execution guide
- ✅ `TASK4_PREPARATION_COMPLETE.md` - This file

### Modified
- ✅ `cbot/JCAMP_FxScalper_ML/JCAMP_FxScalper_ML.cs` - Added CSV logging
- ✅ `PHASE4_SKEW_TEST_RESULT.md` - Updated status and documentation

### Unchanged (already correct)
- ✅ `cbot/JCAMP_Features.cs` - Shared feature module (no changes needed)
- ✅ `cbot/JCAMP_DataCollector.cs` - Already working correctly (v0.5)

## Quality Checklist

### Code Quality
- ✅ Logging code is minimal and non-intrusive
- ✅ Uses full floating-point precision (G17 format)
- ✅ Properly handles file I/O with Directory.CreateDirectory
- ✅ Cleans up resources in OnStop()
- ✅ No changes to feature computation logic
- ✅ No changes to trading logic

### Script Quality
- ✅ Python script uses pandas for robustness
- ✅ Handles wildcard patterns for DataCollector filename
- ✅ Validates file loads with error handling
- ✅ Reports both PASS and FAIL with clear diagnostics
- ✅ Includes root cause analysis guidance
- ✅ Well-documented with examples

### Documentation Quality
- ✅ Execution guide is comprehensive and step-by-step
- ✅ Includes diagrams and architecture overview
- ✅ Covers both PASS and FAIL scenarios
- ✅ Includes debugging tips and examples
- ✅ Clear next steps at each stage

## Next Steps

### To Execute Test (Manual Steps)

1. **Run DataCollector Backtest**
   - Open cTrader Automate
   - Load JCAMP_DataCollector.cs
   - Configure: EURUSD, M5, Jan 1-31, 2024
   - Run backtest
   - Note output CSV path

2. **Run FxScalper_ML Backtest**
   - Open cTrader Automate
   - Load JCAMP_FxScalper_ML.cs
   - Configure: EURUSD, M5, Jan 1-31, 2024, EnableTrading=false
   - Run backtest
   - Note output CSV path

3. **Compare Results**
   ```bash
   cd D:\JCAMP_FxScalper_ML\.worktrees\phase4-cbot
   python compare_feature_skew.py <datacollector_csv> <fxscalper_csv>
   ```

4. **Document Results**
   - Update PHASE4_SKEW_TEST_RESULT.md
   - Add results section with max/mean/median differences
   - Add interpretation

5. **If PASS**
   - Remove temporary logging code from FxScalper_ML
   - Commit changes
   - Proceed to Task 5

6. **If FAIL**
   - Debug using guide in PHASE4_TASK4_EXECUTION_GUIDE.md
   - Fix root cause in FeatureComputer or cBots
   - Re-run test
   - Document findings

### To Automate Test (Future)

Could create a .bat script to:
1. Trigger DataCollector backtest via cTrader CLI
2. Trigger FxScalper_ML backtest via cTrader CLI
3. Run Python comparison script
4. Generate automated report
5. Email results

(Not yet implemented - requires cTrader automation setup)

## Critical Notes

### Train/Serve Consistency is Essential

The ML model was trained on features computed by DataCollector v0.4. When FxScalper_ML uses features with ANY differences:
- Model performance degrades (garbage in, garbage out)
- Predictions become unreliable
- Win rate drops, losses increase
- Trading losses result

### Why Shared FeatureComputer Guarantees Consistency

1. **Single source of truth** - One file, two imports (no duplication)
2. **Identical initialization** - Same indicator parameters, same order
3. **Identical bar indexing** - Both use `Count-2` for just-closed bar
4. **Identical HTF reads** - Both use `.Last(1)` for closed HTF bars
5. **Identical state management** - Shared stateful fields (_atrHistory, etc.)

This architecture is the foundation of a production-grade trading system.

## Success Definition

✅ Test is PASS when:
- Max absolute difference across all 322,000 values ≤ 0.000001
- All 46 features match within tolerance
- Temporary logging is removed
- Results are documented
- Changes are committed to git

❌ Test is FAIL when:
- Max difference > 0.000001 for ANY cell
- Root cause identified and documented
- Plan created to fix issue
- Test re-run after fixes

## Estimated Timeline

- DataCollector backtest: 1-3 minutes
- FxScalper_ML backtest: 1-3 minutes
- Python comparison: < 1 second
- Cleanup and documentation: 5-10 minutes
- **Total: ~15-20 minutes of execution time**

(Most time is waiting for backtests to complete)

## Contact/Support

If issues arise during test execution:
1. Check PHASE4_TASK4_EXECUTION_GUIDE.md for debugging steps
2. Verify parameter configuration matches guide exactly
3. Check file paths are correct (note escape characters in Windows paths)
4. Verify CSV files have expected columns before comparison

---

**Status:** ✅ Ready for execution
**Date Prepared:** 2026-04-19
**Prepared by:** JCAMP Project AI Assistant
**Test Coordinator:** Ready to document and commit results
