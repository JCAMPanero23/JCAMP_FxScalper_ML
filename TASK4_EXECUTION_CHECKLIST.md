# Task 4: Feature Skew Test - Execution Checklist

**Quick Reference Guide**

## Pre-Test Checklist

- [ ] Read `PHASE4_TASK4_EXECUTION_GUIDE.md`
- [ ] Verify access to `C:\Users\Jcamp_Laptop\Documents\JCAMP_Data\`
- [ ] Verify cTrader Automate is available
- [ ] Verify Python 3.6+ with pandas installed
- [ ] Backup any existing CSVs in JCAMP_Data folder

## Part 1: DataCollector Backtest

- [ ] Open cTrader Automate
- [ ] Load file: `cbot/JCAMP_DataCollector.cs`
- [ ] Set parameters:
  - [ ] Symbol: EURUSD
  - [ ] Timeframe: M5
  - [ ] Start: 2024-01-01 00:00
  - [ ] End: 2024-01-31 23:59
  - [ ] Initial Balance: 10000 USD
  - [ ] Mode: Backtest
- [ ] Click "Start" or "Run"
- [ ] Wait for completion (1-3 minutes)
- [ ] Verify logs show:
  - [ ] "DataCollector started"
  - [ ] "DataCollector stopped"
- [ ] Note output CSV filename (format: `DataCollector_EURUSD_M5_20240101_*.csv`)
- [ ] Verify CSV exists in `C:\Users\Jcamp_Laptop\Documents\JCAMP_Data\`
- [ ] Verify CSV has:
  - [ ] ~7000 rows
  - [ ] Columns: timestamp, symbol, [46 features], outcome_long, outcome_short, etc.

## Part 2: FxScalper_ML Backtest

- [ ] Open cTrader Automate
- [ ] Load file: `cbot/JCAMP_FxScalper_ML/JCAMP_FxScalper_ML.cs`
- [ ] Set parameters:
  - [ ] Symbol: EURUSD
  - [ ] Timeframe: M5
  - [ ] Start: 2024-01-01 00:00
  - [ ] End: 2024-01-31 23:59
  - [ ] Initial Balance: 10000 USD
  - [ ] Mode: Backtest
- [ ] Verify cBot parameters:
  - [ ] ML Threshold: 0.65 (any value)
  - [ ] Enable Trading: **false** (CRITICAL!)
  - [ ] API URL: http://localhost:8000/predict
- [ ] Click "Start" or "Run"
- [ ] Wait for completion (1-3 minutes)
- [ ] Verify logs show:
  - [ ] "JCAMP FxScalper ML v1.0.0"
  - [ ] "Mode: SIMULATION"
  - [ ] "STOPPED"
- [ ] Verify CSV exists: `FxScalper_features_debug.csv`
- [ ] Verify CSV has:
  - [ ] ~7000 rows
  - [ ] 46 feature columns only
  - [ ] Header matches FEATURE_NAMES order

## Part 3: Run Comparison Script

- [ ] Open terminal/command prompt
- [ ] Navigate to: `.worktrees/phase4-cbot`
  ```bash
  cd D:\JCAMP_FxScalper_ML\.worktrees\phase4-cbot
  ```
- [ ] Run comparison:
  ```bash
  python compare_feature_skew.py ^
    "C:\Users\Jcamp_Laptop\Documents\JCAMP_Data\DataCollector_EURUSD_M5_20240101_*.csv" ^
    "C:\Users\Jcamp_Laptop\Documents\JCAMP_Data\FxScalper_features_debug.csv"
  ```
- [ ] Verify script output includes:
  - [ ] Both CSVs loaded successfully
  - [ ] Feature columns extracted
  - [ ] Comparison statistics (max, mean, median)
  - [ ] Result: PASS or FAIL

## Part 4a: If PASS

- [ ] Note the max absolute difference value
- [ ] Verify max difference ≤ 0.000001
- [ ] Remove temporary CSV logging code:
  - [ ] Remove `_csvDebug` field from FxScalper_ML.cs
  - [ ] Remove CSV initialization from OnStart()
  - [ ] Remove CSV logging from OnBar()
  - [ ] Remove CSV cleanup from OnStop()
  - [ ] Remove `using System.IO;` if no longer needed
- [ ] Update `PHASE4_SKEW_TEST_RESULT.md`:
  - [ ] Add "## Test Results (Executed)" section
  - [ ] Add date, test period, rows compared
  - [ ] Add max/mean/median differences
  - [ ] Add: "Status: PASS - Train/serve consistency VERIFIED"
- [ ] Commit changes:
  ```bash
  git add -A
  git commit -m "test: Phase 4 Task 4 feature skew test - PASS"
  ```
- [ ] Proceed to Task 5: FastAPI Configuration Verification

## Part 4b: If FAIL

- [ ] Note which features have differences > tolerance
- [ ] Note the max difference values
- [ ] Review debugging guide in `PHASE4_TASK4_EXECUTION_GUIDE.md`
- [ ] Identify root cause:
  - [ ] Check indicator initialization order
  - [ ] Check bar indexing (Count-2)
  - [ ] Check HTF bar selection (Last(1))
  - [ ] Check state management
  - [ ] Add debug prints to FeatureComputer
- [ ] Fix the root cause in code
- [ ] Update `PHASE4_SKEW_TEST_RESULT.md`:
  - [ ] Add "## Test Results (FAILED)" section
  - [ ] Document which features diverge
  - [ ] Document root cause analysis
  - [ ] Document fix applied
- [ ] Commit diagnostic work:
  ```bash
  git add -A
  git commit -m "test: Phase 4 Task 4 - Feature skew detected, root cause: [description]"
  ```
- [ ] Re-run backtests and comparison (return to Part 1)
- [ ] Continue until PASS achieved

## Post-Test Cleanup

- [ ] Remove temporary logging code from FxScalper_ML.cs (if PASS)
- [ ] Delete temporary CSV files (optional):
  - [ ] `DataCollector_EURUSD_M5_*.csv`
  - [ ] `FxScalper_features_debug.csv`
- [ ] Run final git status check:
  ```bash
  git status
  ```
  - [ ] Should show: "nothing to commit, working tree clean" (if PASS)

## Final Verification

- [ ] Review git log:
  ```bash
  git log --oneline -5
  ```
  - [ ] Should show recent commits with test results

- [ ] Verify all documentation updated:
  - [ ] `PHASE4_SKEW_TEST_RESULT.md` has results
  - [ ] Status matches actual test outcome

- [ ] Check files not left in "modified" state:
  ```bash
  git status
  ```
  - [ ] Should show clean state

## Success Criteria Met

- [ ] DataCollector backtest completed successfully
- [ ] FxScalper_ML backtest completed successfully
- [ ] Python comparison script executed
- [ ] Result: PASS (max diff ≤ 0.000001)
- [ ] Temporary code removed from FxScalper_ML
- [ ] Results documented in markdown
- [ ] All changes committed to git
- [ ] Ready to proceed to Task 5

## Troubleshooting Quick Links

| Issue | Solution |
|-------|----------|
| CSV not found | Check filename, verify backtest completed |
| Python script error | Verify pandas installed, check file paths |
| Feature mismatch | See debugging section in execution guide |
| Enable Trading not set | Backtest may have traded; re-run with EnableTrading=false |
| Wrong date range | Verify backtest config, re-run with Jan 1-31 2024 |

## Time Estimates

| Step | Estimated Time |
|------|-----------------|
| DataCollector backtest | 1-3 min |
| FxScalper_ML backtest | 1-3 min |
| Python comparison | < 1 min |
| Results documentation | 5-10 min |
| Code cleanup (if PASS) | 5 min |
| Git operations | 2-3 min |
| **Total** | **~20-25 min** |

## Resources

- **Execution Guide:** `PHASE4_TASK4_EXECUTION_GUIDE.md`
- **Status Report:** `TASK4_STATUS_REPORT.md`
- **Comparison Script:** `compare_feature_skew.py`
- **Results Template:** `PHASE4_SKEW_TEST_RESULT.md`
- **Preparation Summary:** `TASK4_PREPARATION_COMPLETE.md`

---

**Print this checklist for reference during test execution!**

Last Updated: 2026-04-19
Ready for: Backtest Execution Phase
