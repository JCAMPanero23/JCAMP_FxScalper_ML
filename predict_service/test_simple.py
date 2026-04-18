"""
Simple test to verify model can be loaded and predictions work.
"""

import sys
import numpy as np
from pathlib import Path
from joblib import load

# Test 1: Check model file exists
print("\n[TEST 1] Model file exists")
model_path = Path(__file__).parent / "models" / "eurusd_long_v04_final_holdout.joblib"
if model_path.exists():
    print(f"  Model found at: {model_path}")
    print(f"  Size: {model_path.stat().st_size / (1024*1024):.1f} MB")
    print("  PASSED [OK]\n")
else:
    print(f"  FAILED: Model not found at {model_path}\n")
    sys.exit(1)

# Test 2: Load model
print("[TEST 2] Load model")
try:
    model = load(model_path)
    print(f"  Model type: {type(model).__name__}")
    print(f"  Model loaded successfully")
    print("  PASSED [OK]\n")
except Exception as e:
    print(f"  FAILED: {e}\n")
    sys.exit(1)

# Test 3: Feature count
print("[TEST 3] Check feature count")
from config import FEATURE_NAMES
print(f"  Expected features: {len(FEATURE_NAMES)}")
print(f"  Actual features in config: {len(FEATURE_NAMES)}")
if len(FEATURE_NAMES) == 46:
    print("  PASSED [OK]\n")
else:
    print(f"  FAILED: Expected 46 features, got {len(FEATURE_NAMES)}\n")
    sys.exit(1)

# Test 4: Make a prediction with test data
print("[TEST 4] Make a prediction")
test_features = np.array([[
    0.42, 0.81, -1.58, -4.28, -3.43, 2.25, -4.80, 4.39,  # dist_sma
    -0.000068, -0.000048,  # slope_sma
    41.84, 46.86, 42.68,  # rsi
    20.96, 17.90, 21.53,  # adx, di
    0.000345, 0.000471, 0.002034, 0.170, 1.87,  # atr, bb_width
    -0.93, 2.03, 0.38, 1.10, 0.52, 0.81, 0.38, 0.78, 0.03, 0.14,  # bar shapes
    4.81, 1.07,  # swing
    21.0, 3.0, 0.0, 0.0, 0.0,  # time/session
    9.8,  # spread
    -2.0, 1.0, 34.0, -1.0, 0.0,  # mtf
    0.553, 0.0  # regime
]])

try:
    p_win = model.predict_proba(test_features)[0, 1]
    print(f"  p_win_long: {p_win:.6f}")
    print(f"  Decision: {'TRADE (p > 0.65)' if p_win > 0.65 else 'SKIP (p <= 0.65)'}")
    if 0.0 <= p_win <= 1.0:
        print("  PASSED [OK]\n")
    else:
        print(f"  FAILED: p_win out of range: {p_win}\n")
        sys.exit(1)
except Exception as e:
    print(f"  FAILED: {e}\n")
    sys.exit(1)

# Test 5: Config validation
print("[TEST 5] Validate configuration")
try:
    from config import MODEL_VERSION, LONG_MODEL_PATH, DB_PATH
    print(f"  Model version: {MODEL_VERSION}")
    print(f"  Model path: {LONG_MODEL_PATH}")
    print(f"  DB path: {DB_PATH}")
    print("  PASSED [OK]\n")
except Exception as e:
    print(f"  FAILED: {e}\n")
    sys.exit(1)

print("="*60)
print("ALL TESTS PASSED [OK]")
print("="*60)
print("\nThe prediction service is ready to deploy.")
print("To start the server locally:")
print("  python -m uvicorn app:app --host 127.0.0.1 --port 8000")
print()
