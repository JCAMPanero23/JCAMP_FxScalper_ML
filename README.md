# JCAMP FxScalper ML

ML-filtered M5 forex scalping system using LightGBM and triple-barrier labeling.

## Project Status

**Current Phase:** Phase 2 — Python ML Pipeline
**Last Updated:** 2026-04-12

See [STATUS.md](STATUS.md) for detailed status and [PRD_JCAMP_FxScalper_ML.md](PRD_JCAMP_FxScalper_ML.md) for full project requirements.

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
