# V0.4 Implementation Plan — Steps 3-7 Execution Guide

**Status:** Ready for execution
**Date:** 2026-04-18
**Phase:** Phase 2, Branch C (Feature Engineering)

---

## Overview

This document guides execution of Steps 3-7 from `DataCollector_v0.4_patch.md`:

- **Step 3:** Smoke test (Jan 2023 only)
- **Step 4:** Full historical run (Jan 2023 → present)
- **Step 5:** Walk-forward CV analysis
- **Step 6:** Gate decision
- **Step 7:** Documentation update

**Current State:**
- ✅ v0.4 code is complete and compiled in `cbot/JCAMP_DataCollector.cs`
- ✅ Python script ready: `run_v04_walk_forward.py`
- ✅ CV parameter alignment resolved: n_splits=6, test_size=0.15, embargo_bars=48
- ⏳ v0.4 dataset pending (needs DataCollector execution in cTrader)

---

## Steps 3-4: Run DataCollector in cTrader (MANUAL)

### Prerequisites

1. **cTrader Platform** with cAlgo installed
2. **EURUSD M5 chart** open
3. **Live/Demo account** connected

### Step 3: Smoke Test (Jan 2023 Only)

This verifies the new features work correctly before running full history.

```
1. In cTrader:
   - Open EURUSD M5 chart
   - Set date range to Jan 2023 only
   - Add DataCollector robot (cbot/JCAMP_DataCollector.cs)
   - Compile (should succeed with no errors)
   - Start on demo account for 1-2 hours

2. Expected output:
   - CSV file created in: C:\Users\Jcamp_Laptop\Documents\JCAMP_Data\
   - ~8,000-10,000 rows (depends on exact date range)
   - Column count: 46 (was 44 in v0.3)

3. Verify features:
   - atr_percentile_2000bar: values 0.0-1.0 (not all 0.5)
   - h1_alignment_agreement: only values {-1, 0, +1}
   - No NaN/Inf in either column
   - Existing columns unchanged vs v0.3

4. Save as: backup_jan_2023_smoke_test.csv
```

### Step 4: Full Historical Run (Jan 2023 → Present)

Once smoke test passes, run on full date range.

```
1. In cTrader:
   - Set date range: Jan 1, 2023 → Apr 18, 2026 (or latest)
   - Start DataCollector robot on demo account
   - Let run to completion (may take 1-2 hours depending on broker speed)

2. Expected output:
   - CSV file: DataCollector_EURUSD_M5_YYYYMMDD_HHMMSS.csv
   - ~244,000+ rows (same as v0.3, just with 2 new columns)
   - Column count: 46

3. Move to: data/ folder
   - Rename if needed, or keep latest as-is
   - Script automatically finds most recent CSV

4. Verify statistics:
   Run this in Python:

   ```python
   import pandas as pd
   df = pd.read_csv("data/DataCollector_EURUSD_M5_YYYYMMDD_HHMMSS.csv",
                    parse_dates=['timestamp'])
   print(df.shape)                    # Should be (244k+, 46)
   print(df['atr_percentile_2000bar'].describe())  # mean ~0.5
   print(df['h1_alignment_agreement'].unique())    # should be [-1, 0, 1]
   ```
```

---

## Step 5: Run Walk-Forward CV

Once v0.4 data is in `data/` folder, run the Python script.

### Command

```bash
python run_v04_walk_forward.py
```

### What It Does

1. **Loads v0.4 data** (most recent DataCollector CSV)
2. **Verifies v0.4 features** are present (atr_percentile_2000bar, h1_alignment_agreement)
3. **Runs walk-forward CV** using canonical parameters:
   - n_splits=6 (produces 5 usable folds)
   - test_size=0.15
   - embargo_bars=48
4. **Tests thresholds:** 0.55, 0.60, 0.65
5. **For each fold:** trains LightGBM, predicts, evaluates
6. **Saves results to:**
   - `outputs/phase2_v04_results/v04_walk_forward_results.md` (formatted report)
   - `outputs/phase2_v04_results/v04_fold_results.csv` (detailed data)

