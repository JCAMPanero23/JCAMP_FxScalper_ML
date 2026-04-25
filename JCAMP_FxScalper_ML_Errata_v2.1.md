# JCAMP FxScalper ML — Plan v2.0 Errata & Hotfixes

**Version 2.1 | April 19, 2026 | APPLY BEFORE CONTINUING ANY WORK**

---

> **⛔ STOP. Read this entire document before writing any more code.**
>
> This errata supersedes Plan v2.0 wherever they conflict. The v2.0 plan has been partially implemented by Claude Code. This document identifies 8 issues found during post-implementation audit. Issue #1 is a silent feature corruption bug. Issues #2 and #5 will produce wrong numbers that look correct. All 8 must be fixed before any further work proceeds.
>
> **Execution order: Fix issues in the sequence specified at the end of this document. Then re-run the v2.0 plan from Step 0.**

---

## Issue Summary

| # | Issue | Severity | Impact If Missed |
|---|-------|----------|-----------------|
| 1 | Features not updated during open trades | **CRITICAL** | Silent feature corruption, wrong re-scores |
| 2 | DataCollector re-run range too narrow | **CRITICAL** | No holdout data for simulate.py |
| 3 | Holdout "spent" status blocks simulate.py | **HIGH** | Claude Code refuses to run Step 2 |
| 4 | Risk parameter contradictions (DD%, consec) | **HIGH** | Simulator vs cBot mismatch, Gate 1 fail |
| 5 | R-multiple values wrong (2R should be 3R) | **HIGH** | All metrics off by ~50% |
| 6 | Walk-forward fold count: 5 vs 6 | **MEDIUM** | CV results inconsistent with prior runs |
| 7 | +2R milestone detection method unspecified | **MEDIUM** | Simulator vs cBot timing mismatch |
| 8 | Model filename v2 should be v05 | **LOW** | File not found error |

---

## Issue #1 — Features Not Updated During Open Trades

**Severity: CRITICAL**

> **BUG:** This is a silent data corruption bug. Features will be wrong on every re-score and on the first bar after every trade closes. If Claude Code has already implemented OnBar() with the v2.0 structure, it MUST be restructured.

### The Bug

The v2.0 plan OnBar() structure skips feature computation when a position is open:

```csharp
// v2.0 PLAN (BUGGY)
protected override void OnBar()
{
    if (HasOpenPosition())
    {
        ManageOpenTrade();
        return;  // <-- SKIPS FeatureComputer.Compute()
    }

    // Features only computed here
    var features = FeatureComputer.Compute(...);
    // ... entry logic ...
}
```

### Why This Breaks Things

The FeatureComputer has stateful internal fields that accumulate bar-by-bar:

- **atr_percentile_2000bar:** Uses a 2000-bar ring buffer. Skipping bars creates gaps in the rolling window, producing wrong percentile values.
- **mtf_alignment_duration:** Counts consecutive bars of alignment. Skipping bars resets or freezes the count.
- **bars_since_tf_fast_flip:** Increments every bar. Skipping bars produces stale values.

If a trade is open for 20 bars, these three features are 20 bars stale when the +2R re-score happens. The first bar after the trade closes also uses corrupted state. This means every simulation and every live prediction during or after a trade produces wrong features silently.

### The Fix

Feature computation must happen UNCONDITIONALLY at the top of OnBar(), before any position check:

```csharp
// v2.1 FIX (CORRECT)
protected override void OnBar()
{
    // ALWAYS compute features first
    // Stateful trackers need every bar without gaps
    var features = FeatureComputer.Compute(this, Bars, indicators);

    // Then branch on position state
    if (HasOpenPosition())
    {
        ManageOpenTrade(features);  // pass features in
        return;
    }

    if (!RiskModule.CanTrade()) return;
    if (GetOpenPositionCount(Symbol.Name) >= MaxPositionsPerSymbol) return;

    var pWin = PredictAPI.GetPWinLong(features);
    if (pWin >= EntryThreshold)
        OpenLongPosition(features.ATR);
}
```

