# VPS Setup Checklist — ML Service as Auto-Start (No Terminal)

**Goal:** Make the ML prediction service on the Hetzner VPS (`91.99.227.165`) start automatically
on boot with no terminal window — so the cBot always has predictions available.

---

## Step 1 — Connect to the VPS

Two options (try A first):

**Option A — Hetzner Browser Console (no RDP needed)**
1. Go to https://console.hetzner.cloud
2. Click **jcamp-predict** server
3. Click the **Console** button (top-right of the server page)
4. A browser-based terminal opens — you're in

**Option B — Fix RDP (do this inside the VPS after connecting via Option A)**
```powershell
# Enable RDP and open firewall port — run as Admin
Set-ItemProperty -Path 'HKLM:\System\CurrentControlSet\Control\Terminal Server' -Name "fDenyTSConnections" -Value 0
Enable-NetFirewallRule -DisplayGroup "Remote Desktop"
```
After this, RDP from your office machine using `91.99.227.165` should work.

---

## Step 2 — Find Python Path and App Directory

Open **PowerShell** on the VPS and run:
```powershell
(Get-Command python).Source
```
Note the result — it might be `C:\Python311\python.exe`, `C:\Python314\python.exe`, etc.

Also confirm the app directory exists:
```powershell
Test-Path "D:\JCAMP_FxScalper_ML\predict_service\app.py"
```
If it returns `False`, find it:
```powershell
Get-ChildItem C:\,D:\ -Recurse -Filter "app.py" -ErrorAction SilentlyContinue | Where-Object { $_.DirectoryName -like "*predict*" }
```

---

## Step 3 — Stop the Existing Terminal Process

The service is currently running in a terminal (fragile). Kill it first:
```powershell
# Find and kill the uvicorn process on port 8000
$pid = (netstat -ano | findstr ":8000")[0] -split '\s+' | Select-Object -Last 1
Stop-Process -Id $pid -Force
```

---

## Step 4 — Register as a Scheduled Task (Runs as SYSTEM at Boot)

> **Replace `C:\Python314\python.exe` with the actual path you found in Step 2.**
> **Replace `D:\JCAMP_FxScalper_ML\predict_service` with the actual path if different.**

Run this block in **PowerShell (Admin)**:

```powershell
$action = New-ScheduledTaskAction `
    -Execute "C:\Python314\python.exe" `
    -Argument "-m uvicorn app:app --host 0.0.0.0 --port 8000" `
    -WorkingDirectory "D:\JCAMP_FxScalper_ML\predict_service"

$trigger = New-ScheduledTaskTrigger -AtStartup

$principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName "JCAMP_FxScalper_ML_API" `
    -Description "JCAMP FastAPI prediction service" `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Force

Start-ScheduledTask -TaskName "JCAMP_FxScalper_ML_API"
```

---

## Step 5 — Verify It's Running

```powershell
# Check task status
Get-ScheduledTask -TaskName "JCAMP_FxScalper_ML_API" | Select-Object TaskName, State

# Check port 8000 is listening
netstat -ano | findstr ":8000"

# Quick health check
Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing
```

Expected: Task state = `Running`, port 8000 = `LISTENING`.

---

## Step 6 — Verify Firewall Allows Port 8000 (External Access)

The cBot on the office machine calls `http://91.99.227.165:8000/predict` — port 8000 must be open:

```powershell
# Check if rule exists
Get-NetFirewallRule -DisplayName "JCAMP ML Port 8000" -ErrorAction SilentlyContinue

# If nothing returned, add the rule:
New-NetFirewallRule `
    -DisplayName "JCAMP ML Port 8000" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 8000 `
    -Action Allow
```

---

## Step 7 — Test End-to-End from Office Machine

On the office machine (where cTrader runs), open PowerShell and run:
```powershell
Invoke-WebRequest -Uri "http://91.99.227.165:8000/health" -UseBasicParsing
```
Should return a 200 OK response. If it does, the cBot can reach the ML service. Done.

---

## After Setup — What Changes

| Before | After |
|---|---|
| Terminal window opens on login | No terminal, runs silently in background |
| Service dies if terminal closes | Restarts automatically within 1 minute |
| Service dies on VPS reboot | Auto-starts on every boot |
| Manual restart required | Fully autonomous |

---

## Notes

- Task runs as **SYSTEM** — no user login required
- Logs go to the process (check Task Scheduler history if issues arise)
- To stop manually: `Stop-ScheduledTask -TaskName "JCAMP_FxScalper_ML_API"`
- To start manually: `Start-ScheduledTask -TaskName "JCAMP_FxScalper_ML_API"`
- To remove: `Unregister-ScheduledTask -TaskName "JCAMP_FxScalper_ML_API" -Confirm:$false`

---

---

# Demo Performance Review — Before Going Live

**Goal:** Run this review on the **office machine (demo account)** using Claude Code after at least
1–2 weeks of demo trading. If the numbers look good, you're ready for live.

The prediction service logs every signal to `prediction_log.db` on the VPS. The cTrader journal
has the actual trade results. Together they tell you if the ML is earning its keep.

---

## Part A — Add File Logging to the ML Service (Do This on the VPS First)

Right now, service logs only go to the terminal and are lost when it runs as a background task.
Add a rotating log file so errors are always captured.

