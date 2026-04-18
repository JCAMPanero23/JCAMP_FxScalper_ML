# CV Parameter Alignment — Diagnostic Task for Claude Code

**Priority:** BLOCKING — resolve this before running v0.4 walk-forward CV
**Time estimate:** 15-30 minutes
**Date:** 2026-04-18

---

## The Problem

The fold verification (Task 1) produced **4 folds**, but the v0.3 walk-forward
experiment (PHASE2_MTF_EXPERIMENT.md) reported **5 folds** with results. The
parameters don't match, which means the v0.4 evaluation won't be comparable
to v0.3 unless we use the same splitter config.

### Evidence of Mismatch

**Verification notebook (05_fold_verification.ipynb):**
- Config: `PurgedWalkForward(n_splits=5, test_size=0.15, embargo_bars=48)`
- Result: 4 folds, each ~6,143 bars (~1 month)
- Fold 4 ends Apr 2025

**v0.3 experiment (PHASE2_MTF_EXPERIMENT.md):**
- Result: 5 folds with performance data
- Fold 5 existed and had results (LONG: good, SHORT: bad)
- Fold date ranges don't match verification output

**STATUS.md historical note:**
- "Fold 6 Missing" — originally tried n_splits=6, got 5 usable folds
- This suggests the experiment may have used n_splits=6, not n_splits=5

---

## Step 1: Find the Exact Parameters Used in the v0.3 Experiment

Search these files for the PurgedWalkForward instantiation that produced
the 5-fold results:

```
Files to check (in order of likelihood):
1. phase2_multi_threshold_experiment.py
2. notebooks/03_walk_forward.ipynb
3. Any .py file that imports PurgedWalkForward
4. Any notebook that calls PurgedWalkForward
```

### What to look for

```python
# Look for lines like:
cv = PurgedWalkForward(n_splits=???, test_size=???, embargo_bars=???)
# or
splitter = PurgedWalkForward(n_splits=???, ...)
# or
from src.cv import PurgedWalkForward
```

### Run this search command:

```bash
# Find all PurgedWalkForward instantiations in the project
grep -rn "PurgedWalkForward(" --include="*.py" --include="*.ipynb" .

# Also check for any hardcoded n_splits values
grep -rn "n_splits" --include="*.py" --include="*.ipynb" .
```

Record the EXACT parameters found. There may be multiple instantiations
with different parameters — document ALL of them.

---

## Step 2: Reproduce the 5-Fold Split

Once you find the parameters, run this diagnostic:

```python
import pandas as pd
from src.cv import PurgedWalkForward

# Load data
df = pd.read_csv("data/DataCollector_EURUSD_M5_20230101_220400.csv",
                 parse_dates=['timestamp'])
df = df.sort_values('timestamp').reset_index(drop=True)

# Filter to train/CV window
train_cv_end = pd.Timestamp('2025-09-30 23:59:59')
df_cv = df[df.timestamp <= train_cv_end].reset_index(drop=True)

print(f"Total train/CV rows: {len(df_cv):,}")
print()

# ============================================================
# TRY THE PARAMETERS FROM THE EXPERIMENT (fill these in)
# ============================================================
# Replace ??? with actual values found in Step 1
EXPERIMENT_N_SPLITS = ???
EXPERIMENT_TEST_SIZE = ???
EXPERIMENT_EMBARGO = ???

cv = PurgedWalkForward(
    n_splits=EXPERIMENT_N_SPLITS,
    test_size=EXPERIMENT_TEST_SIZE,
    embargo_bars=EXPERIMENT_EMBARGO
)

print(f"Config: n_splits={EXPERIMENT_N_SPLITS}, "
      f"test_size={EXPERIMENT_TEST_SIZE}, "
      f"embargo_bars={EXPERIMENT_EMBARGO}")
print("=" * 70)

fold_count = 0
for fold_num, (train_idx, test_idx) in enumerate(cv.split(df_cv), 1):
    fold_count += 1
    test_start = df_cv.timestamp.iloc[test_idx[0]]
    test_end   = df_cv.timestamp.iloc[test_idx[-1]]
    months = (test_end - test_start).days / 30.44
    print(f"Fold {fold_num}: train={len(train_idx):>7,}  "
          f"test={len(test_idx):>6,}  "
          f"period={test_start.date()} → {test_end.date()} "
          f"({months:.1f} months)")

print(f"\nTotal folds produced: {fold_count}")

if fold_count == 5:
    print("✅ MATCHES v0.3 experiment (5 folds). Use these parameters for v0.4.")
elif fold_count == 4:
    print("❌ Still only 4 folds. Try n_splits=6 next.")
else:
    print(f"⚠️  Unexpected fold count: {fold_count}. Investigate further.")
```

### If Step 1 doesn't find the exact params, try these combinations:

```python
# Try each of these until one produces exactly 5 folds:
configs_to_try = [
    {'n_splits': 6, 'test_size': 0.15, 'embargo_bars': 48},
    {'n_splits': 5, 'test_size': 0.12, 'embargo_bars': 48},
    {'n_splits': 6, 'test_size': 0.12, 'embargo_bars': 48},
    {'n_splits': 5, 'test_size': 0.10, 'embargo_bars': 48},
]

for cfg in configs_to_try:
    cv = PurgedWalkForward(**cfg)
    folds = list(cv.split(df_cv))
    n = len(folds)
    print(f"n_splits={cfg['n_splits']}, test_size={cfg['test_size']}, "
          f"embargo={cfg['embargo_bars']} → {n} folds")
    if n == 5:
        print("  ^^^ THIS ONE MATCHES. Use these parameters.")
        # Print fold boundaries
        for i, (train_idx, test_idx) in enumerate(folds, 1):
            ts = df_cv.timestamp.iloc[test_idx[0]].date()
            te = df_cv.timestamp.iloc[test_idx[-1]].date()
            print(f"  Fold {i}: {ts} → {te} ({len(test_idx):,} bars)")
        break
```

---

## Step 3: Document the Resolution

Once you find the config that produces 5 folds, update STATUS.md:

```markdown
## CV Parameter Alignment (Resolved 2026-04-18)

**Issue:** Fold verification used n_splits=5 and got 4 folds. v0.3 experiment
produced 5 folds. Parameters didn't match.

**Resolution:** The v0.3 experiment used:
- n_splits = [ACTUAL VALUE]
- test_size = [ACTUAL VALUE]
- embargo_bars = [ACTUAL VALUE]

**Fold boundaries (canonical, used for all future comparisons):**
| Fold | Test Start | Test End | Test Rows |
|------|------------|----------|-----------|
| 1    | ...        | ...      | ...       |
| 2    | ...        | ...      | ...       |
| 3    | ...        | ...      | ...       |
| 4    | ...        | ...      | ...       |
| 5    | ...        | ...      | ...       |

**Action:** All v0.4 walk-forward evaluations will use these exact parameters.
```

---

## Step 4: Proceed with v0.4 Walk-Forward

Once the parameters are locked down, proceed with the v0.4 evaluation using
the checklist from DataCollector_v0.4_patch.md (Steps 3-7):

1. Smoke test v0.4 DataCollector on Jan 2023
2. Full historical run
3. Walk-forward CV using the CORRECT parameters from this diagnostic
4. Evaluate against Gate A / B / C
5. Document results

---

## Success Criteria for This Task

- [ ] Found the exact PurgedWalkForward parameters used in the v0.3 experiment
- [ ] Reproduced exactly 5 folds with those parameters
- [ ] Fold boundaries documented in STATUS.md
- [ ] v0.4 walk-forward CV configured to use the same parameters
- [ ] Any discrepancy between verification and experiment is explained
