# JCAMP FxScalper ML

ML-filtered M5 forex scalping system using LightGBM and triple-barrier labeling.

## Project Status

**Current Phase:** Phase 4 — Trading cBot Implementation (COMPLETE)
**Last Updated:** 2026-04-18

See [STATUS.md](STATUS.md) for detailed status and [PRD_JCAMP_FxScalper_ML.md](PRD_JCAMP_FxScalper_ML.md) for full project requirements.

## Phase 4 — Trading cBot Deployment Guide

### Prerequisites

1. **FastAPI Service Running** (from Phase 3)
   - Service must be running on `http://localhost:8000`
   - Verify with: `curl http://localhost:8000/health`
   - Expected: `{"status":"ok","model_loaded":true,...}`

2. **cTrader Platform**
   - Version: Latest (2024+)
   - Account: Demo (for forward test) or Live (after demo passes)
   - Symbol: EURUSD
   - Timeframe: M5

### Installation

1. **Copy shared module to cTrader:**
   - Copy `cbot/JCAMP_Features.cs` to cTrader sources folder
   - Location: `%USERPROFILE%\Documents\cAlgo\Sources\Robots\JCAMP_Features.cs`

2. **Copy trading cBot to cTrader:**
   - Copy `cbot/JCAMP_FxScalper_ML/JCAMP_FxScalper_ML.cs` to cTrader sources folder
   - Location: `%USERPROFILE%\Documents\cAlgo\Sources\Robots\JCAMP_FxScalper_ML.cs`

3. **Build in cTrader:**
   - Open cTrader Automate
   - Build both files (should compile with zero errors)

### Configuration

**Demo Forward Test Settings:**
```
Symbol: EURUSD
Timeframe: M5
MLThreshold: 0.65
ApiUrl: http://localhost:8000/predict
ApiTimeoutMs: 5000
RiskPercent: 1.0
SlAtrMult: 1.5
TpAtrMult: 3.0
DailyLossLimitR: -2.0
MonthlyDDPercent: 6.0
MaxConsecLosses: 8
MaxPositions: 1
EnableTrading: true  (set to true for demo test)
```

**Live Settings:**
- Same as demo, but on live account
- Account size: $500 minimum
- Risk per trade: $5 (1% of $500)

### Monitoring

**Daily Checks (first week):**
- API health: Check FastAPI logs for errors
- Trade frequency: ~2-5 trades per day expected
- Position sizing: Verify lots match risk calculation
- R-multiples: Check exit logs for win/loss R values
- Risk limits: Monitor daily R loss, monthly DD

**Weekly Checks (after first week):**
- Cumulative R: Track net R across all trades
- Win rate: Should be ~58% (from holdout test)
- Max consecutive losses: Should not exceed 16 (from holdout)
- Monthly DD: Should not exceed 6% (stop trading if hit)

### Troubleshooting

**API Connection Errors:**
- Check FastAPI service is running: `curl http://localhost:8000/health`
- Check firewall allows localhost connections
- Check API URL parameter matches service URL

**No Trades:**
- Verify model threshold (0.65 is conservative, try 0.60 for more trades)
- Check FastAPI logs for prediction values
- Verify feature computation (check cBot logs for null features)

**Unexpected Losses:**
- Check position sizing calculation
- Verify SL/TP levels (should be 1.5×ATR / 3.0×ATR)
- Review exit logs for R-multiples
- Check if risk limits are working (daily/monthly/consecutive)

### Files

- **Trading cBot:** `cbot/JCAMP_FxScalper_ML/JCAMP_FxScalper_ML.cs`
- **Shared Features:** `cbot/JCAMP_Features.cs`
- **FastAPI Service:** `predict_service/app.py`
- **Model File:** `predict_service/models/eurusd_long_v04_final_holdout.joblib`

---

## Phase 2 Structure

```
JCAMP_FxScalper_ML/
├── data/                       # CSVs from DataCollector (gitignored)
│   └── DataCollector_EURUSD_M5_20230101_220400.csv (243k rows)
├── models/                     # Trained .joblib models
├── notebooks/                  # Jupyter notebooks for ML workflow
│   ├── 01_eda.ipynb           # Exploratory data analysis
│   ├── 02_train_baseline.ipynb # Baseline model training (70/30 split)
│   └── 03_walk_forward.ipynb  # 6-fold purged walk-forward CV
├── src/                        # Python modules
│   ├── __init__.py
│   ├── data_loader.py         # Load CSV, data splits, validation
│   ├── labels.py              # 3-class → binary label conversion
│   ├── features.py            # Feature utilities
│   ├── cv.py                  # PurgedWalkForward CV implementation
│   ├── train.py               # LightGBM training & model persistence
│   └── evaluate.py            # Metrics, equity curves, performance reports
├── tests/                      # Unit tests
├── cbot/                       # C# cBots (Phase 1 & 4)
├── requirements.txt            # Python dependencies
├── .gitignore
└── README.md
```

## Setup Instructions

### 1. Create Python Environment

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run Jupyter

```bash
jupyter notebook
```

Navigate to `notebooks/` and start with `01_eda.ipynb`.

## Phase 2 Workflow

1. **EDA** (`01_eda.ipynb`)
   - Load CSV from Phase 1
   - Validate data quality (no NaN/Inf)
   - Analyze label balance
   - Check feature distributions
   - Identify correlations

2. **Baseline Training** (`02_train_baseline.ipynb`)
   - Simple 70/30 split
   - Train separate LONG/SHORT models
   - Verify ROC-AUC > 0.55 (minimum edge threshold)
   - Feature importance analysis

3. **Walk-Forward CV** (`03_walk_forward.ipynb`)
   - 6-fold purged walk-forward
   - Embargo period to prevent leakage
   - Aggregate OOS metrics
   - Train final models on full train/CV set
   - Export to `models/eurusd_{long,short}_v1.joblib`

## Key Constraints

- **NEVER** use held-out test set (Oct 2025 - Mar 2026) for hyperparameter tuning
- Target: OOS ROC-AUC > 0.55
- Target: Positive expectancy on ≥4 of 6 CV folds
- Conservative LightGBM params to prevent overfitting (max_depth=6, num_leaves=31)

## Data Splits

- **Train/CV:** Jan 2023 - Sep 2025 (204,392 rows, 84.0%)
- **Held-out test:** Oct 2025 - Mar 2026 (36,845 rows, 15.1%) — TOUCH ONCE
- **Live forward:** Apr 2026+ (1,979 rows, 0.8%)

## Next Phase

**Phase 3:** FastAPI inference service for live predictions (`POST /predict`).

See PRD for full roadmap.
