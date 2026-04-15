# Phase 2 Decision Protocol

> **For:** Claude Code session working on `jcamp_fxscalper_ml`
> **Reads:** `PRD.md`, `STATUS.md`, `PHASE2_CORRECTIONS.md`, `PHASE2_CORRECTED_RESULTS.md`
> **Status:** 🟡 Phase 2 bugs fixed, but the go/no-go decision for Phase 3 is **not yet made**.
> **Goal:** Run one more experiment, apply the decision tree below, and produce an unambiguous answer: proceed / test / iterate.
> **Do not:** Start Phase 3 work until this protocol is complete and STATUS.md reflects the decision.

---

## TL;DR

The corrected Phase 2 results prove the edge is real (wide plateau) but inconsistent (only 3/6 walk-forward folds positive at threshold 0.55). The previous recommendation to proceed at threshold 0.65 is based on an **untested assumption** that fold consistency improves at higher thresholds. This protocol tests that assumption directly, then applies a decision tree to route the project to one of three outcomes.

---

## Corrections to `PHASE2_CORRECTED_RESULTS.md`

These issues in the previous analysis need to be addressed before any decision is made.

### Correction 1 — Fold 6 is missing

Both LONG and SHORT walk-forward tables list fold 6 as `(incomplete)`. A 5-fold walk-forward is not a 6-fold walk-forward. The missing fold could change the story either way.

**Action:** Find out why fold 6 didn't run. Fix it. Re-run the full 6-fold walk-forward before evaluating anything else. If there's a data availability issue (e.g., fold 6 extends into the held-out set), shrink the fold definitions so all 6 fit entirely inside the train/CV window (Jan 2023 – Sep 2025).

### Correction 2 — Equity curve shape gate was skipped

The previous document marked "Equity curve shape" as `TBD` and proceeded anyway. That gate is not optional — per-fold equity curves reveal whether a profitable fold is steadily compounding or riding on 2 lucky winners. Those two cases have wildly different implications for live trading.

**Action:** For every fold, every direction, every threshold tested below, plot the running equity curve (cumulative R over trade number). A profitable fold that's actually a random walk with 2 big winners is not the same as a profitable fold with persistent climb.

### Correction 3 — "Proceed anyway if expectancy ≥0.15R" is not a valid gate

The previous document proposes: *"If walk-forward at 0.65 still shows only 3/6 positive folds, proceed anyway if mean expectancy ≥0.15R."* This is gate erosion. A gate that moves when you fail it is not a gate.

**Action:** Replace this with the decision tree in section 4 below. There are three valid outcomes (proceed, test held-out only, iterate features) and exactly one condition for each. "Proceed anyway" is not one of them.

### Correction 4 — The worst-fold metric was not reported

The previous document reports mean expectancy across folds, but the mean doesn't tell you whether your system survives the bad months. If 5 folds average +0.20R and one fold averages -1.0R, the mean looks fine but the one bad fold would blow your account. Worst-fold performance matters more than average-fold performance for a system that has to trade every period.

**Action:** For every threshold tested below, report not just the mean but also the **worst fold's expectancy, worst fold's net R, and worst fold's max drawdown as % of fold starting equity**.

### Correction 5 — Threshold was only tested at 0.55 in walk-forward

The 70/30 split was evaluated at 0.50–0.75. The walk-forward was only evaluated at 0.55. The entire "proceed at 0.65" recommendation is based on extrapolating 70/30 behavior to walk-forward behavior, which is exactly the kind of leap that walk-forward exists to prevent. Walk-forward must be re-run at the threshold you actually plan to use.

**Action:** Run walk-forward at four thresholds, not one. See the experiment below.

---

## Experiment — Multi-Threshold Walk-Forward

### Objective

Determine whether raising the probability threshold improves walk-forward fold consistency, or only improves per-trade expectancy while leaving the same folds broken.

### Procedure

For each direction (LONG and SHORT), re-run the complete 6-fold purged walk-forward CV at **four thresholds**: `0.55`, `0.60`, `0.65`, `0.70`.

Use the corrected `calculate_trading_metrics()` from `PHASE2_CORRECTIONS.md`. Use `commission_r = 0.04`. Use the same fold boundaries and purging/embargo settings as the existing notebook.

For every `(direction, threshold)` combination, record per fold:

