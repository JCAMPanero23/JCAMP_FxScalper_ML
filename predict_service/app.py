"""
JCAMP FxScalper ML — Prediction Service
========================================

FastAPI service that loads the trained LightGBM model and serves
predictions on POST /predict.

Runs on localhost:8000 on the VPS alongside cTrader.
"""

import time
import math
import sqlite3
import logging
import json
from datetime import datetime, timezone
from pathlib import Path
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from joblib import load

from config import (
    FEATURE_NAMES,
    LONG_MODEL_PATH,
    MODEL_VERSION,
    DB_PATH,
)

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("predict_service")

# --- Global state ---
long_model = None
start_time = None
request_count = 0


# --- Database setup ---
def init_db():
    """Create prediction log table if it doesn't exist."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prediction_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            bar_timestamp TEXT,
            p_win_long REAL NOT NULL,
            model_version TEXT NOT NULL,
            latency_ms REAL NOT NULL,
            features_json TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pred_timestamp
        ON prediction_log(timestamp)
    """)
    conn.commit()
    conn.close()
    logger.info(f"Prediction log database ready at {DB_PATH}")


def log_prediction(symbol: str, bar_timestamp: str, p_win_long: float,
                   latency_ms: float, features_json: str):
    """Log a prediction to SQLite. Non-blocking best-effort."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            """INSERT INTO prediction_log
               (timestamp, symbol, bar_timestamp, p_win_long,
                model_version, latency_ms, features_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                symbol,
                bar_timestamp,
                p_win_long,
                MODEL_VERSION,
                latency_ms,
                features_json,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to log prediction: {e}")


# --- Startup / shutdown ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model on startup, cleanup on shutdown."""
    global long_model, start_time

    logger.info("="*60)
    logger.info("JCAMP FxScalper ML — Prediction Service Starting")
    logger.info("="*60)

    # Load model
    if not LONG_MODEL_PATH.exists():
        logger.error(f"Model file not found: {LONG_MODEL_PATH}")
        raise FileNotFoundError(f"Model file not found: {LONG_MODEL_PATH}")

    long_model = load(LONG_MODEL_PATH)
    logger.info(f"Loaded LONG model from {LONG_MODEL_PATH}")
    logger.info(f"Model version: {MODEL_VERSION}")
    logger.info(f"Expected features: {len(FEATURE_NAMES)}")

    # Init database
    init_db()

    start_time = datetime.now(timezone.utc)
    logger.info("Service ready. Listening on http://localhost:8000")

    yield  # App runs here

    logger.info("Service shutting down.")


# --- FastAPI app ---
app = FastAPI(
    title="JCAMP FxScalper ML",
    version=MODEL_VERSION,
    lifespan=lifespan,
)


# --- Request / Response schemas ---
class PredictRequest(BaseModel):
    symbol: str
    timestamp: str = ""
    features: dict[str, float]

    @field_validator("features")
    @classmethod
    def validate_features(cls, v):
        # Check all required features are present
        missing = [f for f in FEATURE_NAMES if f not in v]
        if missing:
            raise ValueError(f"Missing features: {missing}")

        # Check for NaN/Inf
        bad = [f for f, val in v.items() if f in FEATURE_NAMES
               and (math.isnan(val) or math.isinf(val))]
        if bad:
            raise ValueError(f"NaN or Inf in features: {bad}")

        return v


class PredictResponse(BaseModel):
    p_win_long: float
    model_version: str
    latency_ms: float


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_version: str
    uptime_seconds: float
    total_requests: int


class ModelInfoResponse(BaseModel):
    model_version: str
    model_path: str
    n_features: int
    feature_names: list[str]
    threshold_recommendation: float


# --- Endpoints ---
@app.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest):
    """Score a single bar's features and return P(win) for LONG."""
    global request_count
    t0 = time.perf_counter()

    if long_model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    # Build feature array in the correct order
    feature_array = np.array(
        [[req.features[f] for f in FEATURE_NAMES]]
    )

    # Predict
    p_win_long = float(long_model.predict_proba(feature_array)[0, 1])

    latency_ms = (time.perf_counter() - t0) * 1000
    request_count += 1

    # Log to SQLite (best-effort, don't block response)
    features_json = json.dumps(
        {f: req.features[f] for f in FEATURE_NAMES}
    )
    log_prediction(
        symbol=req.symbol,
        bar_timestamp=req.timestamp,
        p_win_long=p_win_long,
        latency_ms=latency_ms,
        features_json=features_json,
    )

    return PredictResponse(
        p_win_long=round(p_win_long, 6),
        model_version=MODEL_VERSION,
        latency_ms=round(latency_ms, 2),
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    uptime = (datetime.now(timezone.utc) - start_time).total_seconds() \
        if start_time else 0

    return HealthResponse(
        status="ok" if long_model is not None else "degraded",
        model_loaded=long_model is not None,
        model_version=MODEL_VERSION,
        uptime_seconds=round(uptime, 1),
        total_requests=request_count,
    )


@app.get("/model_info", response_model=ModelInfoResponse)
async def model_info():
    """Return model metadata and feature list."""
    return ModelInfoResponse(
        model_version=MODEL_VERSION,
        model_path=str(LONG_MODEL_PATH),
        n_features=len(FEATURE_NAMES),
        feature_names=FEATURE_NAMES,
        threshold_recommendation=0.65,
    )
