"""
Reproduce the exact fold split used in v0.3 experiment
"""
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
# v0.3 EXPERIMENT PARAMETERS (from phase2_multi_threshold_experiment.py)
# ============================================================
EXPERIMENT_N_SPLITS = 6
EXPERIMENT_TEST_SIZE = 0.15
EXPERIMENT_EMBARGO = 48

cv = PurgedWalkForward(
    n_splits=EXPERIMENT_N_SPLITS,
    test_size=EXPERIMENT_TEST_SIZE,
    embargo_bars=EXPERIMENT_EMBARGO
)

print(f"Config: n_splits={EXPERIMENT_N_SPLITS}, "
      f"test_size={EXPERIMENT_TEST_SIZE}, "
      f"embargo_bars={EXPERIMENT_EMBARGO}")
print("=" * 80)

fold_count = 0
fold_data = []
for fold_num, (train_idx, test_idx) in enumerate(cv.split(df_cv), 1):
    fold_count += 1
    test_start = df_cv.timestamp.iloc[test_idx[0]]
    test_end   = df_cv.timestamp.iloc[test_idx[-1]]
    months = (test_end - test_start).days / 30.44

    fold_info = {
        'fold': fold_num,
        'test_start': test_start.date(),
        'test_end': test_end.date(),
        'test_rows': len(test_idx),
        'train_rows': len(train_idx),
        'months': f'{months:.1f}'
    }
    fold_data.append(fold_info)

    print(f"Fold {fold_num}: train={len(train_idx):>7,}  "
          f"test={len(test_idx):>6,}  "
          f"period={test_start.date()} -> {test_end.date()} "
          f"({months:.1f} months)")

print(f"\nTotal folds produced: {fold_count}")

if fold_count == 5:
    print("[OK] MATCHES v0.3 experiment (5 folds). Use these parameters for v0.4.")
elif fold_count == 4:
    print("[FAIL] Still only 4 folds. Try n_splits=6 next.")
else:
    print(f"[WARN] Unexpected fold count: {fold_count}. Investigate further.")

# Output fold table
print("\n" + "=" * 80)
print("FOLD BOUNDARIES TABLE (for documentation)")
print("=" * 80)
print("| Fold | Test Start | Test End   | Test Rows |")
print("|------|------------|------------|-----------|")
for fold in fold_data:
    print(f"| {fold['fold']}    | {fold['test_start']} | {fold['test_end']} | {fold['test_rows']:>9} |")
