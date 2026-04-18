# Phase 3 — FastAPI Inference Service

**Date:** 2026-04-18
**Status:** Ready to build
**Deliverable:** `predict_service/` — a FastAPI app that loads the trained
LightGBM model and serves predictions on `POST /predict`

---

## What This Service Does

The cBot (Phase 4) computes 46 features on every M5 bar close, sends them
to this service via HTTP, and gets back a probability. The service is the
bridge between your C# trading bot and the Python ML model.

```
cTrader cBot ──HTTP POST──► FastAPI service ──► LightGBM model
     (C#)        (JSON)         (Python)          (.joblib)
                                   │
                                   ▼
                              { p_win_long: 0.72 }
```

The service runs on the same VPS as cTrader. No internet exposure needed.
Localhost only.

---

## Project Layout

```
predict_service/
├── app.py                  # FastAPI application (main file)
├── config.py               # Configuration (paths, thresholds, feature list)
├── models/                 # Model files (symlinked or copied from project)
│   └── eurusd_long_v04_final_holdout.joblib
├── prediction_log.db       # SQLite log (auto-created on first request)
├── requirements.txt        # Python dependencies
├── install_service.bat     # NSSM service installer script
├── healthcheck.py          # Standalone healthcheck script
└── README.md               # Setup and deployment instructions
```

---

## File 1: config.py

```python
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
```

---

## File 2: app.py

```python
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
    import json
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
```

---

## File 3: requirements.txt

```
fastapi==0.115.0
uvicorn==0.30.0
pydantic==2.8.0
joblib==1.4.2
lightgbm==4.5.0
numpy==1.26.4
scikit-learn==1.5.2
```

Pin versions to match what you trained with. If your training env used
different versions of lightgbm or scikit-learn, use THOSE versions here.
Version mismatch between training and serving can cause silent prediction
errors.

---

## File 4: healthcheck.py

```python
"""
Standalone healthcheck script.
Run via Task Scheduler every 5 minutes to verify service is alive.
If service is down, log an alert (extend with email/Telegram later).
"""

import sys
import requests
from datetime import datetime

URL = "http://localhost:8000/health"
LOG_FILE = "healthcheck.log"


def check():
    try:
        r = requests.get(URL, timeout=5)
        data = r.json()
        status = data.get("status", "unknown")
        uptime = data.get("uptime_seconds", 0)
        reqs = data.get("total_requests", 0)

        msg = (f"{datetime.now().isoformat()} | "
               f"status={status} | uptime={uptime:.0f}s | "
               f"requests={reqs}")

        if status != "ok":
            msg += " | WARNING: service degraded"

        print(msg)
        with open(LOG_FILE, "a") as f:
            f.write(msg + "\n")

        return 0 if status == "ok" else 1

    except requests.exceptions.ConnectionError:
        msg = f"{datetime.now().isoformat()} | ERROR: service unreachable"
        print(msg)
        with open(LOG_FILE, "a") as f:
            f.write(msg + "\n")
        return 2

    except Exception as e:
        msg = f"{datetime.now().isoformat()} | ERROR: {e}"
        print(msg)
        with open(LOG_FILE, "a") as f:
            f.write(msg + "\n")
        return 2


if __name__ == "__main__":
    sys.exit(check())
```

---

## File 5: install_service.bat

```bat
@echo off
REM Install JCAMP FxScalper ML Prediction Service as a Windows service
REM Requires NSSM (https://nssm.cc/) to be installed and on PATH
REM
REM Run this script as Administrator on the VPS

SET SERVICE_NAME=JCAMP_FxScalper_ML_API
SET PYTHON_PATH=C:\Python311\python.exe
SET APP_DIR=D:\JCAMP_FxScalper_ML\predict_service
SET LOG_DIR=D:\JCAMP_Logs

REM Create log directory
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM Install the service
nssm install %SERVICE_NAME% %PYTHON_PATH% -m uvicorn app:app --host 127.0.0.1 --port 8000
nssm set %SERVICE_NAME% AppDirectory %APP_DIR%
nssm set %SERVICE_NAME% AppStdout %LOG_DIR%\predict_service_stdout.log
nssm set %SERVICE_NAME% AppStderr %LOG_DIR%\predict_service_stderr.log
nssm set %SERVICE_NAME% AppRotateFiles 1
nssm set %SERVICE_NAME% AppRotateBytes 10485760

REM Auto-start on boot
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START

REM Restart on failure (after 5 second delay)
nssm set %SERVICE_NAME% AppExit Default Restart
nssm set %SERVICE_NAME% AppRestartDelay 5000

echo.
echo Service "%SERVICE_NAME%" installed.
echo.
echo To start:  nssm start %SERVICE_NAME%
echo To stop:   nssm stop %SERVICE_NAME%
echo To remove: nssm remove %SERVICE_NAME% confirm
echo.
echo IMPORTANT: Update PYTHON_PATH and APP_DIR above to match your VPS paths.
pause
```