### Expected Duration

- ~10-15 minutes (5 folds × 2 directions × 3 thresholds = 30 model trains)

### Expected Output Structure

```
# Phase 2 v0.4 Walk-Forward CV Results

## Summary Results

| Direction | Threshold | Positive Folds | Mean Expectancy | ... |
|-----------|-----------|-----------------|-----------------|-----|
| LONG      | 0.55      | 4/5 (80%)       | +0.087R         | ... |
| LONG      | 0.60      | 4/5 (80%)       | +0.095R         | ... |
| ...       | ...       | ...             | ...             | ... |

## Fold-by-Fold Details

### LONG Model
#### Threshold 0.55
| Fold | Test Start | Test End | Accuracy | Precision | Recall | F1 | Mean Exp |
| ... | ... | ... | ... | ... | ... | ... | ... |

## Gate Decision

**Gate:** [A / B / C]
**Reasoning:**
- [reasons]

**Next Action:** [action]

## Comparison with v0.3
[table comparing v0.3 vs v0.4 metrics]
```

---

## Step 6: Interpret Results & Make Gate Decision

### Gate A — Proceed to Holdout (Best Case)

**Criteria (ALL must be met at ONE threshold):**

| Criterion | LONG | SHORT |
|-----------|------|-------|
| Positive folds | ≥ 4/5 (80%) | ≥ 3/5 (60%) |
| Mean expectancy | ≥ +0.09R | ≥ +0.09R |
| Worst fold expectancy | ≥ -0.15R | ≥ -0.15R |
| Avg trades per fold | ≥ 80 | ≥ 80 |

**If Gate A is met:**
```
1. Run on holdout set (Oct 2025 - Mar 2026) ONCE
2. Compare holdout performance vs CV estimates
3. If holdout ±30% of CV → proceed to Phase 3 (FastAPI)
4. If holdout diverges >30% → return to diagnosis
```

### Gate B — Pivot to Meta-Gating (Middle Case)

**Trigger:** Improved but not Gate A

Examples:
- Mean expectancy +0.013R → +0.08R (improved, but <+0.09R threshold)
- Fold consistency 3/5 → 4/5 (improved, but LONG still <4/5)
- Only SHORT passes but LONG doesn't

**If Gate B:**
```
1. Train separate binary classifier for "regime quality"
2. Labels: folds where model was profitable = "good", losses = "bad"
3. Gating model learns to classify CURRENT regime
4. Combined rule: base_model_win > threshold AND gating_model_good = 1
5. ONE experiment only
6. If still doesn't clear Gate A → proceed to Gate C
```

### Gate C — Pivot Away (Last Resort)

**Trigger:** No meaningful improvement or Gate B fails

"Meaningful improvement" = mean expectancy change ≥ +0.01R for both directions
AND fold consistency maintained or improved.

**If Gate C:**

Choose ONE of these pivots:

| Option | Description | Effort |
|--------|-------------|--------|
| **C1: M15 Timeframe** | Re-run DataCollector on M15 bars. Completely different feature space. New Phase 2. | High |
| **C2: ML for Exits** | Keep v4.5.x rule entries. Train ML for exit timing instead. Different labels. | Medium |
| **C3: GBPUSD Pair** | More volatile. Same M5 pipeline, different pair. New DataCollector. | Medium |
| **C4: Honest Abandon** | ML doesn't add enough complexity vs benefit. Archive cleanly. | Low |

**Do NOT pre-commit** to a pivot direction. Evaluate results first.

---

## Step 7: Update Documentation

### Update STATUS.md

Add new section after "CV Parameter Alignment":

