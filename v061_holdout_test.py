"""
v0.6.1 HOLDOUT TEST -- LONG + SHORT Final Generalization Check
==============================================================

Loads the v0.6.1 models already trained on Jan 2023 - Sep 2025 in
`v061_retrain.py` / `v061_retrain_short.py`, then evaluates on the
unseen Oct 2025 - Mar 2026 holdout.

Locked thresholds (from CV):
  - LONG:  0.65 (mean exp +0.639R)
  - SHORT: 0.55 (mean exp +0.333R)

R-mapping (matches CV: timeout_as="loss"):
  win = +3.0R, loss = -1.0R, timeout = 0.0R

CRITICAL: Run this ONCE per direction. The holdout is single-use.
"""

import pandas as pd
import numpy as np
from joblib import load
from pathlib import Path
import json
from datetime import datetime

DATA_PATH = Path("data/DataCollector_EURUSD_M5_20230102_000000.csv")
MODEL_DIR = Path("models")
OUTPUT_DIR = Path("outputs/holdout_test_v061")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_END = pd.Timestamp('2025-09-30 23:59:59')
HOLDOUT_END = pd.Timestamp('2026-03-31 23:59:59')

CONFIGS = [
    {
        'direction': 'long',
        'model_file': 'eurusd_long_v061.joblib',
        'threshold': 0.65,
        'cv_estimate': 0.639,
        'outcome_col': 'outcome_long',
    },
    {
        'direction': 'short',
        'model_file': 'eurusd_short_v061.joblib',
        'threshold': 0.55,
        'cv_estimate': 0.333,
        'outcome_col': 'outcome_short',
    },
]

LABEL_COLS = ['timestamp', 'symbol',
              'outcome_long', 'bars_to_outcome_long',
              'outcome_short', 'bars_to_outcome_short']

print("=" * 70)
print("v0.6.1 HOLDOUT TEST -- LONG + SHORT")
print("=" * 70)
print(f"Started: {datetime.now().isoformat()}\n")

# Load data once
print("Loading data...")
df = pd.read_csv(DATA_PATH, parse_dates=['timestamp'])
df = df.sort_values('timestamp').reset_index(drop=True)
df_holdout = df[(df.timestamp > TRAIN_END) & (df.timestamp <= HOLDOUT_END)].reset_index(drop=True)
print(f"Holdout set: {len(df_holdout):,} rows ({df_holdout.timestamp.min().date()} to {df_holdout.timestamp.max().date()})")
assert len(df_holdout) > 30000, f"Holdout too small: {len(df_holdout)}"

FEATURE_COLS = [c for c in df.columns if c not in LABEL_COLS]
assert len(FEATURE_COLS) == 49, f"Expected 49 features, got {len(FEATURE_COLS)}"
print(f"Features: {len(FEATURE_COLS)}\n")

X_holdout = df_holdout[FEATURE_COLS]
all_summaries = {}

