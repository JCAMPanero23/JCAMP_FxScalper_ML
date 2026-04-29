"""
JCAMP FxScalper ML — Prediction Service (v0.6.1)
================================================

FastAPI service that loads LONG and SHORT LightGBM models and serves
both probabilities on POST /predict.

The cBot decides whether to act on p_win_short (shadow vs live).
The service always returns both — logging happens regardless of action.
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
    SHORT_MODEL_PATH,
    MODEL_VERSION,
    LONG_THRESHOLD,
    SHORT_THRESHOLD,
    DB_PATH,
)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("predict_service")

long_model = None
short_model = None
start_time = None
request_count = 0


def init_db():
    """Create prediction log table if missing; add p_win_short column if upgrading from v0.5."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prediction_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            bar_timestamp TEXT,
            p_win_long REAL NOT NULL,
            p_win_short REAL,
            model_version TEXT NOT NULL,
            latency_ms REAL NOT NULL,
            features_json TEXT
        )
    """)
    cur = conn.execute("PRAGMA table_info(prediction_log)")
    cols = [row[1] for row in cur.fetchall()]
    if "p_win_short" not in cols:
        conn.execute("ALTER TABLE prediction_log ADD COLUMN p_win_short REAL")
        logger.info("Added p_win_short column to prediction_log (v0.5 -> v0.6.1 upgrade)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pred_timestamp ON prediction_log(timestamp)")
    conn.commit()
    conn.close()
    logger.info(f"Prediction log database ready at {DB_PATH}")


def log_prediction(symbol, bar_timestamp, p_win_long, p_win_short, latency_ms, features_json):
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            """INSERT INTO prediction_log
               (timestamp, symbol, bar_timestamp, p_win_long, p_win_short,
                model_version, latency_ms, features_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (datetime.now(timezone.utc).isoformat(), symbol, bar_timestamp,
             p_win_long, p_win_short, MODEL_VERSION, latency_ms, features_json),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to log prediction: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global long_model, short_model, start_time

    logger.info("=" * 60)
    logger.info("JCAMP FxScalper ML — Prediction Service Starting (v0.6.1)")
    logger.info("=" * 60)

    if not LONG_MODEL_PATH.exists():
        raise FileNotFoundError(f"LONG model file not found: {LONG_MODEL_PATH}")
    if not SHORT_MODEL_PATH.exists():
        raise FileNotFoundError(f"SHORT model file not found: {SHORT_MODEL_PATH}")

    long_model = load(LONG_MODEL_PATH)
    short_model = load(SHORT_MODEL_PATH)
    logger.info(f"Loaded LONG  model from {LONG_MODEL_PATH}")
    logger.info(f"Loaded SHORT model from {SHORT_MODEL_PATH}")
    logger.info(f"Model version: {MODEL_VERSION}")
    logger.info(f"Expected features: {len(FEATURE_NAMES)}")

    init_db()
    start_time = datetime.now(timezone.utc)
    logger.info("Service ready. Listening on http://localhost:8000")

    yield
    logger.info("Service shutting down.")


app = FastAPI(title="JCAMP FxScalper ML", version=MODEL_VERSION, lifespan=lifespan)


class PredictRequest(BaseModel):
    symbol: str
    timestamp: str = ""
    features: dict[str, float]

    @field_validator("features")
    @classmethod
    def validate_features(cls, v):
        missing = [f for f in FEATURE_NAMES if f not in v]
        if missing:
            raise ValueError(f"Missing features: {missing}")
        bad = [f for f, val in v.items() if f in FEATURE_NAMES
               and (math.isnan(val) or math.isinf(val))]
        if bad:
            raise ValueError(f"NaN or Inf in features: {bad}")
        return v


class PredictResponse(BaseModel):
    p_win_long: float
    p_win_short: float
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
    long_model_path: str
    short_model_path: str
    n_features: int
    feature_names: list[str]
    long_threshold: float
    short_threshold: float


@app.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest):
    global request_count
    t0 = time.perf_counter()

    if long_model is None or short_model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    feature_array = np.array([[req.features[f] for f in FEATURE_NAMES]])
    p_win_long = float(long_model.predict_proba(feature_array)[0, 1])
    p_win_short = float(short_model.predict_proba(feature_array)[0, 1])

    latency_ms = (time.perf_counter() - t0) * 1000
    request_count += 1

    features_json = json.dumps({f: req.features[f] for f in FEATURE_NAMES})
    log_prediction(req.symbol, req.timestamp, p_win_long, p_win_short,
                   latency_ms, features_json)

    return PredictResponse(
        p_win_long=round(p_win_long, 6),
        p_win_short=round(p_win_short, 6),
        model_version=MODEL_VERSION,
        latency_ms=round(latency_ms, 2),
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    uptime = (datetime.now(timezone.utc) - start_time).total_seconds() if start_time else 0
    loaded = long_model is not None and short_model is not None
    return HealthResponse(
        status="ok" if loaded else "degraded",
        model_loaded=loaded,
        model_version=MODEL_VERSION,
        uptime_seconds=round(uptime, 1),
        total_requests=request_count,
    )


@app.get("/model_info", response_model=ModelInfoResponse)
async def model_info():
    return ModelInfoResponse(
        model_version=MODEL_VERSION,
        long_model_path=str(LONG_MODEL_PATH),
        short_model_path=str(SHORT_MODEL_PATH),
        n_features=len(FEATURE_NAMES),
        feature_names=FEATURE_NAMES,
        long_threshold=LONG_THRESHOLD,
        short_threshold=SHORT_THRESHOLD,
    )