```markdown
## Phase 2 v0.4 Results (2026-04-18)

**Patch Applied:** atr_percentile_2000bar + h1_alignment_agreement (2 regime features)
**Feature Count:** 44 → 46
**Dataset:** v0.4 (Jan 2023 - present)

### Walk-Forward CV Results

**LONG Model (Threshold 0.55):**
- Positive folds: X/5 (YY%)
- Mean expectancy: +Z.ZZZR
- Worst fold: -Z.ZZZR
- Improvement vs v0.3: +/- Z.ZZZR

**SHORT Model (Threshold 0.55):**
- Positive folds: X/5 (YY%)
- Mean expectancy: +Z.ZZZR
- Worst fold: -Z.ZZZR
- Improvement vs v0.3: +/- Z.ZZZR

### Gate Decision: [A / B / C]

**Reasoning:** [decision details]

**Next Step:** [action]
```

### Create PHASE2_V04_RESULTS.md

Auto-generated by `run_v04_walk_forward.py`. Contains:
- Summary table (all thresholds × directions)
- Fold-by-fold details
- Gate decision and reasoning
- Comparison vs v0.3

### Commit Changes

```bash
git add STATUS.md PHASE2_V04_RESULTS.md outputs/phase2_v04_results/
git commit -m "v0.4 walk-forward CV complete: [GATE A/B/C decision]"
git push origin main
```

---

## Execution Timeline

| Step | Who | Tool | Duration | Blockers |
|------|-----|------|----------|----------|
| 3 | You | cTrader | 1-2 hrs | Broker connection |
| 4 | You | cTrader | 1-2 hrs | Broker connection |
| 5 | Claude Code | Python | 10-15 min | v0.4 data file |
| 6 | You | Analysis | 30 min | Results interpretation |
| 7 | Claude Code | Python/Git | 5 min | Results ready |

---

## Success Criteria

- [ ] v0.4 CSV generated (46 columns, 244k+ rows)
- [ ] Smoke test passed (atr_percentile, h1_alignment_agreement correct)
- [ ] run_v04_walk_forward.py executed without errors
- [ ] PHASE2_V04_RESULTS.md generated and reviewed
- [ ] Gate decision made (A, B, or C)
- [ ] STATUS.md updated with results
- [ ] Changes committed to git

---

## If Something Goes Wrong

### DataCollector won't compile
- Check C# syntax in JCAMP_DataCollector.cs (lines 106-109, 353-400)
- Verify cAlgo API version matches
- Check for typos in feature names (atr_percentile_2000bar, h1_alignment_agreement)

### v0.4 features are all 0s or NaNs
- Check: does _atrHistory have data? (needs 50+ bars warmup)
- Check: are alignScore and h1Slope computed before being used?
- Look at line 388-400 in ComputeFeatures for logic flow

### run_v04_walk_forward.py fails to load data
- Verify CSV path: should auto-detect in data/ folder
- Check column names match: timestamp, label, feature columns
- Run: `python -c "import pandas as pd; df = pd.read_csv('data/DataCollector_*.csv'); print(df.shape)"`

### Results seem too good (Gate A immediately)
- This is possible! v0.4 features were diagnosis-driven
- Double-check: are metrics calculated consistently with v0.3?
- Compare against v0.3 at same threshold in same fold
- If real improvement, proceed to holdout validation

---

## Next Phase (Post-Decision)

### If Gate A → Phase 3 (FastAPI)
- Deploy model as REST API
- Create live trading wrapper
- Test on holdout set first

### If Gate B → Meta-Gating Experiment
- Design gating model (separate notebook)
- ONE iteration only
- Evaluate result against Gate A
- If yes → Phase 3; if no → Gate C decision

### If Gate C → Choose Pivot
- Document lessons learned
- Archive current work cleanly
- Start next direction (M15, exits, GBPUSD, or abandon)

---

## Notes

- The iteration budget is non-negotiable: **Maximum 2 remaining experiments** (v0.4 + optional meta-gating)
- Holdout set remains untouched: **exactly 1 touch at the end**
- Results must be reproducible: save all intermediate CSVs and configs
- Decision discipline: no "just one more tweak" after Gate C
