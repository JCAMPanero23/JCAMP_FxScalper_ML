# PRD: JCAMP FxScalper ML

> **Status**: Draft v0.1 — Phase 1 (DataCollector) ready to build
> **Owner**: JCamp
> **Last updated**: 2026-04-12

---

## 1. Goal

Build an end-to-end ML-filtered M5 forex scalping system. A LightGBM model, trained on historical M5 features with triple-barrier labels, scores each bar's win probability. A cTrader cBot consumes those scores via a local Python API and trades only high-confidence setups.

**Success criteria:**
- Out-of-sample (walk-forward) win rate beats unfiltered baseline by ≥5 percentage points
- Out-of-sample profit factor ≥ 1.3 across multiple test windows
- Live forward-test results match backtest within ±20% on R-multiple
- System runs unattended on VPS for ≥30 days without manual intervention

**Non-goals:**
- Beating institutional HFT
- Sub-M5 trading
- Trading more than 3 pairs in v1
- Replacing the existing v4.5.x cBot (this is a parallel system)

---

## 2. Background

JCamp has an existing rule-based cTrader cBot (`JCAMP_FxScalper` v4.5.x) that uses MTF SMA alignment + ADX flip logic on M1. v4.6.0 added a 4TF system but shows negative R on validation — likely overfitting. Rather than tune rules further, this project takes a different approach: log every M5 bar with rich features, let LightGBM discover entry conditions, and use the model as a filter on top of (or replacement for) hand-coded rules.

---

## 3. Architecture

```
┌──────────────────────────────────────────────┐
│  VPS (Vultr/IONOS London, ~$7-10/month)      │
│                                              │
│  ┌──────────────────────────────────┐        │
│  │  cTrader Desktop                 │        │
│  │  ┌─────────────────────────┐     │        │
│  │  │ JCAMP_DataCollector     │     │   ← Phase 1 (backtest only)
│  │  │ (M5, no trading)        │     │        │
│  │  └─────────────────────────┘     │        │
│  │                                  │        │
│  │  ┌─────────────────────────┐     │        │
│  │  │ JCAMP_FxScalper_ML      │─────┼────┐   ← Phase 4
│  │  │ (M5, EURUSD)            │     │    │   │
│  │  └─────────────────────────┘     │    │   │
│  │  ┌─────────────────────────┐     │    │   │
│  │  │ JCAMP_FxScalper_ML      │─────┼────┤   │
│  │  │ (M5, GBPUSD instance)   │     │    │   │
│  │  └─────────────────────────┘     │    │   │
│  └──────────────────────────────────┘    │   │
│                                          │   │
│  ┌──────────────────────────────────┐    │   │
│  │  FastAPI service (localhost:8000)│◄───┘   │
│  │  POST /predict                   │        │
│  │   - loads LightGBM model         │        │
│  │   - returns P(win) per direction │        │
│  │  Runs as Windows Service         │        │
│  └──────────────────────────────────┘        │
│                                              │
│  ┌──────────────────────────────────┐        │
│  │  Local data + retraining scripts │        │
│  │  - CSVs from DataCollector       │        │
│  │  - Trained model files           │        │
│  │  - Monthly retrain cron task     │        │
│  └──────────────────────────────────┘        │
└──────────────────────────────────────────────┘
```

**Why VPS over cTrader Cloud:** cTrader Cloud sandbox can't host the Python service, forcing a public API split. VPS keeps cBot + ML API + retraining + data storage all on one machine. Same monthly cost, dramatically simpler.

---

## 4. Tech stack