**ManageOpenTrade signature changes:** It now receives the pre-computed features as a parameter. The +2R re-score uses these features directly instead of calling Compute() a second time. This guarantees features are fresh AND computed exactly once per bar.

```csharp
void ManageOpenTrade(Dictionary<string, double> features)
{
    var state = CurrentTradeState;
    state.BarsOpen++;

    if (state.BarsOpen >= TimeoutBars)
    { ClosePosition(); return; }

    if (!state.BreakevenMoved && GetCurrentProfitR() >= 2.0)
    {
        MoveStopToBreakeven();
        state.BreakevenMoved = true;

        // Use ALREADY-COMPUTED features from this bar
        var pWin = PredictAPI.GetPWinLong(features);
        if (pWin >= ExtensionThreshold && !state.TPExtended)
        {
            ExtendTP(TpExtendedAtrMult);
            state.TPExtended = true;
        }
    }
}
```

### Apply to simulate.py Too

The Python TradeSim must also update feature state on every bar, including bars where a position is open. If simulate.py reads ML scores from a pre-computed DataFrame (indexed by timestamp), the feature state is already handled by the training pipeline. But verify that the scores DataFrame contains a score for EVERY bar, not just bars where no position was open.

---

## Issue #2 — DataCollector Re-Run Range Too Narrow

**Severity: CRITICAL**

> **BUG:** Step 0 in v2.0 says "Run full backtest Jan 2023 to Sep 2025." This omits the holdout period. simulate.py cannot run on Oct 2025 to Mar 2026 without new labels for those bars.

### The Problem

The v2.0 plan Step 0 instructs: "Run full backtest Jan 2023 to Sep 2025 on EURUSD M5."

But Step 2 (simulate.py) requires: "Run on full holdout set (Oct 2025 to Mar 2026)."

The holdout bars need new labels with TP=4.5×ATR. If the DataCollector only runs through Sep 2025, there are zero 4.5×ATR labels for the holdout period. simulate.py has nothing to validate against.

### The Fix

> **FIX REQUIRED:** Change Step 0 to: "Run full backtest Jan 2023 to present (including holdout period through Mar 2026). The train/CV vs holdout split is enforced in Python, not by limiting the DataCollector run."

The DataCollector generates one CSV covering the full date range. Python splits it:

- **Train/CV:** Jan 2023 to Sep 2025 (for Step 1 retraining)
- **Holdout:** Oct 2025 to Mar 2026 (for Step 2 simulate.py)
- **Live forward:** Apr 2026 onward (not used yet)

---

## Issue #3 — Holdout "Spent" Status Blocks simulate.py

**Severity: HIGH**

### The Problem

STATUS.md says the holdout (Oct 2025 to Mar 2026) is SPENT from the v04 test. Claude Code reads STATUS.md and may refuse to run simulate.py on that period.

### Why This Is a New Experiment

The v04 holdout tested a model trained on TP=3.0×ATR labels. The v05 retrain uses TP=4.5×ATR labels. The outcome variable itself has changed. This is not retesting the same hypothesis. It is a new experiment that covers the same calendar dates with a fundamentally different question.

### The Fix

> **FIX REQUIRED:** Update STATUS.md with the following note BEFORE running Step 2:

```markdown
## Holdout Status

v04 holdout (TP=3.0×ATR labels): SPENT on 2026-04-18.
Results: +0.749R, PF 2.82, 422 trades.

v05 holdout (TP=4.5×ATR labels): AVAILABLE.
The barrier parameters changed, making the outcome variable
fundamentally different. The v05 model answers a different
question than v04. This constitutes a new experiment.

RULE: v05 holdout is still single-use.
Touch ONCE with simulate.py. Do not re-run after seeing results.
```

---

## Issue #4 — Risk Parameter Contradictions

**Severity: HIGH**

### The Problem

Three sources give conflicting risk parameter values:

| Source | Monthly DD / Consec Loss Limit |
|--------|-------------------------------|
| Original PRD | 8% / 6 |
| Phase 4 spec (after holdout analysis) | 6% / 8 |
| Plan v2.0 (partially implemented) | 8% / 6 |

The Phase 4 spec values were chosen for specific reasons:

- **Monthly DD 6%:** LONG-only on $500 means less diversification. Tighter DD protection is warranted.
- **Consec loss limit 8:** The v04 holdout showed max consecutive losses of 16. Setting the limit at 6 triggers constant false pauses during normal losing streaks. 8 gives breathing room while still providing a circuit breaker.

### The Fix

> **FIX REQUIRED:** Use these values consistently in ALL three locations:

| Parameter | Correct Value |
|-----------|--------------|
| MonthlyDDLimitPct | **6.0** |
| ConsecLossLimit | **8** |
| DailyLossLimitR | 2.0 (unchanged) |
| RiskPerTradePct | 1.0 (unchanged) |

**Update in:** (1) simulate.py TradeSim defaults, (2) JCAMP_FxScalper_ML.cs cBot parameter defaults, (3) any entry gate code block that references these values.

---

## Issue #5 — R-Multiple Values Wrong

**Severity: HIGH**

### The Problem

The RR changed from 1:2 to 1:3, but code may still use the old mapping:

```python
# OLD (v04): TP=3.0×ATR / SL=1.5×ATR = 2.0R on win
r_map = {"win": 2.0, "loss": -1.0, "timeout": 0.0}

# NEW (v05): TP=4.5×ATR / SL=1.5×ATR = 3.0R on win
# Extended:  TP=6.0×ATR / SL=1.5×ATR = 4.0R on win
```

If any script uses `win=+2R` instead of `win=+3R`, all reported metrics are wrong by ~50% on the upside.

### Correct Values

| Outcome | Old v04 R | New v05 R |
|---------|-----------|-----------|
| Win (TP at 4.5×ATR) | +2.0R | **+3.0R** |
| Win extended (TP at 6.0×ATR) | N/A | **+4.0R** |
| Loss (SL at 1.5×ATR) | -1.0R | -1.0R (unchanged) |
| Timeout (close at market) | 0.0R | variable (actual P&L from price) |

### The Fix

#### In walk-forward CV and holdout evaluation scripts

These use label-based R assignment (they look up `outcome_long` from the CSV):

```python
# CORRECT for v05
r_map = {"win": 3.0, "loss": -1.0, "timeout": 0.0}
```

#### In simulate.py

Do NOT use a label lookup. Calculate R from actual trade price:

```python
if sl_hit:
    r = -1.0
elif tp_hit and not extended:
    r = 3.0   # TP 4.5×ATR / SL 1.5×ATR
elif tp_hit and extended:
    r = 4.0   # TP 6.0×ATR / SL 1.5×ATR
elif timeout:
    # Close at market price
    pips_from_entry = (close - entry) * direction
    r = pips_from_entry / sl_pips  # variable R
```

> **FIX REQUIRED:** Search the ENTIRE codebase for the number 2.0 in context of R-multiple or reward mapping. Every instance must be verified. Command: `grep -rn "2\.0" src/ notebooks/ --include="*.py" --include="*.ipynb"`

#### Gate A criteria note

The old Gate A expectancy threshold of +0.09R was calibrated for 2:1 R/R. With 3:1 R/R, the baseline expectancy for a random model is different. However, the threshold should stay at +0.09R because it represents the minimum edge worth deploying, not a function of the R/R ratio. A model that makes +0.09R per trade at 3:1 R/R is still profitable.

---

## Issue #6 — Walk-Forward Fold Count: 5 vs 6

**Severity: MEDIUM**

### The Problem

The PRD says "6 folds." All actual results reference 5 folds ("4/5 positive folds", "3/5"). The v2.0 plan says "same 6 folds" which contradicts the implementation.

### The Fix

> **FIX REQUIRED:** Check cv.py for the actual `n_splits` value. Use whatever is in the code. Do not change it. Based on all historical results, it is 5 folds. Read the v2.0 plan reference to "6 folds" as "same fold count as existing CV implementation."

**Verify:** `grep -n "n_splits\|n_folds\|num_splits" src/cv.py`

---

## Issue #7 — +2R Milestone Detection Method

**Severity: MEDIUM**

### The Problem

