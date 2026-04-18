"""
Test script for the prediction service.
Tests all endpoints without needing to start the server in background.
"""

import sys
import json
import asyncio
from fastapi.testclient import TestClient
from app import app

# Test data - a real feature vector
test_features = {
    "dist_sma_m5_50": 0.42,
    "dist_sma_m5_100": 0.81,
    "dist_sma_m5_200": -1.58,
    "dist_sma_m5_275": -4.28,
    "dist_sma_m15_200": -3.43,
    "dist_sma_m30_200": 2.25,
    "dist_sma_h1_200": -4.80,
    "dist_sma_h4_200": 4.39,
    "slope_sma_m5_200": -0.000068,
    "slope_sma_h1_200": -0.000048,
    "rsi_m5": 41.84,
    "rsi_m15": 46.86,
    "rsi_m30": 42.68,
    "adx_m5": 20.96,
    "di_plus_m5": 17.90,
    "di_minus_m5": 21.53,
    "atr_m5": 0.000345,
    "atr_m15": 0.000471,
    "atr_h1": 0.002034,
    "atr_ratio_m5_h1": 0.170,
    "bb_width": 1.87,
    "bar0_body": -0.93,
    "bar0_range": 2.03,
    "bar1_body": 0.38,
    "bar1_range": 1.10,
    "bar2_body": 0.52,
    "bar2_range": 0.81,
    "bar3_body": 0.38,
    "bar3_range": 0.78,
    "bar4_body": 0.03,
    "bar4_range": 0.14,
    "dist_swing_high": 4.81,
    "dist_swing_low": 1.07,
    "hour_utc": 21.0,
    "dow": 3.0,
    "sess_asia": 0.0,
    "sess_london": 0.0,
    "sess_ny": 0.0,
    "spread_pips": 9.8,
    "mtf_alignment_score": -2.0,
    "mtf_stacking_score": 1.0,
    "bars_since_tf_fast_flip": 34.0,
    "tf_fast_flip_direction": -1.0,
    "mtf_alignment_duration": 0.0,
    "atr_percentile_2000bar": 0.553,
    "h1_alignment_agreement": 0.0
}


def run_tests():
    """Run all tests."""
    client = TestClient(app)

    print("\n" + "="*60)
    print("PHASE 3 - FASTAPI PREDICTION SERVICE TESTS")
    print("="*60 + "\n")

    passed = 0
    failed = 0

    # Test 1: Health check
    print("[TEST 1] GET /health")
    try:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["model_loaded"] == True
        assert data["model_version"] == "eurusd_long_v04_20260418"
        print("  Status:", data["status"])
        print("  Model loaded:", data["model_loaded"])
        print("  Model version:", data["model_version"])
        print("  PASSED [OK]\n")
        passed += 1
    except Exception as e:
        print(f"  FAILED: {e}\n")
        failed += 1

    # Test 2: Model info
    print("[TEST 2] GET /model_info")
    try:
        response = client.get("/model_info")
        assert response.status_code == 200
        data = response.json()
        assert data["n_features"] == 46
        assert len(data["feature_names"]) == 46
        assert data["threshold_recommendation"] == 0.65
        print(f"  Features: {data['n_features']}")
        print(f"  Model version: {data['model_version']}")
        print(f"  Threshold recommendation: {data['threshold_recommendation']}")
        print("  PASSED [OK]\n")
        passed += 1
    except Exception as e:
        print(f"  FAILED: {e}\n")
        failed += 1

    # Test 3: Prediction with valid features
    print("[TEST 3] POST /predict (valid request)")
    try:
        response = client.post(
            "/predict",
            json={
                "symbol": "EURUSD",
                "timestamp": "2026-04-18T14:35:00Z",
                "features": test_features
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "p_win_long" in data
        assert "model_version" in data
        assert "latency_ms" in data
        p_win = data["p_win_long"]
        assert 0.0 <= p_win <= 1.0, f"p_win_long out of range: {p_win}"
        print(f"  p_win_long: {p_win:.6f}")
        print(f"  Latency: {data['latency_ms']:.2f}ms")
        print(f"  Decision: {'TRADE' if p_win > 0.65 else 'SKIP'}")
        print("  PASSED [OK]\n")
        passed += 1
    except Exception as e:
        print(f"  FAILED: {e}\n")
        failed += 1

    # Test 4: Prediction with missing features
    print("[TEST 4] POST /predict (missing features - should fail)")
    try:
        bad_features = test_features.copy()
        del bad_features["dist_sma_m5_50"]  # Remove one feature
        response = client.post(
            "/predict",
            json={
                "symbol": "EURUSD",
                "timestamp": "2026-04-18T14:35:00Z",
                "features": bad_features
            }
        )
        assert response.status_code == 422  # Validation error
        print("  Correctly rejected missing feature")
        print("  PASSED [OK]\n")
        passed += 1
    except Exception as e:
        print(f"  FAILED: {e}\n")
        failed += 1

    # Test 5: Prediction with NaN value (should fail)
    print("[TEST 5] POST /predict (NaN value - should fail)")
    try:
        bad_features = test_features.copy()
        bad_features["dist_sma_m5_50"] = float('nan')
        response = client.post(
            "/predict",
            json={
                "symbol": "EURUSD",
                "timestamp": "2026-04-18T14:35:00Z",
                "features": bad_features
            }
        )
        assert response.status_code == 422  # Validation error
        print("  Correctly rejected NaN value")
        print("  PASSED [OK]\n")
        passed += 1
    except Exception as e:
        print(f"  FAILED: {e}\n")
        failed += 1

    # Test 6: Prediction log verification
    print("[TEST 6] Verify prediction log database")
    try:
        import sqlite3
        from pathlib import Path
        from config import DB_PATH

        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM prediction_log")
        count = cursor.fetchone()[0]
        conn.close()

        assert count > 0, "No predictions logged"
        print(f"  Predictions logged: {count}")
        print("  PASSED [OK]\n")
        passed += 1
    except Exception as e:
        print(f"  FAILED: {e}\n")
        failed += 1

    # Summary
    print("="*60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*60 + "\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