| Layer | Tool |
|-------|------|
| Trading bot | cTrader Automate (cAlgo C# API) |
| Broker | FP Markets cTrader Raw account |
| VPS | Vultr or IONOS, Windows Server, London datacenter, 4GB RAM |
| ML training | Python 3.11, pandas, LightGBM, scikit-learn, mlfinlab (purged CV) |
| Inference API | FastAPI, uvicorn, joblib, NSSM (Windows service wrapper) |
| Version control | Git (GitHub or local) |

---

## 5. Data

- **Source**: FP Markets cTrader historical M5 bars + commission data
- **Range**: Jan 2023 → present (~2.5+ years, ~75k M5 bars per pair)
- **Pairs (v1)**: EURUSD only. GBPUSD added in v1.1 if EURUSD validates.
- **Splits**:
  - Training/CV: Jan 2023 – Sep 2025 (purged walk-forward, 6 folds)
  - Held-out final test: Oct 2025 – Mar 2026 (touch ONCE at the end)
  - Live forward test: Apr 2026 onward
- **Storage**: CSVs on VPS `D:\JCAMP_Data\`, mirrored weekly to laptop via robocopy

---

## 6. Phases

### Phase 1 — DataCollector cBot ✅ v0.1 written

**Deliverable:** `JCAMP_DataCollector.cs` cBot that logs M5 features + triple-barrier labels.

**Features logged (~35):**
- ATR-normalized distance from price to SMA(50/100/200/275) on M5
- ATR-normalized distance to SMA(200) on M15/M30/H1/H4
- 5-bar slope of M5 SMA(200) and H1 SMA(200)
- RSI on M5/M15/M30
- ADX, +DI, -DI on M5
- ATR(14) on M5/M15/H1, ATR ratio M5/H1
- Bollinger Band width (ATR-normalized)
- Last 5 bar bodies and ranges (ATR-normalized)
- Distance to 50-bar swing high/low (ATR-normalized)
- Hour UTC, day of week, session flags (Asia/London/NY)
- Live spread in pips

**Labels (per bar, both directions):**
- `outcome_long` ∈ {win, loss, timeout}
- `bars_to_outcome_long`
- `outcome_short` ∈ {win, loss, timeout}
- `bars_to_outcome_short`
- Triple-barrier params: SL = 1.5×ATR, TP = 3.0×ATR, max 48 bars (4h)
- Pessimistic resolution: if both SL and TP hit in same bar, label as loss

**Tasks:**
- [x] v0.1 cBot written
- [ ] Smoke test on Jan 2023 only — eyeball CSV, check feature ranges, label balance, no NaNs
- [ ] Full backtest run Jan 2023 → today on EURUSD M5
- [ ] Move CSV from VPS to laptop for Phase 2

**Acceptance:**
- ~75,000 rows in CSV
- No NaN/Inf in any feature column
- Label balance: each of {win, loss, timeout} ≥ 10% of rows for both directions
- Feature distributions visually sane (RSI 0–100, distances mostly within ±5 ATR, etc.)

**v0.2 backlog:**
- Add M15/M30 ADX via multi-TF indicator wrapper
- Optimize pending-bar queue removal (O(1) via linked list or index map)

---

### Phase 2 — Python ML pipeline

**Deliverable:** Jupyter notebook + reusable Python module that loads CSV, trains LightGBM, validates with purged walk-forward CV, exports model.

**Project layout:**
```
jcamp_fxscalper_ml/
├── data/                   # CSVs (gitignored)
├── models/                 # trained .joblib files
├── notebooks/
│   ├── 01_eda.ipynb
│   ├── 02_train_baseline.ipynb
│   └── 03_walk_forward.ipynb
├── src/
│   ├── data_loader.py
│   ├── features.py         # any post-processing
│   ├── labels.py           # 3-class → binary collapse helpers
│   ├── cv.py               # purged K-fold wrapper
│   ├── train.py            # main training entrypoint
│   └── evaluate.py         # metrics, equity curves
├── tests/
└── requirements.txt
```

**Tasks:**
- [ ] Set up Python env on laptop (Python 3.11, pandas, lightgbm, mlfinlab, scikit-learn, matplotlib, jupyter)
- [ ] `01_eda.ipynb`: load CSV, summary stats, label balance, feature correlations, drop dead features
- [ ] Implement `cv.PurgedWalkForward` (6 folds, embargo of MaxBarsToOutcome rows between train/test)
- [ ] `02_train_baseline.ipynb`: single LightGBM on 70/30 split, sanity check
- [ ] `03_walk_forward.ipynb`: 6-fold purged CV, report mean OOS metrics
- [ ] Train one model per direction (long_model, short_model) — separate binary classifiers
- [ ] Export to `models/eurusd_long_v1.joblib` and `models/eurusd_short_v1.joblib`

**Acceptance:**
- OOS ROC-AUC > 0.55 averaged across folds (anything ≤0.52 = no edge, abandon and rethink features)
- OOS win rate at chosen threshold > unfiltered baseline by ≥5 pp
- Equity curve simulation (assume fixed 1R risk, 1.5R reward after costs) shows positive expectancy on ≥4 of 6 folds
- Feature importance plot makes economic sense (no single feature dominating >40%, no obvious leakage)

**Overfitting guardrails:**
- Hard rule: never tune hyperparameters on the held-out Oct 2025–Mar 2026 set
- Use early stopping on each fold's validation portion
- Cap LightGBM `num_leaves` at 31, `max_depth` at 6 for v1
- Drop features with importance < 1% in v2 retrain

---

### Phase 3 — FastAPI inference service

**Deliverable:** `predict_service/` FastAPI app that loads model files at startup and serves predictions on `POST /predict`.

**Endpoint contract:**
```
POST http://localhost:8000/predict
Content-Type: application/json

Request:
{
  "symbol": "EURUSD",
  "timestamp": "2026-04-12T14:35:00Z",
  "features": {
    "dist_sma_m5_50": 0.42,
    "dist_sma_m5_100": 0.81,
    ... (all ~35 features)
  }
}

Response:
{
  "p_win_long": 0.62,
  "p_win_short": 0.18,
  "model_version": "eurusd_v1_20260412",
  "latency_ms": 4
}
```

**Tasks:**
- [ ] FastAPI app with `/predict`, `/health`, `/model_info` endpoints
- [ ] Load both long and short models at startup
- [ ] Pydantic validation on request body — reject if any feature missing or NaN
- [ ] Log every prediction to local SQLite for ongoing model evaluation
- [ ] Wrap as Windows service via NSSM, auto-start on VPS boot
- [ ] Healthcheck script

**Acceptance:**
- p99 latency < 50ms (target <10ms typical)
- Service survives cTrader restart, network blip, model file reload
- Prediction log has 100% of cBot's API calls captured

---

### Phase 4 — Trading cBot (FxScalper_ML)

**Deliverable:** `JCAMP_FxScalper_ML.cs` cBot that on each M5 bar close computes the same features as DataCollector, calls `/predict`, and trades when `P(win) > threshold`.

**CRITICAL constraint:** The feature computation code must be **byte-identical** to DataCollector. Train/serve skew is the #1 ML failure mode. Approach: extract feature logic into shared `JCAMP_Features.cs` file, copy into both bot folders. Add a unit test (Phase 4.5) that runs both bots on the same backtest range and asserts feature CSVs match exactly.

**Risk management (calibrated for $500 starting capital):**
- Position size: 1% account risk per trade → ~0.03 lots on EURUSD with 1.5×ATR stop
- Daily loss limit: -2R (was -3R in v4.5.x — tightened for small account)
- Monthly DD limit: 8% (was 10% — tightened for small account)
- Consecutive loss limit: 6 (was 9 — tightened)
- Close all on monthly DD hit: yes
- Min ML threshold: tunable parameter, default `p_win > 0.55`

**Tasks:**
- [ ] Extract shared `JCAMP_Features.cs`
- [ ] Refactor DataCollector to use shared feature module
- [ ] Build FxScalper_ML cBot with HTTP client to localhost:8000
- [ ] Risk management module ported from v4.5.x with new limits
- [ ] Backtest on held-out Oct 2025 – Mar 2026 (single use of holdout!)
- [ ] Demo forward test for 2 weeks
- [ ] Live with $500 on FP Markets

**Acceptance:**
- Backtest on holdout set: positive R, profit factor > 1.3, max DD < 8%
- Demo forward test results within ±20% of backtest expectations
- Zero unhandled exceptions over 2-week demo run

---

### Phase 5 — Operations & monitoring

- [ ] Monthly retrain cron task (Windows Task Scheduler) — pulls last 9 months of new data, retrains, swaps model file, FastAPI hot-reloads
- [ ] Weekly equity curve report emailed to JCamp
- [ ] Drift detection: alert if live `p_win` distribution differs from training distribution by >15% (KS test)
- [ ] Backup: daily robocopy `D:\JCAMP_Data` and `D:\JCAMP_Models` to laptop or B2

---

## 7. Risk register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Train/serve feature skew | High | Catastrophic | Shared feature module + CSV diff test |
| Overfitting to 2023-2025 regime | Medium | High | Purged walk-forward CV; held-out test set; monthly retraining |
| Costs eat ML edge on $500 | Medium | High | Use FP Markets Raw (commission-based, lower total); require min RR=2 in label |
| VPS outage during live | Low | Medium | $500 cap = manageable; monitoring + auto-restart |
| ROC-AUC ≤ 0.52 (no real edge) | Medium | High | Abandon Phase 4 honestly; revisit features or pair selection |
| Live results diverge from backtest | Medium | High | Demo forward test before live; ±20% tolerance gate |

---

## 8. Open questions

- Multi-pair model: per-pair models (Option A) vs pooled with symbol features (Option B) — defer until EURUSD validates, then test both on GBPUSD
- News filter: should we block trading 30 min around high-impact news? Probably yes, add as a feature in v2 (`minutes_to_next_high_impact_news`)
- Model versioning: timestamped filenames + symlink to "current"? Or in-DB version registry? Decide in Phase 3

---

## 9. Definition of done (v1)

- [ ] DataCollector logged ≥75k clean rows for EURUSD
- [ ] LightGBM model with OOS ROC-AUC > 0.55 on purged walk-forward
- [ ] FastAPI service running as Windows service on VPS
- [ ] FxScalper_ML cBot live on FP Markets with $500
- [ ] 30 days unattended live trading completed
- [ ] Live R-multiple within ±20% of backtest expectation

---

## 10. Working notes for Claude Code

When resuming work on this project, Claude Code should:
1. Read this PRD first
2. Check `STATUS.md` (to be created in repo) for the current phase and last completed task
3. Never touch files outside the current phase without explicit permission
4. Always run the smoke test (Jan 2023 single-month) after any change to DataCollector before doing a full historical run
5. Never tune hyperparameters using the held-out Oct 2025–Mar 2026 data — that set is touched exactly once at end of Phase 2
6. Keep feature definitions in ONE place (`JCAMP_Features.cs` once Phase 4 starts) — do not duplicate
7. Prefer small, reviewable commits over large refactors
