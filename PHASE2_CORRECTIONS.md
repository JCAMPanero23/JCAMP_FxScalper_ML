# Phase 2 Review — Bugs Found & Required Corrections

> **For:** Claude Code session working on `jcamp_fxscalper_ml`
> **Context:** Review of `notebooks/02_train_baseline.ipynb` and the walk-forward results from `notebooks/03_walk_forward.ipynb`.
> **Status:** 🔴 **Do NOT proceed to Phase 3 until all three bugs below are fixed and the walk-forward notebook is re-run.**
> **Priority:** High — current headline metrics are misleading and will cause incorrect go/no-go decisions.

---

## TL;DR

The equity curve in notebook 02 is trustworthy and shows a real edge. But **two separate bugs** in the trading metrics calculation and hyperparameter tuning code are producing headline numbers (PF 4.25, 68% win rate) that do not reflect the model's actual performance. Before proceeding to Phase 3 we need to:

1. Fix `calculate_trading_metrics()` to use probabilities + a real threshold
2. Re-run the walk-forward notebook with the fix
3. Add a threshold sensitivity plot to confirm the edge is robust (plateau) rather than fragile (peak)
4. Fix the broken SHORT hyperparameter tuning cell
5. Update the PRD acceptance criteria to reflect trading-relevant metrics, not ROC-AUC

---

## Bug 1 — `calculate_trading_metrics()` is trading every bar, not filtered signals 🚨

### Where

`src/evaluate.py` → function `calculate_trading_metrics()`
Called from `notebooks/02_train_baseline.ipynb` cell "## 5. Trading Simulation - LONG"

### Current behavior (wrong)

```python
y_pred = model_long.predict(X_test)   # returns 0/1 class labels at threshold=0.5
trading_metrics = calculate_trading_metrics(
    y_test.values,
    y_pred,
    risk_reward=2.0,
    commission_pips=0.0
)
```

This reports `total_trades: 61232` — which is the **entire test set size**, not the number of trades the model would actually take. The function is computing win rate and profit factor over *every bar in the test set* rather than over bars where the model has confidence `p > threshold`.

### Why this matters

The whole premise of the ML filter is that we trade only bars where `P(win) > threshold`. A threshold of 0.5 is not a filter — it's "any bar the model leans bullish on" — and doesn't match how the live `FxScalper_ML` cBot will make decisions. The headline numbers (PF 4.25, win rate 68%, expectancy 1.04R) are therefore **not the model's trading edge**. They're a statistical artifact of how `.predict()` interacts with the base rate of the dataset.

Evidence this is wrong:

- `simulate_equity_curve()` in the same notebook shows ~2,800 trades with +361R final P&L over the same test window
- `calculate_trading_metrics()` claims 61,232 trades with +63,658R P&L
- Those two numbers are from the same data with different logic — they must agree when computed correctly

The equity curve function is the honest one. The trading metrics function is buggy.

### Fix

Rewrite `calculate_trading_metrics()` to accept probabilities and a threshold, and only count trades where the probability crosses the threshold. It should also accept a `commission_r` parameter (cost as a fraction of R, e.g., `0.04` = 4% of 1R) so costs are modeled correctly.

**New signature:**

