# Phase 4 Task 4: Feature Skew Test - START HERE

**Status:** ✅ READY FOR EXECUTION
**Date:** 2026-04-19
**Time:** ~20-25 minutes to execute

## Quick Start

This task verifies that **DataCollector** and **FxScalper_ML** compute **IDENTICAL features**.

### What Was Done

1. ✅ FxScalper_ML enhanced with temporary CSV logging (16 lines of code)
2. ✅ Python comparison script created (`compare_feature_skew.py`)
3. ✅ Comprehensive execution guide written
4. ✅ Quick reference checklist created
5. ✅ All changes committed to git

### How to Execute (3 Steps)

**STEP 1:** Run DataCollector backtest on Jan 2024
- Open cTrader → Load JCAMP_DataCollector.cs
- Config: EURUSD, M5, Jan 1-31 2024
- Run backtest (~2 min)

**STEP 2:** Run FxScalper_ML backtest on Jan 2024
- Open cTrader → Load JCAMP_FxScalper_ML.cs
- Config: EURUSD, M5, Jan 1-31 2024, **EnableTrading=false**
- Run backtest (~2 min)

**STEP 3:** Run Python comparison script
```bash
cd D:\JCAMP_FxScalper_ML\.worktrees\phase4-cbot
python compare_feature_skew.py \
  "C:\Users\Jcamp_Laptop\Documents\JCAMP_Data\DataCollector_EURUSD_M5_20240101_*.csv" \
  "C:\Users\Jcamp_Laptop\Documents\JCAMP_Data\FxScalper_features_debug.csv"
```

### Expected Result

```
STATUS: ✅ PASS - Features are identical within tolerance!

Max absolute difference: 0.000000000000000e+00
Tolerance:             1.000000000000000e-06

→ Train/serve consistency VERIFIED
→ Safe to proceed to Task 5
```

## Documentation Index

| Document | Purpose | Time to Read |
|----------|---------|--------------|
| **TASK4_EXECUTION_CHECKLIST.md** | Quick reference (print this!) | 2 min |
| **PHASE4_TASK4_EXECUTION_GUIDE.md** | Complete procedures | 10 min |
| **TASK4_STATUS_REPORT.md** | Detailed status | 10 min |
| **TASK4_FINAL_SUMMARY.txt** | One-page summary | 5 min |

## Files Created

- `compare_feature_skew.py` - Python comparison script
- `PHASE4_TASK4_EXECUTION_GUIDE.md` - Step-by-step guide
- `TASK4_EXECUTION_CHECKLIST.md` - Printable checklist
- `TASK4_STATUS_REPORT.md` - Detailed status
- `TASK4_PREPARATION_COMPLETE.md` - Preparation summary
- `TASK4_FINAL_SUMMARY.txt` - One-page summary

## Files Modified

- `cbot/JCAMP_FxScalper_ML/JCAMP_FxScalper_ML.cs` - Added CSV logging (16 lines)
- `PHASE4_SKEW_TEST_RESULT.md` - Updated status

## Why This Matters

The ML model was trained on DataCollector features. If FxScalper_ML uses different features, the model will fail.

The shared FeatureComputer module guarantees consistency:
- Single source of truth (one file, two imports)
- Identical computation when used by both
- Test verifies this works

## Next Steps After PASS

1. Remove temporary CSV logging code from FxScalper_ML
2. Commit results to git
3. Proceed to Task 5: FastAPI Configuration Verification

## Critical Checklist

Before running tests:
- [ ] EnableTrading = false in FxScalper_ML backtest
- [ ] Use Jan 1-31, 2024 for both backtests
- [ ] Use M5 timeframe
- [ ] Use EURUSD symbol

## Get Started

1. **Print this:** `TASK4_EXECUTION_CHECKLIST.md`
2. **Read this:** `PHASE4_TASK4_EXECUTION_GUIDE.md`
3. **Execute:** Follow the checklist
4. **Document:** Update `PHASE4_SKEW_TEST_RESULT.md`

---

**Time to completion:** ~20-25 minutes (mostly waiting for backtests)

**Expected outcome:** PASS (max difference = 0.000000)

**Status:** ✅ Ready for execution
