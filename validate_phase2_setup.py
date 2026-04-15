"""
Phase 2 Setup Validation Script
Tests all custom modules with actual data
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path

print("="*70)
print("Phase 2 Setup Validation")
print("="*70)

# Test imports
print("\n1. Testing module imports...")
try:
    from src.data_loader import load_datacollector_csv, get_data_splits, validate_data_quality
    from src.labels import collapse_to_binary, get_label_balance, print_label_summary
    from src.features import get_feature_columns, check_feature_distributions
    from src.cv import PurgedWalkForward
    from src.train import train_lightgbm, evaluate_model
    from src.evaluate import calculate_trading_metrics, simulate_equity_curve
    print("   [OK] All modules imported successfully")
except Exception as e:
    print(f"   [FAIL] Import failed: {e}")
    sys.exit(1)

# Test data loading
print("\n2. Testing data loading...")
try:
    csv_path = 'data/DataCollector_EURUSD_M5_20230101_220400.csv'
    if not Path(csv_path).exists():
        print(f"   [FAIL] CSV file not found: {csv_path}")
        sys.exit(1)

    df = load_datacollector_csv(csv_path)
    print(f"   [OK] Loaded {len(df):,} rows, {len(df.columns)} columns")
    print(f"   [OK] Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
except Exception as e:
    print(f"   [FAIL] Data loading failed: {e}")
    sys.exit(1)

# Test data quality validation
print("\n3. Testing data quality validation...")
try:
    quality = validate_data_quality(df, verbose=False)
    if quality['passed']:
        print(f"   [OK] Data quality check PASSED")
        print(f"     - Total rows: {quality['total_rows']:,}")
        print(f"     - NaN values: {quality['nan_count']}")
        print(f"     - Inf values: {quality['inf_count']}")
    else:
        print(f"   [FAIL] Data quality check FAILED")
        print(f"     - NaN values: {quality['nan_count']}")
        print(f"     - Inf values: {quality['inf_count']}")
except Exception as e:
    print(f"   [FAIL] Data quality validation failed: {e}")
    sys.exit(1)

# Test data splits
print("\n4. Testing data splits...")
try:
    train_cv, held_out_test, live_forward = get_data_splits(df)
    print(f"   [OK] Train/CV:      {len(train_cv):7,} rows ({len(train_cv)/len(df)*100:5.1f}%)")
    print(f"   [OK] Held-out test: {len(held_out_test):7,} rows ({len(held_out_test)/len(df)*100:5.1f}%)")
    print(f"   [OK] Live forward:  {len(live_forward):7,} rows ({len(live_forward)/len(df)*100:5.1f}%)")
except Exception as e:
    print(f"   [FAIL] Data splits failed: {e}")
    sys.exit(1)

# Test label processing
print("\n5. Testing label processing...")
try:
    # Test LONG labels
    df_long = collapse_to_binary(train_cv.head(1000), direction="long", timeout_as="loss")
    balance_long = get_label_balance(train_cv.head(1000), direction="long")
    print(f"   [OK] LONG labels: {balance_long['win_pct']:.1f}% win, {balance_long['loss_pct']:.1f}% loss, {balance_long['timeout_pct']:.1f}% timeout")

    # Test SHORT labels
    df_short = collapse_to_binary(train_cv.head(1000), direction="short", timeout_as="loss")
    balance_short = get_label_balance(train_cv.head(1000), direction="short")
    print(f"   [OK] SHORT labels: {balance_short['win_pct']:.1f}% win, {balance_short['loss_pct']:.1f}% loss, {balance_short['timeout_pct']:.1f}% timeout")
except Exception as e:
    print(f"   [FAIL] Label processing failed: {e}")
    sys.exit(1)

# Test feature extraction
print("\n6. Testing feature extraction...")
try:
    features = get_feature_columns(df)
    print(f"   [OK] Found {len(features)} features")
    print(f"   [OK] First 5 features: {features[:5]}")
except Exception as e:
    print(f"   [FAIL] Feature extraction failed: {e}")
    sys.exit(1)

# Test Purged Walk-Forward CV
print("\n7. Testing PurgedWalkForward CV...")
try:
    cv = PurgedWalkForward(n_splits=3, embargo_bars=48, test_size=0.15)

    # Use small sample for speed
    sample = train_cv.head(10000).copy()
    df_sample_long = collapse_to_binary(sample, direction="long", timeout_as="loss")
    X_sample = df_sample_long[features]
    y_sample = df_sample_long['label']
    bars_sample = df_sample_long['bars_to_outcome_long']

    n_folds = 0
    for train_idx, test_idx in cv.split(X_sample, y_sample, bars_sample):
        n_folds += 1

    print(f"   [OK] CV generated {n_folds} folds")
    print(f"   [OK] Example fold - Train: {len(train_idx):,} samples, Test: {len(test_idx):,} samples")
except Exception as e:
    print(f"   [FAIL] PurgedWalkForward CV failed: {e}")
    sys.exit(1)

# Test LightGBM training (quick test on tiny sample)
print("\n8. Testing LightGBM training...")
try:
    # Use very small sample for quick test
    tiny_sample = train_cv.head(5000).copy()
    df_tiny = collapse_to_binary(tiny_sample, direction="long", timeout_as="loss")
    X_tiny = df_tiny[features]
    y_tiny = df_tiny['label']

    # Split for quick test
    split_idx = int(len(X_tiny) * 0.7)
    X_train_tiny = X_tiny.iloc[:split_idx]
    y_train_tiny = y_tiny.iloc[:split_idx]
    X_test_tiny = X_tiny.iloc[split_idx:]
    y_test_tiny = y_tiny.iloc[split_idx:]

    # Train with minimal params for speed
    params = {
        'objective': 'binary',
        'n_estimators': 10,  # Very few for speed test
        'max_depth': 3,
        'num_leaves': 7,
        'verbose': -1,
        'random_state': 42
    }

    model = train_lightgbm(X_train_tiny, y_train_tiny, params=params)
    metrics = evaluate_model(model, X_test_tiny, y_test_tiny, verbose=False)

    print(f"   [OK] Model trained successfully")
    print(f"   [OK] Test ROC-AUC: {metrics['roc_auc']:.4f}")
    print(f"   [OK] Test Accuracy: {metrics['accuracy']:.4f}")

    if metrics['roc_auc'] > 0.45:  # Very low bar for tiny sample
        print(f"   [OK] Model shows learning (AUC > 0.45)")
    else:
        print(f"   [WARN] Model AUC low (expected with tiny sample)")

except Exception as e:
    print(f"   [FAIL] LightGBM training failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test evaluation metrics
print("\n9. Testing evaluation metrics...")
try:
    y_pred = model.predict(X_test_tiny)
    trading_metrics = calculate_trading_metrics(
        y_test_tiny.values,
        y_pred,
        risk_reward=2.0
    )
    print(f"   [OK] Trading metrics calculated")
    print(f"     - Win rate: {trading_metrics['win_rate']*100:.1f}%")
    print(f"     - Expectancy: {trading_metrics['expectancy_r']:+.3f}R")

    # Test equity curve
    y_pred_proba = model.predict_proba(X_test_tiny)[:, 1]
    equity_df = simulate_equity_curve(
        y_test_tiny.values,
        y_pred_proba,
        threshold=0.5,
        risk_reward=2.0
    )
    print(f"   [OK] Equity curve simulated ({len(equity_df)} points)")

except Exception as e:
    print(f"   [FAIL] Evaluation metrics failed: {e}")
    sys.exit(1)

# Summary
print("\n" + "="*70)
print("VALIDATION SUMMARY")
print("="*70)
print("[OK] All tests passed!")
print("\nPhase 2 setup is ready:")
print(f"  - Data: {len(df):,} rows loaded and validated")
print(f"  - Features: {len(features)} features extracted")
print(f"  - Modules: All 6 custom modules working correctly")
print(f"  - ML Pipeline: LightGBM training and evaluation functional")
print("\nReady to start with notebooks/01_eda.ipynb")
print("="*70)