The +2R check is not specified as using bar CLOSE or bar HIGH. Different methods cause the milestone to trigger on different bars between simulate.py and the cBot, breaking Gate 1 matching.

### The Fix

> **FIX REQUIRED:** Both simulate.py and cBot must use BAR CLOSE for the +2R milestone check.

Rationale: The cBot runs OnBar() at bar close only. Using bar HIGH in simulate.py would trigger earlier than the cBot can, causing systematic mismatch.

```python
# simulate.py -- +2R uses CLOSE
profit_r = (bar.close - pos.entry_price) * direction / sl_distance
if profit_r >= 2.0 and not pos.breakeven_moved:
    # trigger milestone
```

```csharp
// cBot -- consistent with simulate.py
double currentR = (Bars.ClosePrices.LastValue - state.EntryPrice)
                  * (state.Direction == "LONG" ? 1 : -1)
                  / state.SLDistance;
if (currentR >= BEtriggerR && !state.BreakevenMoved)
{
    // trigger milestone
}
```

### Important distinction

SL/TP HIT detection is different from the +2R milestone check:

- **SL/TP hit detection:** Uses bar HIGH and LOW (intrabar). Pessimistic: if both hit same bar, SL wins. Same as DataCollector.
- **+2R milestone:** Uses bar CLOSE only. Matches cBot OnBar() timing.

These are two different checks with two different data sources. Do not conflate them.

---

## Issue #8 — Model Filename

**Severity: LOW**

### The Problem

The v2.0 plan references `eurusd_long_v2.joblib`. The versioning convention uses v0.x. Current model is v04. Next is v05.

### The Fix

| Location | Change |
|----------|--------|
| Step 1 acceptance | `eurusd_long_v2.joblib` → `eurusd_long_v05.joblib` |
| Section 6 table | `eurusd_long_v2` → `eurusd_long_v05` |
| FastAPI config.py MODEL_VERSION | `eurusd_long_v04_20260418` → `eurusd_long_v05_YYYYMMDD` |
| FastAPI config.py LONG_MODEL_PATH | Update path to v05 file |

**Atomic swap:** When deploying v05 to FastAPI, update the .joblib file, the version string in config.py, and restart the service as one step. Not three separate commits.

---

## Execution Order

Apply fixes in this order, then resume v2.0 plan from Step 0:

| Order | Action |
|-------|--------|
| 1. Fix #8 | Rename model file references: v2 → v05. |
| 2. Fix #6 | Verify fold count in cv.py. Note actual value. |
| 3. Fix #4 | Update risk params: monthly DD=6%, consec loss=8. In simulate.py AND cBot. |
| 4. Fix #5 | Update ALL R-multiple mappings: win=3.0R, not 2.0R. Search entire codebase. |
| 5. Fix #2 | Change DataCollector run range to Jan 2023 → present (full range). |
| 6. Fix #3 | Update STATUS.md: v05 holdout is AVAILABLE (new experiment). |
| 7. Fix #1 | Restructure OnBar(): features computed unconditionally at top. Pass to ManageOpenTrade(). Apply same in simulate.py. |
| 8. Fix #7 | Verify +2R uses bar CLOSE. Verify SL/TP uses HIGH/LOW. Both systems. |
| 9. Resume | Re-run v2.0 plan from Step 0 with corrected DataCollector range. |

---

## Appendix: Re-Score Semantics at +2R

This is not a bug, but Claude Code must understand what the re-score means.

When the model re-scores at +2R, it answers: **"If I entered a NEW long at this bar, would it hit TP=4.5×ATR before SL=1.5×ATR?"** It does NOT answer: "Should I hold my existing position?"

This is a deliberate design choice. The model is used as a regime quality indicator. High p_win at +2R means "conditions are still favorable for longs" so extending TP is justified. Low p_win means conditions have deteriorated, so the conservative path (keep original TP, lock breakeven stop) is correct.

The model has no knowledge of the existing position, floating P&L, or entry price. It scores current bar features only. This is intentional for v1. A position-aware trade management model would be a separate future project.

---

*End of Errata v2.1 | April 19, 2026 | Owner: JCamp*
