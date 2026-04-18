"""
Configuration for the prediction service.
All feature names, model paths, and thresholds in one place.
"""

from pathlib import Path

# --- Paths ---
MODEL_DIR = Path(__file__).parent / "models"
LONG_MODEL_PATH = MODEL_DIR / "eurusd_long_v04_final_holdout.joblib"
DB_PATH = Path(__file__).parent / "prediction_log.db"

# --- Model version ---
MODEL_VERSION = "eurusd_long_v04_20260418"

# --- Feature list (EXACT order must match training) ---
# These are the 46 features in the order the model expects them.
# DO NOT reorder, rename, or remove any feature without retraining.
FEATURE_NAMES = [
    # Price vs SMAs (ATR-normalized)
    "dist_sma_m5_50",
    "dist_sma_m5_100",
    "dist_sma_m5_200",
    "dist_sma_m5_275",
    "dist_sma_m15_200",
    "dist_sma_m30_200",
    "dist_sma_h1_200",
    "dist_sma_h4_200",
    # SMA slopes
    "slope_sma_m5_200",
    "slope_sma_h1_200",
    # Momentum
    "rsi_m5",
    "rsi_m15",
    "rsi_m30",
    "adx_m5",
    "di_plus_m5",
    "di_minus_m5",
    # Volatility
    "atr_m5",
    "atr_m15",
    "atr_h1",
    "atr_ratio_m5_h1",
    "bb_width",
    # Recent bar shape (ATR-normalized)
    "bar0_body",
    "bar0_range",
    "bar1_body",
    "bar1_range",
    "bar2_body",
    "bar2_range",
    "bar3_body",
    "bar3_range",
    "bar4_body",
    "bar4_range",
    # Swing structure
    "dist_swing_high",
    "dist_swing_low",
    # Time / session
    "hour_utc",
    "dow",
    "sess_asia",
    "sess_london",
    "sess_ny",
    # Cost
    "spread_pips",
    # MTF alignment (v0.3)
    "mtf_alignment_score",
    "mtf_stacking_score",
    "bars_since_tf_fast_flip",
    "tf_fast_flip_direction",
    "mtf_alignment_duration",
    # Regime (v0.4)
    "atr_percentile_2000bar",
    "h1_alignment_agreement",
]

assert len(FEATURE_NAMES) == 46, f"Expected 46 features, got {len(FEATURE_NAMES)}"