```python
def calculate_trading_metrics(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    threshold: float = 0.55,
    risk_reward: float = 2.0,
    commission_r: float = 0.0,
) -> dict:
    """
    Calculate trading metrics for a probability-based entry filter.

    Only counts trades where y_pred_proba >= threshold. For each such trade,
    a win returns +risk_reward R and a loss returns -1 R, minus commission_r
    applied to every trade.

    Returns a dict with: total_trades, wins, losses, win_rate, profit_factor,
    expectancy_r, net_profit_r, gross_profit_r, gross_loss_r, selection_rate
    (fraction of bars that became trades), avg_threshold_used.
    """
    # Filter to high-confidence bars only
    selected = y_pred_proba >= threshold
    n_total_bars = len(y_true)
    n_trades = int(selected.sum())

    if n_trades == 0:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "expectancy_r": 0.0,
            "net_profit_r": 0.0,
            "gross_profit_r": 0.0,
            "gross_loss_r": 0.0,
            "selection_rate": 0.0,
            "threshold_used": float(threshold),
        }

    y_selected = y_true[selected]
    wins = int((y_selected == 1).sum())
    losses = int((y_selected == 0).sum())

    # P&L per trade, net of commission
    gross_profit_r = wins * risk_reward - wins * commission_r
    gross_loss_r = losses * 1.0 + losses * commission_r
    net_profit_r = gross_profit_r - gross_loss_r

    win_rate = wins / n_trades
    profit_factor = (
        gross_profit_r / gross_loss_r if gross_loss_r > 0 else float("inf")
    )
    expectancy_r = net_profit_r / n_trades

    return {
        "total_trades": n_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 4),
        "profit_factor": round(profit_factor, 4),
        "expectancy_r": round(expectancy_r, 4),
        "net_profit_r": round(net_profit_r, 2),
        "gross_profit_r": round(gross_profit_r, 2),
        "gross_loss_r": round(gross_loss_r, 2),
        "selection_rate": round(n_trades / n_total_bars, 4),
        "threshold_used": float(threshold),
    }
```

### Update call site in notebook 02

Replace the cell "## 5. Trading Simulation - LONG" with:

```python
# Get probabilities (not class labels)
y_pred_proba = model_long.predict_proba(X_test)[:, 1]

# Evaluate at multiple thresholds so we see the full picture
print("LONG model — trading metrics at various thresholds:\n")
print(f"{'threshold':>10} {'trades':>8} {'win_rate':>9} {'pf':>7} "
      f"{'expectancy':>11} {'net_R':>10}")
print("-" * 60)

for thr in [0.50, 0.55, 0.60, 0.65, 0.70]:
    m = calculate_trading_metrics(
        y_test.values,
        y_pred_proba,
        threshold=thr,
        risk_reward=2.0,
        commission_r=0.04,   # ~4% of R — approx FP Markets Raw cost at $500 / 1% risk
    )
    print(f"{thr:>10.2f} {m['total_trades']:>8} {m['win_rate']:>9.2%} "
          f"{m['profit_factor']:>7.2f} {m['expectancy_r']:>11.3f} "
          f"{m['net_profit_r']:>10.1f}")
```

This gives a table showing how the model behaves across threshold choices. Do the same for the SHORT model.

---

## Bug 2 — SHORT hyperparameter tuning cell is fake 🚨

### Where

`notebooks/02_train_baseline.ipynb` → "Attempting Hyperparameter Tuning" cell

### Evidence

Output shows:

```
LONG tuned:  ROC-AUC 0.5461, Accuracy 0.6771, Predicted win% 6.9%
SHORT tuned: ROC-AUC 0.5461, Accuracy 0.6771, Predicted win% 6.9%
```

**These numbers are identical to 4 decimal places.** That's not plausible for two independently trained models on two different label sets. The SHORT cell is almost certainly evaluating the LONG model, or training on the LONG labels, due to a variable scope / copy-paste issue in the notebook.

The summary line `SHORT: 0.5462 -> 0.5461 (-0.0001)` is meaningless and should not be used to make any decisions.

### Fix

Restructure the tuning cell so LONG and SHORT are fully isolated. Use distinct variable names and re-derive splits from the correct label dataframe:

```python
# --- Tuned LONG ---
X_long = df_long[features]
y_long = df_long['label']
X_long_tr, X_long_te, y_long_tr, y_long_te = train_test_split(
    X_long, y_long, test_size=0.3, random_state=42, shuffle=False
)
X_long_tr_sub, X_long_val, y_long_tr_sub, y_long_val = train_test_split(
    X_long_tr, y_long_tr, test_size=0.2, random_state=42, shuffle=False
)

print("Training tuned LONG...")
model_long_tuned = train_lightgbm(
    X_long_tr_sub, y_long_tr_sub, X_long_val, y_long_val, params=params_tuned
)
metrics_long_tuned = evaluate_model(model_long_tuned, X_long_te, y_long_te, verbose=True)

# --- Tuned SHORT (completely separate) ---
X_short = df_short[features]
y_short = df_short['label']
X_short_tr, X_short_te, y_short_tr, y_short_te = train_test_split(
    X_short, y_short, test_size=0.3, random_state=42, shuffle=False
)
X_short_tr_sub, X_short_val, y_short_tr_sub, y_short_val = train_test_split(
    X_short_tr, y_short_tr, test_size=0.2, random_state=42, shuffle=False
)

print("Training tuned SHORT...")
model_short_tuned = train_lightgbm(
    X_short_tr_sub, y_short_tr_sub, X_short_val, y_short_val, params=params_tuned
)
metrics_short_tuned = evaluate_model(model_short_tuned, X_short_te, y_short_te, verbose=True)
```

**Sanity check after re-running:** the two AUC values should NOT be identical. If they still are, there's a deeper bug — investigate further before moving on.

---

## Bug 3 — Walk-forward notebook likely inherits Bug 1

### Where

`notebooks/03_walk_forward.ipynb` — wherever the walk-forward loop calls `calculate_trading_metrics()` per fold.

### Why this matters

The walk-forward result Claude Code reported — "5/6 folds profitable, PF 3.1–4.4, expectancy 0.95R" — is suspiciously similar in magnitude to Bug 1's inflated numbers from notebook 02. If notebook 03 also uses `.predict()` (class labels at 0.5) instead of `.predict_proba()` + threshold, **the walk-forward metrics are inflated by the same bug**.

### Fix

After fixing Bug 1 in `src/evaluate.py`:

1. Audit `notebooks/03_walk_forward.ipynb` for every call to `calculate_trading_metrics()`
2. Ensure every call passes `y_pred_proba` (not `y_pred`) and an explicit `threshold`
3. Re-run the full walk-forward at threshold = 0.55, 0.60, 0.65 (do three passes)
4. Report the **honest** per-fold metrics at each threshold

**Expected outcome:** the absolute numbers will be smaller than originally reported. That's fine — what matters is:

- Is the edge still positive in most folds?
- Is it stable across thresholds?
- Is the trade count per fold ≥ 100?

If yes to all three, the edge is real. The original PF of 3.1–4.4 was inflated, but a corrected PF of 1.3–1.8 with stable thresholds and consistent fold profitability is a perfectly valid trading edge — in fact, more believable and more likely to hold in live trading.

---

## New requirement — Threshold sensitivity plot

### Why

The PRD originally used ROC-AUC > 0.55 as the Phase 2 acceptance gate. The LONG model returned 0.5366 and SHORT 0.5462 — both below threshold. But AUC measures overall ranking quality, while our strategy only uses the confident tail. The equity curve shows the tail *is* profitable, so AUC is the wrong metric to gate on.

We need a better gate: **threshold stability**. A real edge shows a broad, flat plateau of positive expectancy across many thresholds. A fragile overfit shows a sharp peak at one specific threshold. The plot distinguishes these two cases visually.

### Implementation

Add a new function to `src/evaluate.py`:

```python
def plot_threshold_sensitivity(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    risk_reward: float = 2.0,
    commission_r: float = 0.04,
    thresholds: np.ndarray = None,
    title: str = "Threshold Sensitivity",
):
    """
    Plot how trade count, win rate, profit factor, and expectancy vary across
    probability thresholds. A robust edge shows a wide plateau of positive
    expectancy. An overfit edge shows a sharp peak.
    """
    import matplotlib.pyplot as plt

    if thresholds is None:
        thresholds = np.arange(0.40, 0.81, 0.01)

    rows = []
    for thr in thresholds:
        m = calculate_trading_metrics(
            y_true, y_pred_proba,
            threshold=thr,
            risk_reward=risk_reward,
            commission_r=commission_r,
        )
        rows.append({
            "threshold": thr,
            "n_trades": m["total_trades"],
            "win_rate": m["win_rate"],
            "profit_factor": m["profit_factor"],
            "expectancy_r": m["expectancy_r"],
            "net_profit_r": m["net_profit_r"],
        })

    df = pd.DataFrame(rows)

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    fig.suptitle(title, fontsize=14)

    axes[0, 0].plot(df["threshold"], df["n_trades"], marker=".")
    axes[0, 0].set_xlabel("Threshold")
    axes[0, 0].set_ylabel("Trade count")
    axes[0, 0].set_title("Trades taken vs threshold")
    axes[0, 0].grid(alpha=0.3)

    axes[0, 1].plot(df["threshold"], df["win_rate"], marker=".", color="green")
    axes[0, 1].axhline(1 / (1 + risk_reward), ls="--", color="gray",
                       label=f"Breakeven (RR={risk_reward})")
    axes[0, 1].set_xlabel("Threshold")
    axes[0, 1].set_ylabel("Win rate")
    axes[0, 1].set_title("Win rate vs threshold")
    axes[0, 1].legend()
    axes[0, 1].grid(alpha=0.3)

    axes[1, 0].plot(df["threshold"], df["profit_factor"], marker=".", color="purple")
    axes[1, 0].axhline(1.0, ls="--", color="red", label="PF = 1 (breakeven)")
    axes[1, 0].axhline(1.3, ls="--", color="orange", label="PF = 1.3 (target)")
    axes[1, 0].set_xlabel("Threshold")
    axes[1, 0].set_ylabel("Profit factor")
    axes[1, 0].set_title("Profit factor vs threshold")
    axes[1, 0].legend()
    axes[1, 0].grid(alpha=0.3)

    axes[1, 1].plot(df["threshold"], df["expectancy_r"], marker=".", color="navy")
    axes[1, 1].axhline(0, ls="--", color="red")
    axes[1, 1].set_xlabel("Threshold")
    axes[1, 1].set_ylabel("Expectancy (R per trade)")
    axes[1, 1].set_title("Expectancy vs threshold")
    axes[1, 1].grid(alpha=0.3)

    plt.tight_layout()
    return fig, df
```

### Usage (add to notebook 02 after the fix)

```python
fig, sens_df = plot_threshold_sensitivity(
    y_test.values,
    y_pred_proba,
    risk_reward=2.0,
    commission_r=0.04,
    title="LONG — Threshold Sensitivity (70/30 hold-out)",
)
plt.show()

# Identify the stable profitable region
profitable = sens_df[(sens_df["expectancy_r"] > 0) & (sens_df["n_trades"] > 100)]
print(f"\nProfitable threshold range: "
      f"{profitable['threshold'].min():.2f} to {profitable['threshold'].max():.2f}")
print(f"Width of profitable plateau: "
      f"{profitable['threshold'].max() - profitable['threshold'].min():.2f}")
```

### How to interpret

- **Plateau width ≥ 0.10** (e.g., profitable from 0.55 to 0.68) → robust edge, proceed
- **Plateau width 0.04–0.09** → mild edge, borderline, proceed with caution
- **Plateau width < 0.04** → fragile / overfit, do not proceed, revisit features

Do the same plot for SHORT.

---

## PRD update — replace the AUC gate

The PRD currently says (Phase 2, Acceptance):

> OOS ROC-AUC > 0.55 averaged across folds (anything ≤0.52 = no edge, abandon and rethink features)

Replace with:

> **Phase 2 acceptance — trading-relevant gates (ALL must pass):**
>
> 1. **Fold consistency:** ≥ 5 of 6 walk-forward folds show positive net R at the chosen production threshold
> 2. **Sample size:** Each fold has ≥ 100 trades taken at the chosen production threshold
> 3. **Threshold stability:** Profitable plateau width ≥ 0.08 (positive expectancy across a threshold band of at least 0.08)
> 4. **Realistic expectancy:** Mean OOS expectancy ≥ 0.10R per trade after modeling commission (commission_r = 0.04)
> 5. **Feature sanity:** No single feature contributes > 40% of total importance; top feature importance must be economically interpretable (no obvious leakage candidates)
> 6. **Equity curve shape:** Per-fold equity curves show persistent climb rather than single large winners; maximum fold-level drawdown < 30% of peak equity
>
> ROC-AUC is no longer a hard gate but should be reported for reference. Values in the 0.52–0.56 range are acceptable IF the six gates above pass.

---

## Execution checklist for Claude Code

Work through these in order. Do not skip ahead.

- [ ] **Step 1** — Replace `calculate_trading_metrics()` in `src/evaluate.py` with the new implementation (Bug 1 fix)
- [ ] **Step 2** — Add `plot_threshold_sensitivity()` to `src/evaluate.py`
- [ ] **Step 3** — Update notebook 02 "Trading Simulation" cells (LONG and SHORT) to use probabilities + multi-threshold table + sensitivity plot
- [ ] **Step 4** — Fix the SHORT hyperparameter tuning cell in notebook 02 (Bug 2 fix). Sanity check: LONG and SHORT tuned AUCs must NOT be identical
- [ ] **Step 5** — Audit notebook 03 (walk-forward) for any call to `calculate_trading_metrics()` — update every call to pass probabilities and an explicit threshold
- [ ] **Step 6** — Re-run notebook 03 fully. Report per-fold metrics at thresholds 0.55, 0.60, 0.65
- [ ] **Step 7** — Generate threshold sensitivity plots for both LONG and SHORT on the walk-forward aggregated predictions
- [ ] **Step 8** — Evaluate against the 6 new acceptance gates. Document pass/fail for each, per direction
- [ ] **Step 9** — Update `PRD.md` Phase 2 acceptance section with the new gates
- [ ] **Step 10** — Update `STATUS.md` with results and go/no-go decision for Phase 3

---

## What I expect the honest results to look like

Based on the equity curve in notebook 02 showing +361R over ~2,800 trades:

- True expectancy: **~0.13R per trade** (not 0.95R as originally reported)
- True win rate at 0.55 threshold: likely **45–55%** (not 68%)
- True profit factor: likely **1.3–1.8** at stable thresholds (not 3.1–4.4)
- Trades per month after filtering: probably **30–80** (depending on threshold)

These are **still tradeable numbers** for a $500 starting account, and they're numbers you can actually trust. The original headline figures were inflated by Bug 1 — the edge itself is probably real, just smaller than first reported.

If the corrected walk-forward shows 5/6 folds profitable with PF ≥ 1.3 and a plateau ≥ 0.08 wide, proceed to Phase 3 with confidence. If it doesn't, the honest answer is that feature engineering is needed before a trading bot gets built.

---

## Notes for future prevention

Add these to `CLAUDE.md` in the project root so Claude Code doesn't repeat these mistakes:

1. **Never use `model.predict()` for trading simulation.** Always use `model.predict_proba()` and an explicit threshold. `.predict()` is only for classification accuracy metrics, not for trading decisions.
2. **Any function named `calculate_trading_metrics` or similar must accept a threshold.** If it doesn't, it's wrong.
3. **Always model commission.** Even if costs seem small, a "free" backtest inflates edge by exactly the amount of the cost. Default to `commission_r = 0.04` for FP Markets Raw at 1% risk on $500.
4. **When training two models (LONG and SHORT), always sanity-check that their metrics are not identical.** Identical numbers to 4 decimal places is a scope bug, not a coincidence.
5. **AUC is not a trading metric.** It measures ranking quality across the whole distribution. For filtered entry strategies, expectancy and threshold stability matter more.
6. **Trust the equity curve over summary statistics.** If `total_trades` in metrics and trade count in the equity curve disagree, the metrics function is broken.
