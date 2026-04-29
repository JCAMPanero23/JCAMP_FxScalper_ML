"""
Configuration for the prediction service.
All feature names, model paths, and thresholds in one place.

v0.6.1 deploy: 49 features, both LONG and SHORT models.
SHORT runs in shadow mode by default (cBot decides whether to act on
p_win_short via the EnableShortTrading parameter).
"""

from pathlib import Path

# --- Paths ---
MODEL_DIR = Path(__file__).parent / "models"
LONG_MODEL_PATH = MODEL_DIR / "eurusd_long_v061.joblib"
SHORT_MODEL_PATH = MODEL_DIR / "eurusd_short_v061.joblib"
DB_PATH = Path(__file__).parent / "prediction_log.db"

# --- Model version ---
MODEL_VERSION = "eurusd_v061_20260429"

# --- Threshold recommendations (cBot can override) ---
LONG_THRESHOLD = 0.65
SHORT_THRESHOLD = 0.55

# --- Feature list (EXACT order must match training) ---
# 49 features, order must match LightGBM feature_name_ in both joblibs.
# Verified: LONG and SHORT v0.6.1 have identical feature ordering.
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
    # SMA slopes (v0.6.1 added slope_sma_h4_200)
    "slope_sma_m5_200",
    "slope_sma_h1_200",
    "slope_sma_h4_200",
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
    # MTF alignment
    "mtf_alignment_score",
    "mtf_stacking_score",
    "bars_since_tf_fast_flip",
    "tf_fast_flip_direction",
    "mtf_alignment_duration",
    # Regime
    "atr_percentile_2000bar",
    "h1_alignment_agreement",
    # v0.6.1 H4 regime additions
    "mtf_with_h4_score",
    "h4_alignment_duration",
]

assert len(FEATURE_NAMES) == 49, f"Expected 49 features, got {len(FEATURE_NAMES)}"
