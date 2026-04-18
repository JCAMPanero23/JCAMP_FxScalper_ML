# JCAMP FxScalper ML — Prediction Service

FastAPI inference service for the trained LightGBM LONG model. Serves real-time predictions on EURUSD M5 bars.

## Quick Start (Local Development)

### 1. Install dependencies

```bash
cd predict_service
pip install -r requirements.txt
```

### 2. Copy model file

```bash
mkdir models
copy ..\models\eurusd_long_v04_final_holdout.joblib models\
```

Or create a symlink (Windows):
```bash
cd models
mklink eurusd_long_v04_final_holdout.joblib ..\..\models\eurusd_long_v04_final_holdout.joblib
```

### 3. Run the server

```bash
python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### 4. Test the endpoints

#### Health check
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "ok",
  "model_loaded": true,
  "model_version": "eurusd_long_v04_20260418",
  "uptime_seconds": 5.2,
  "total_requests": 0
}
```

#### Model info
```bash
curl http://localhost:8000/model_info
```

Expected response:
```json
{
  "model_version": "eurusd_long_v04_20260418",
  "model_path": "D:\\JCAMP_FxScalper_ML\\predict_service\\models\\eurusd_long_v04_final_holdout.joblib",
  "n_features": 46,
  "feature_names": ["dist_sma_m5_50", "dist_sma_m5_100", ...],
  "threshold_recommendation": 0.65
}
```

#### Get a prediction

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
      ...
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

## API Documentation

The service auto-generates OpenAPI documentation at:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## Features

- **Single endpoint for predictions:** `POST /predict`
- **Health monitoring:** `GET /health`
- **Model metadata:** `GET /model_info`
- **Prediction logging:** All requests logged to SQLite `prediction_log.db`
- **Input validation:** Pydantic validates all required features, rejects NaN/Inf
- **Performance:** Typical latency <5ms per prediction
- **Logging:** Detailed logs of startup, errors, and predictions

## Configuration

Edit `config.py` to:
- Change model path: `LONG_MODEL_PATH`
- Update feature names: `FEATURE_NAMES`
- Update model version: `MODEL_VERSION`
- Change database path: `DB_PATH`

**Important:** Feature names must match training exactly, in the same order.

## Database

Prediction log is stored in SQLite (`prediction_log.db`). Example query:

```sql
SELECT timestamp, symbol, p_win_long, latency_ms
FROM prediction_log
ORDER BY timestamp DESC
LIMIT 10;
```

## Performance

- **Typical latency:** 3–5 ms per prediction
- **p99 latency target:** <10 ms
- **Throughput:** Handles 200+ requests/second (well above cBot needs)

## VPS Deployment

### Prerequisites

1. Windows Server 2019+ (Vultr London datacenter recommended)
2. Python 3.11 installed
3. NSSM (https://nssm.cc/download) installed
4. cTrader Desktop running

### Steps

1. Copy `predict_service/` to VPS (e.g., `D:\JCAMP_FxScalper_ML\predict_service\`)
2. Copy trained model to `predict_service/models/`
3. Install dependencies:
   ```bash
   cd predict_service
   pip install -r requirements.txt
   ```
4. Test locally first:
   ```bash
   python -m uvicorn app:app --host 127.0.0.1 --port 8000
   ```
5. Verify with curl:
   ```bash
   curl http://localhost:8000/health
   ```
6. Edit `install_service.bat` paths to match your VPS
7. Run as Administrator:
   ```bash
   install_service.bat
   ```
8. Start the service:
   ```bash
   nssm start JCAMP_FxScalper_ML_API
   ```

### Task Scheduler for Healthchecks

To run healthchecks every 5 minutes:

1. Open Task Scheduler
2. Create Basic Task:
   - Name: `JCAMP_FxScalper_ML_Healthcheck`
   - Trigger: Repeat every 5 minutes
   - Action: Start a program
     - Program: `C:\Python311\python.exe`
     - Arguments: `D:\JCAMP_FxScalper_ML\predict_service\healthcheck.py`
     - Start in: `D:\JCAMP_FxScalper_ML\predict_service`

## Troubleshooting

### Model fails to load at startup

```
ERROR: Model file not found: D:\JCAMP_FxScalper_ML\predict_service\models\eurusd_long_v04_final_holdout.joblib
```

**Fix:** Copy or symlink the model file to `predict_service/models/`

### Service returns 503 "Model not loaded"

**Fix:** Check that model loaded successfully in logs. Restart the service.

### Feature validation error: "Missing features"

**Fix:** Ensure cBot sends all 46 features. Check feature names in request vs `config.py`.

### NaN/Inf in features

**Fix:** Ensure cBot feature calculations are correct (no division by zero, etc).

### Latency > 10ms

- Normal: LightGBM predictions are fast, <5ms expected
- Check CPU load on VPS
- Consider running service with higher priority on VPS

## Testing Checklist

- [ ] `/predict` endpoint returns valid p_win_long
- [ ] `/predict` rejects missing features
- [ ] `/predict` rejects NaN/Inf values
- [ ] `/health` returns status "ok"
- [ ] `/model_info` returns 46 features
- [ ] Predictions are logged to SQLite
- [ ] Startup logs show model loading successfully
- [ ] Latency < 10ms typical

## Model Version

- **Current:** eurusd_long_v04_20260418
- **Training data:** Jan 2, 2023 – Sep 30, 2025
- **Holdout validation:** Oct 1, 2025 – Mar 31, 2026
- **Features:** 46 (39 base + 5 MTF v0.3 + 2 regime v0.4)
- **Threshold:** 0.65 (Gate A passing threshold)

## Phase 4 Integration

The cBot (Phase 4) will:

1. Calculate 46 features every M5 bar
2. Send `POST /predict` request with features
3. Use response `p_win_long` value to decide entry
4. Log all predictions for audit trail

Expected flow:
```
cBot calculates features → POST /predict → Receive p_win_long → Enter trade if p_win_long > 0.65
```

## Support

For issues or questions:
1. Check logs: `prediction_log.db` and service logs
2. Review `PHASE3_FASTAPI_SPEC.md` for detailed specification
3. Check feature extraction in Phase 4 cBot code