for cfg in CONFIGS:
    direction = cfg['direction']
    threshold = cfg['threshold']
    cv_est = cfg['cv_estimate']
    outcome_col = cfg['outcome_col']

    print("=" * 70)
    print(f"{direction.upper()} @ threshold {threshold}")
    print("=" * 70)

    model_path = MODEL_DIR / cfg['model_file']
    bundle = load(model_path)
    model = bundle['model'] if isinstance(bundle, dict) else bundle
    print(f"Loaded {model_path}")

    p_win = model.predict_proba(X_holdout)[:, 1]
    print(f"\n  Pred dist: mean={p_win.mean():.4f} std={p_win.std():.4f} min={p_win.min():.4f} max={p_win.max():.4f}")
    print(f"  P > {threshold}: {(p_win > threshold).sum():,} bars ({(p_win > threshold).mean():.1%})")

    df_h = df_holdout.copy()
    df_h['p_win'] = p_win
    traded = df_h[df_h['p_win'] > threshold].copy()
    n_trades = len(traded)

    print(f"\n  Traded: {n_trades:,} bars\n")

    if n_trades == 0:
        print(f"  [ERROR] No trades. Skipping.\n")
        all_summaries[direction] = {'verdict': 'NO_TRADES'}
        continue

    r_map = {'win': 3.0, 'loss': -1.0, 'timeout': 0.0}
    traded['r'] = traded[outcome_col].map(r_map)

    expectancy = traded['r'].mean()
    net_r = traded['r'].sum()
    n_wins = (traded[outcome_col] == 'win').sum()
    n_losses = (traded[outcome_col] == 'loss').sum()
    n_timeouts = (traded[outcome_col] == 'timeout').sum()
    win_rate = n_wins / n_trades

    gross_wins = n_wins * 3.0
    gross_losses = n_losses * 1.0
    profit_factor = gross_wins / max(gross_losses, 0.001)

    is_loss = (traded[outcome_col] == 'loss').values
    max_consec = 0
    cur = 0
    for l in is_loss:
        if l:
            cur += 1
            max_consec = max(max_consec, cur)
        else:
            cur = 0

    traded['cum_r'] = traded['r'].cumsum()
    peak = 0
    max_dd_r = 0
    for r in traded['cum_r']:
        if r > peak:
            peak = r
        dd = peak - r
        if dd > max_dd_r:
            max_dd_r = dd

    print(f"  --- RESULTS ---")
    print(f"  Trades:         {n_trades}")
    print(f"    Wins:         {n_wins} ({win_rate:.1%})")
    print(f"    Losses:       {n_losses}")
    print(f"    Timeouts:     {n_timeouts}")
    print(f"  Expectancy:     {expectancy:+.3f}R/trade")
    print(f"  Net R:          {net_r:+.1f}R")
    print(f"  Profit Factor:  {profit_factor:.2f}")
    print(f"  Max Consec L:   {max_consec}")
    print(f"  Max Drawdown:   {max_dd_r:.1f}R")

    pct_of_cv = expectancy / cv_est * 100 if cv_est != 0 else 0
    within_30 = abs(expectancy - cv_est) / abs(cv_est) <= 0.30
    print(f"\n  --- VERDICT ---")
    print(f"  CV estimate:    {cv_est:+.3f}R | Holdout: {expectancy:+.3f}R | %CV: {pct_of_cv:.0f}%")

    if expectancy > 0 and within_30:
        verdict = "PASS"
        print(f"  [OK] PASS -- holdout confirms CV.")
    elif expectancy > 0 and not within_30:
        if pct_of_cv < 100:
            verdict = "CAUTIOUS_PASS"
            print(f"  [WARN] CAUTIOUS_PASS -- positive but below CV (-30% tolerance).")
        else:
            verdict = "VERIFY"
            print(f"  [WARN] VERIFY -- well above CV. Possible data issue.")
    else:
        verdict = "FAIL"
        print(f"  [FAIL] FAIL -- no edge on holdout. DO NOT DEPLOY.")

    # Monthly breakdown
    traded['month'] = traded['timestamp'].dt.to_period('M').astype(str)
    monthly = traded.groupby('month').agg(
        trades=('r', 'count'),
        wins=(outcome_col, lambda x: (x == 'win').sum()),
        win_rate=(outcome_col, lambda x: (x == 'win').mean()),
        expectancy=('r', 'mean'),
        net_r=('r', 'sum'),
    )
    print(f"\n  --- MONTHLY ---")
    print(monthly.to_string())
    print()

    # Save artifacts
    out_subdir = OUTPUT_DIR / direction
    out_subdir.mkdir(exist_ok=True)
    traded[['timestamp', 'p_win', outcome_col, 'r', 'cum_r']].to_csv(
        out_subdir / "holdout_equity_curve.csv", index=False)
    monthly.to_csv(out_subdir / "holdout_monthly_breakdown.csv")

    summary = {
        'direction': direction,
        'test_period': f"{df_holdout.timestamp.min().date()} to {df_holdout.timestamp.max().date()}",
        'threshold': threshold,
        'n_trades': int(n_trades),
        'n_wins': int(n_wins),
        'n_losses': int(n_losses),
        'n_timeouts': int(n_timeouts),
        'win_rate': f"{win_rate:.1%}",
        'expectancy_r': f"{expectancy:+.3f}",
        'net_r': f"{net_r:+.1f}",
        'profit_factor': f"{profit_factor:.2f}",
        'max_consec_losses': int(max_consec),
        'max_drawdown_r': f"{max_dd_r:.1f}",
        'cv_estimate_r': f"{cv_est:+.3f}",
        'pct_of_cv': f"{pct_of_cv:.0f}%",
        'within_30pct_tolerance': bool(within_30),
        'verdict': verdict,
    }
    with open(out_subdir / "holdout_summary.json", 'w') as f:
        json.dump(summary, f, indent=2)
    all_summaries[direction] = summary
    print(f"  Saved to {out_subdir}/\n")

print("=" * 70)
print("v0.6.1 HOLDOUT FINAL SUMMARY")
print("=" * 70)
for d, s in all_summaries.items():
    print(f"  {d.upper():<6}: verdict={s.get('verdict')}, exp={s.get('expectancy_r', 'N/A')}, trades={s.get('n_trades', 'N/A')}")

with open(OUTPUT_DIR / "holdout_combined_summary.json", 'w') as f:
    json.dump(all_summaries, f, indent=2)
print(f"\nCombined summary: {OUTPUT_DIR}/holdout_combined_summary.json")