---

## How to Run Locally (Development / Testing)

```bash
cd predict_service

# Install dependencies
pip install -r requirements.txt

# Copy model file into predict_service/models/
# (or symlink it from the project models/ directory)
mkdir models
copy ..\models\eurusd_long_v04_final_holdout.joblib models\

# Run the server
python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

Then test with curl or Python:

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "EURUSD",
    "timestamp": "2026-04-18T14:35:00Z",
    "features": {
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
  }'
```

Expected response:
```json
{
  "p_win_long": 0.691,
  "model_version": "eurusd_long_v04_20260418",
  "latency_ms": 3.2
}
```

Test the other endpoints:
```bash
curl http://localhost:8000/health
curl http://localhost:8000/model_info
```

---

## Testing Checklist (Before Deploying to VPS)

### Functional Tests

- [ ] `/predict` returns valid p_win_long for the sample request above
- [ ] `/predict` rejects request with missing features (returns 422)
- [ ] `/predict` rejects request with NaN values (returns 422)
- [ ] `/predict` rejects request with empty features dict (returns 422)
- [ ] `/health` returns status "ok" and model_loaded=true
- [ ] `/model_info` returns correct feature list (46 features)
- [ ] Prediction log in SQLite captures every request
- [ ] Service starts cleanly from cold (model loads on startup)

### Performance Tests

- [ ] Single prediction latency < 10ms (measured by latency_ms in response)
- [ ] 100 sequential requests complete without errors
- [ ] Service handles malformed JSON without crashing
- [ ] Service handles network timeout from client gracefully

### Resilience Tests

- [ ] Service restarts automatically if killed (via NSSM on VPS)
- [ ] Service survives model file being temporarily unavailable at startup
  (should log error, not crash silently)
- [ ] SQLite log doesn't grow unbounded (check after 1000 predictions)

---

## Deployment to VPS

### Prerequisites

1. Windows Server VPS (Vultr or IONOS, London datacenter)
2. Python 3.11 installed
3. NSSM installed (https://nssm.cc/download)
4. cTrader Desktop installed and running

### Steps

1. Copy `predict_service/` folder to VPS (e.g., `D:\JCAMP_FxScalper_ML\predict_service\`)
2. Copy model file to `predict_service/models/`
3. Install Python dependencies: `pip install -r requirements.txt`
4. Test locally first: `python -m uvicorn app:app --host 127.0.0.1 --port 8000`
5. Verify with curl or browser: `http://localhost:8000/health`
6. Edit `install_service.bat` paths to match your VPS
7. Run `install_service.bat` as Administrator
8. Start the service: `nssm start JCAMP_FxScalper_ML_API`
9. Set up healthcheck in Task Scheduler (every 5 minutes)

### Verify on VPS

```bash
curl http://localhost:8000/health
# Should return: {"status":"ok","model_loaded":true,...}

curl http://localhost:8000/model_info
# Should return feature list with 46 features
```

---

## What This Spec Does NOT Cover (Phase 4)

- The cBot that calls this API (Phase 4, separate spec)
- Train/serve feature skew testing (Phase 4, JCAMP_Features.cs extraction)
- Model retraining pipeline (Phase 5)
- Hot-reload of model files without restarting the service (v2 enhancement)

---

## PRD Updates From Phase 2 Findings

The original PRD spec for Phase 3 mentioned loading "both long and short
models." Since SHORT did not pass Gate A, the v1 service is **LONG-only**.

| PRD Original | v1 Actual | Reason |
|---|---|---|
| Load long + short models | Load LONG only | SHORT failed Gate A |
| `p_win_short` in response | Removed | Not deployed |
| ~35 features | 46 features | v0.3 MTF + v0.4 regime |
| `p_win > 0.55` default | `p_win > 0.65` recommendation | Gate A threshold |

---

## Acceptance Criteria (From PRD, Updated)

- [ ] `/predict` endpoint returns p_win_long within expected range (0.0–1.0)
- [ ] p99 latency < 50ms (target < 10ms typical)
- [ ] Service survives cTrader restart, network blip
- [ ] Prediction log captures 100% of requests
- [ ] Service auto-starts on VPS boot via NSSM
- [ ] Healthcheck script runs every 5 minutes via Task Scheduler
- [ ] Model version is visible in `/health` and `/model_info` responses
