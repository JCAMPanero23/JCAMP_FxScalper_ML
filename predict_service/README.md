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

## VPS Deployment (Current: Hetzner CX23, Ubuntu 22.04)

**Live VPS:** `91.99.227.165` | Service: `jcamp-predict` (systemd)

### Prerequisites

1. Ubuntu 22.04 VPS (Hetzner CX23)
2. Python 3.11 + venv at `/opt/jcamp/venv`
3. Service files at `/opt/jcamp/predict_service/`

### Install as systemd service (auto-restarts on crash)

```bash
cp jcamp-predict.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable jcamp-predict   # auto-start on boot
systemctl start jcamp-predict
systemctl status jcamp-predict
```

### Common management commands

```bash
systemctl restart jcamp-predict   # restart
systemctl stop jcamp-predict      # stop
journalctl -u jcamp-predict -f    # tail live logs
journalctl -u jcamp-predict --since "1 hour ago"  # recent logs
curl http://localhost:8000/health  # verify locally
```

### Firewall (UFW)

Port 8000 is open to anywhere (dynamic IP support — cTrader runs on a home connection with rotating IP):

```bash
ufw status                          # check rules
ufw allow 8000                      # open to anywhere (current config)
# When cTrader moves to a static Windows VPS, lock it down:
# ufw delete allow 8000
# ufw allow from <WINDOWS_VPS_IP> to any port 8000
```

> **Why open to anywhere?** The home internet IP rotates dynamically. On 2026-04-21,
> a rotating IP caused a ~6-hour outage (10:45am–16:22 UTC) when UFW blocked the new IP.
> Once cTrader moves to a Windows VPS with a static IP, restrict port 8000 to that IP only.

### cBot Auto-Recovery (SSH-based)

The cBot (`JCAMP_FxScalper_ML.cs`) monitors API health and SSHes into this VPS to
restart the systemd service when 3 consecutive failures are detected.

**Required one-time setup on the cTrader machine:**

```powershell
# Generate SSH key (if not already present)
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\jcamp_vps" -N ""

# Copy public key to VPS
type "$env:USERPROFILE\.ssh\jcamp_vps.pub" | ssh root@91.99.227.165 "cat >> ~/.ssh/authorized_keys"

# Test passwordless login
ssh -i "$env:USERPROFILE\.ssh\jcamp_vps" root@91.99.227.165 "systemctl status jcamp-predict"
```

**cBot parameters to set:**

| Parameter | Value |
|---|---|
| Auto-Restart API Service | `true` |
| VPS SSH Host | `91.99.227.165` |
| VPS SSH User | `root` |
| SSH Key Path | `C:\Users\Jcamp_Laptop\.ssh\jcamp_vps` |
| VPS Service Name | `jcamp-predict` |

The cBot will run: `ssh -i <key> root@91.99.227.165 "systemctl restart jcamp-predict"`

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