**On the VPS**, open `D:\JCAMP_FxScalper_ML\predict_service\app.py` and replace the logging block
(lines 37–41) with this:

```python
import logging.handlers
from pathlib import Path

_LOG_DIR = Path("D:/JCAMP_Logs")
_LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            _LOG_DIR / "predict_service.log",
            maxBytes=10 * 1024 * 1024,  # 10 MB per file
            backupCount=5,
        ),
    ],
)
logger = logging.getLogger("predict_service")
```

Then restart the service:
```powershell
Stop-ScheduledTask  -TaskName "JCAMP_FxScalper_ML_API"
Start-ScheduledTask -TaskName "JCAMP_FxScalper_ML_API"
```

Logs will now be written to `D:\JCAMP_Logs\predict_service.log`.

---

## Part B — Pull the Prediction Log from the VPS

The SQLite database lives on the VPS at:
```
D:\JCAMP_FxScalper_ML\predict_service\prediction_log.db
```

Copy it to your office machine for analysis. Once RDP is working:
- Open File Explorer → `\\91.99.227.165\D$\JCAMP_FxScalper_ML\predict_service\prediction_log.db`
- Copy it locally to your dev machine

Or via PowerShell from your office machine (after RDP is enabled):
```powershell
Copy-Item "\\91.99.227.165\D$\JCAMP_FxScalper_ML\predict_service\prediction_log.db" `
          "D:\JCAMP_FxScalper_ML\predict_service\prediction_log.db"
```

---

## Part C — Export cTrader Trade History

In cTrader on the office machine:
1. Go to **History** tab (bottom panel)
2. Set date range to cover the demo period
3. Right-click → **Export** → save as `demo_trades.csv`
4. Save it to `D:\JCAMP_FxScalper_ML\docs\demo_trades.csv`

---

## Part D — Run Claude Code Analysis on the Office Machine

Install Claude Code on the office machine if not already there:
```powershell
npm install -g @anthropic-ai/claude-code
```

Then open the project and ask Claude Code to run the performance review:
```
cd D:\JCAMP_FxScalper_ML
claude
```

Once inside Claude Code, paste this prompt:
```
Run a demo performance review. Analyze:
1. predict_service/prediction_log.db — signal frequency, score distributions,
   how often LONG >= 0.65 and SHORT >= 0.55 thresholds are hit per day
2. docs/demo_trades.csv — win rate, avg R:R, expectancy, max drawdown,
   best/worst sessions by hour and day-of-week
3. Cross-check: do high-confidence ML signals (p > 0.70) have better win rates
   than borderline signals (p 0.65–0.70)?
4. Give a go/no-go recommendation for live trading based on the data.
```

---

## Part E — Key Metrics to Check Before Going Live

| Metric | Minimum Target | How to Check |
|---|---|---|
| Demo period | ≥ 2 weeks, ≥ 50 trades | cTrader History |
| Win rate (LONG) | ≥ 55% | cTrader History |
| Win rate (SHORT) | ≥ 55% | cTrader History |
| Expectancy | > 0 (positive) | Claude Code analysis |
| Max drawdown | < 10% of balance | cTrader History |
| ML signal frequency | 1–5 signals/day | prediction_log.db |
| High-conf win rate (p > 0.70) | Better than p 0.65–0.70 | Claude Code analysis |
| API error rate | < 1% of bars | predict_service.log |
| Service uptime | No gaps > 5 min | prediction_log.db timestamps |

If all green → proceed to live with minimum lot size.
If any red → investigate before going live.

---

## Part F — Quick SQL Queries for the Prediction Log

Run these directly on the VPS (or on a local copy) using any SQLite tool
or Python:

```python
import sqlite3, pandas as pd

conn = sqlite3.connect("predict_service/prediction_log.db")

# Total predictions and date range
print(pd.read_sql("SELECT COUNT(*) as total, MIN(timestamp) as first, MAX(timestamp) as last FROM prediction_log", conn))

# Daily signal count (bars where ML fired above threshold)
print(pd.read_sql("""
    SELECT DATE(timestamp) as date,
           SUM(CASE WHEN p_win_long  >= 0.65 THEN 1 ELSE 0 END) as long_signals,
           SUM(CASE WHEN p_win_short >= 0.55 THEN 1 ELSE 0 END) as short_signals,
           COUNT(*) as total_bars
    FROM prediction_log
    GROUP BY DATE(timestamp)
    ORDER BY date DESC
    LIMIT 30
""", conn))

# Score distribution buckets
print(pd.read_sql("""
    SELECT
        ROUND(p_win_long, 1) as score_bucket,
        COUNT(*) as count
    FROM prediction_log
    GROUP BY ROUND(p_win_long, 1)
    ORDER BY score_bucket
""", conn))

# Average latency (should be < 50ms)
print(pd.read_sql("SELECT AVG(latency_ms) as avg_ms, MAX(latency_ms) as max_ms FROM prediction_log", conn))

conn.close()
```

---

## Go / No-Go Decision

After running the Claude Code analysis:

- **Go** — win rate ≥ 55%, positive expectancy, drawdown < 10%, ML adds value at high confidence
- **No-Go** — any metric below target → fix the model or thresholds before going live

Start live with **minimum lot size (0.01)** for the first 2 weeks regardless of demo results.