- Fold number
- Number of trades
- Win rate
- Profit factor
- Expectancy in R
- Net R
- Max drawdown in R (peak-to-trough of the fold's equity curve)

And report these aggregates:

- **Positive fold count** (how many of 6 folds have `net_r > 0`)
- **Mean expectancy** across folds
- **Worst fold expectancy** (the minimum)
- **Worst fold net R**
- **Standard deviation of fold expectancy** (consistency measure)

### Required outputs

Save these artifacts to `notebooks/outputs/phase2_decision/`:

1. `walk_forward_multi_threshold_long.csv` — long-format table: `threshold, fold, n_trades, win_rate, pf, expectancy_r, net_r, max_dd_r`
2. `walk_forward_multi_threshold_short.csv` — same structure
3. `fold_equity_curves_long_thr{0.55,0.60,0.65,0.70}.png` — 4 charts, each showing all 6 fold equity curves overlaid
4. `fold_equity_curves_short_thr{0.55,0.60,0.65,0.70}.png` — same
5. `threshold_consistency_summary.md` — a table with the aggregates above for each direction × threshold

### Summary table format

The `threshold_consistency_summary.md` should contain one table per direction in this shape:

```markdown
### LONG — Walk-forward across thresholds

| Threshold | Positive folds | Mean exp | Worst fold exp | Worst fold net R | Stdev exp | Avg trades/fold |
|-----------|---------------:|---------:|---------------:|-----------------:|----------:|----------------:|
| 0.55      | 3/6            | +0.013   | -0.297         | -231.2           | 0.186     | 481             |
| 0.60      | ?              | ?        | ?              | ?                | ?         | ?               |
| 0.65      | ?              | ?        | ?              | ?                | ?         | ?               |
| 0.70      | ?              | ?        | ?              | ?                | ?         | ?               |
```

(Row for 0.55 pre-filled from the previous corrected results. Fill in the rest.)

### Sanity check before proceeding

Before accepting the experiment output:

- Trade counts should decrease monotonically as threshold rises. If they don't, something is broken.
- Expectancy should generally rise as threshold rises (this is the "confident tail" effect). If it's flat or falling, the model has no useful ranking signal — that's a different failure mode that invalidates everything.
- At threshold 0.70, some folds may have < 20 trades. Flag these as statistically unreliable in the summary — any expectancy on < 20 trades is noise.

---

## Decision Tree

Once the experiment is complete and the summary table is filled in, apply this tree **strictly**. Do not improvise gate values. If the result doesn't match any branch, stop and report the ambiguity before making a decision.

### Branch A — Proceed to held-out test

**Required (all must hold at a single threshold, call it `T*`):**

- Positive folds ≥ 4/6 at `T*`
- Worst fold expectancy ≥ -0.15R at `T*`
- Mean expectancy ≥ 0.10R at `T*`
- Avg trades per fold ≥ 100 at `T*`
- Fold equity curves show persistent climb (not 2-winners-carry-the-fold)
- Plateau width ≥ 0.08 around `T*` (re-verify from sensitivity plot)

**Action:** `T*` becomes the production threshold. Run the held-out set (Oct 2025 – Mar 2026) **exactly once** at `T*`. Do not tune. Do not rerun. The held-out set is touched exactly this one time.

Then apply the held-out gate:

- Held-out PF ≥ 1.25 AND ≥ 4 of 6 held-out months show positive net R → **proceed to Phase 3**
- Held-out PF < 1.25 OR ≤ 3 held-out months positive → **stop, go to Branch C (feature engineering)**. The held-out set is now burned; any future retraining must re-define a new held-out window.

### Branch B — Proceed to held-out test with reduced confidence

**Required (all must hold at `T*`):**

- Positive folds = 3/6 at `T*` (not 4+)
- Worst fold expectancy ≥ -0.10R at `T*` (tighter than Branch A — we need the bad folds to be less bad to compensate for their frequency)
- Mean expectancy ≥ 0.15R at `T*` (higher than Branch A — we need the good folds to be better to compensate)
- Plateau width ≥ 0.15 around `T*` (wider than Branch A — we need stronger robustness evidence)
- Avg trades per fold ≥ 80

**Action:** This is the "experiment, not deployment" path. `T*` is the candidate threshold, but you go in knowing the system might fail. Run the held-out set once at `T*`. Then:

- Held-out PF ≥ 1.40 AND ≥ 4 months positive → **proceed to Phase 3** but explicitly document in `STATUS.md` that this is an experimental deployment, not a validated one. Size at 0.5% risk per trade instead of 1% for the first 30 days.
- Anything weaker → **stop, go to Branch C**.

### Branch C — Feature engineering required

**Trigger (any of):**

- No threshold achieves ≥ 3/6 positive folds
- At every threshold, worst fold expectancy < -0.15R
- Mean expectancy < 0.10R at every threshold
- Equity curves reveal that profitable folds are carried by < 5 trades each
- Trade count at `T*` is < 20 per fold (statistically unreliable)

**Action:** Do NOT touch the held-out set. Do NOT proceed to Phase 3. Instead, add regime-aware features and re-run walk-forward from scratch.

Specifically, add these features to the DataCollector (requires cBot v0.3 and a new full historical run):

- `atr_h1_pct_rank_30d` — where current H1 ATR sits in the last 30-day distribution (volatility regime indicator)
- `adx_h1` and `adx_h4` — trend strength at higher TFs
- `hours_since_session_open` — how far into the current session we are
- `realized_vol_m5_50` — rolling 50-bar standard deviation of M5 returns
- `spread_pct_of_atr` — relative cost of entry

The hypothesis is that the system can't distinguish good regimes from bad, and these features give the model a way to learn *when* to be active, not just *which* signals to take.

After the new DataCollector run and retraining, return to this decision tree at the top.

---

## Execution checklist

Work through these in order:

- [ ] **Step 1** — Read `PRD.md`, `STATUS.md`, `PHASE2_CORRECTIONS.md`, `PHASE2_CORRECTED_RESULTS.md`
- [ ] **Step 2** — Fix fold 6 (Correction 1). Re-run the single-threshold 6-fold walk-forward at 0.55 to confirm fold 6 now runs. Sanity check: fold 6 should not be wildly different from folds 1–5
- [ ] **Step 3** — Run the multi-threshold experiment (section 3 above) at 0.55, 0.60, 0.65, 0.70 for both directions
- [ ] **Step 4** — Generate all required artifacts (the 4 output files listed in section 3)
- [ ] **Step 5** — Visually inspect every fold equity curve. Flag any that look like random walks or 2-winner flukes
- [ ] **Step 6** — Fill in the summary table for both directions
- [ ] **Step 7** — For each direction, identify `T*` — the threshold with the best combination of fold consistency, worst-fold safety, and mean expectancy. If LONG and SHORT prefer different thresholds, that's fine — use different `T*` per direction, document both
- [ ] **Step 8** — Apply the decision tree strictly. Write which branch (A, B, or C) applies and why, with the specific numbers that triggered that branch
- [ ] **Step 9** — If Branch A or B: run the held-out set at `T*` exactly once. Apply the held-out gate. Write the result
- [ ] **Step 10** — If Branch C: do NOT run the held-out set. Begin the feature engineering plan
- [ ] **Step 11** — Update `STATUS.md` with the final decision and all supporting numbers
- [ ] **Step 12** — Update `PRD.md` Phase 2 acceptance section to reflect the new gates (the branches above)

---

## Notes

- **The held-out set is one-shot.** It is touched exactly once, after the threshold is finalized, and never again. If the held-out test fails, the held-out set is burned and you need a new one. This is non-negotiable and is what makes the held-out result meaningful.
- **"Worst fold" matters more than "mean fold".** Your live system has to survive every fold, not just the average. A system with mean +0.20R but worst-fold -1.0R will blow up the account before the good folds can carry it.
- **Do not tune on the held-out set.** Ever. Not even "just to see." The moment you look at held-out performance and change something based on what you saw, the held-out set is no longer held out.
- **If LONG and SHORT land in different branches**, handle them separately. It's valid to proceed with SHORT-only if SHORT passes Branch A and LONG fails. In that case, disable long trading in the Phase 4 cBot and document it.
- **If the experiment reveals something weird** (non-monotonic expectancy, trade counts not dropping as threshold rises, one fold with 0 trades) — stop and investigate. Do not paper over anomalies. Report them in `STATUS.md` and wait for review before proceeding.

---

## Expected outcomes

Based on the 70/30 results showing an edge that concentrates at higher thresholds, the most likely outcome is **Branch A or B at threshold 0.65 for SHORT** and either Branch A/B at 0.65 or Branch C for LONG (since LONG had 0.5246 AUC, weaker than SHORT's 0.5388). Don't anchor on this prediction — run the experiment and let the numbers decide. But if the result is very different from this (e.g., LONG passes Branch A easily while SHORT fails), that's a flag worth investigating before trusting the result.
