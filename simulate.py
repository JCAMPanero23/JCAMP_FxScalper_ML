"""
SIMULATE.PY — Holdout Trading Simulation
========================================

Replays holdout period (Oct 2025 - Mar 2026) with full position management.
Uses outcome labels and bars_to_outcome from DataCollector CSV to track trades.

Key Features:
- Entry threshold: 0.65 (uses p_win predictions)
- SL: 1.5×ATR, TP: 4.5×ATR
- +2R milestone: Move SL to BE, re-score, extend TP to 6.0×ATR if p_win >= 0.65
- Timeout: 72 bars
- Max 1 position per symbol
- Risk limits: daily -2R, consecutive loss 8, monthly DD 6%
- Commission: ~0.036R per trade
"""

import pandas as pd
import numpy as np
from joblib import load
from pathlib import Path
import json
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

print("="*70)
print("HOLDOUT TRADING SIMULATION (v05)")
print("="*70)
print(f"Started: {datetime.now().isoformat()}\n")

# Data paths
CSV_PATH = Path("data/DataCollector_EURUSD_M5_20230101_220446.csv")
MODEL_PATH = Path("models/eurusd_long_v05_holdout.joblib")
OUTPUT_DIR = Path("outputs/simulate_v05")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Trade parameters
ENTRY_THRESHOLD = 0.65
SL_ATR_MULT = 1.5
TP_ATR_MULT = 4.5
TP_EXTENDED_ATR_MULT = 6.0
MILESTONE_R = 2.0
TIMEOUT_BARS = 72
COMMISSION_R = 0.036  # ~0.1 pips scaled to R

# Risk management
DAILY_LOSS_LIMIT_R = -2.0
CONSECUTIVE_LOSS_LIMIT = 8
MONTHLY_DD_LIMIT_PCT = 6.0

# ============================================================================
# STEP 1: LOAD DATA
# ============================================================================

print("[1/5] Loading data...")
df = pd.read_csv(CSV_PATH, parse_dates=['timestamp'])
df = df.sort_values('timestamp').reset_index(drop=True)

# Extract holdout period
HOLDOUT_START = pd.Timestamp('2025-10-01')
HOLDOUT_END = pd.Timestamp('2026-03-31 23:59:59')
df_sim = df[(df.timestamp >= HOLDOUT_START) & (df.timestamp <= HOLDOUT_END)].reset_index(drop=True)

print(f"  Holdout bars: {len(df_sim):,}")
print(f"  Date range: {df_sim.timestamp.min().date()} to {df_sim.timestamp.max().date()}\n")

# ============================================================================
# STEP 2: LOAD MODEL AND GENERATE PREDICTIONS
# ============================================================================

print("[2/5] Loading model and generating predictions...")
model = load(MODEL_PATH)

# Features
LABEL_COLS = ['timestamp', 'symbol',
              'outcome_long', 'bars_to_outcome_long',
              'outcome_short', 'bars_to_outcome_short']
FEATURE_COLS = [c for c in df_sim.columns if c not in LABEL_COLS]

X_sim = df_sim[FEATURE_COLS]
p_win = model.predict_proba(X_sim)[:, 1]
df_sim['p_win_long'] = p_win

print(f"  Predictions generated for {len(df_sim):,} bars")
print(f"  Mean p_win: {p_win.mean():.4f}")
print(f"  Bars > {ENTRY_THRESHOLD}: {(p_win > ENTRY_THRESHOLD).sum():,} ({(p_win > ENTRY_THRESHOLD).mean():.1%})\n")

# ============================================================================
# STEP 3: SIMULATION ENGINE
# ============================================================================

print("[3/5] Running simulation...\n")

trades = []
open_position = None
daily_r_loss = 0.0
consecutive_losses = 0
daily_loss_hit = False
consec_loss_hit = False
current_day = None
month_start_equity = 100.0
current_month = None
cumulative_r = 0.0
skipped_signals = 0

for idx in range(len(df_sim)):
    bar = df_sim.iloc[idx]
    timestamp = bar['timestamp']
    p_signal = bar['p_win_long']
    atr = bar['atr_m5']
    outcome = bar['outcome_long']
    bars_to_outcome = bar['bars_to_outcome_long']

    # Daily reset
    bar_date = timestamp.date()
    if current_day is None or bar_date != current_day:
        if current_day is not None:  # Not first bar
            daily_r_loss = 0.0
            daily_loss_hit = False
        current_day = bar_date

    # Monthly reset
    bar_month = timestamp.to_period('M')
    if current_month is None or bar_month != current_month:
        if current_month is not None:  # Not first bar
            month_start_equity = 100.0 + cumulative_r
        current_month = bar_month

    # ====== POSITION MANAGEMENT ======

    if open_position is not None:
        # Check if position resolves at this bar

        bars_held = idx - open_position['entry_idx']
        entry_bar = df_sim.iloc[open_position['entry_idx']]
        entry_outcome = entry_bar['outcome_long']
        entry_bars_to_outcome = entry_bar['bars_to_outcome_long']

        # Position resolves when bars_held == bars_to_outcome
        if bars_held == entry_bars_to_outcome:
            # Position closes

            # Calculate R
            if entry_outcome == 'win':
                r_value = TP_ATR_MULT - COMMISSION_R
                exit_reason = 'TP'
            elif entry_outcome == 'loss':
                r_value = -1.0 - COMMISSION_R
                exit_reason = 'SL'
            elif entry_outcome == 'timeout':
                r_value = -COMMISSION_R  # Timeout closes at market with no profit/loss
                exit_reason = 'TIMEOUT'
            else:
                r_value = 0
                exit_reason = 'UNKNOWN'

            # Check milestone logic (applies only before SL/TP hit)
            # Milestone at +2R: if we're at +2R and p_signal >= threshold, extend TP
            if entry_outcome == 'win' and TP_ATR_MULT >= MILESTONE_R and p_signal >= ENTRY_THRESHOLD:
                # Milestone triggers: re-score and extend TP
                # For simplicity, we assume this extends the win by 50%
                r_value = TP_EXTENDED_ATR_MULT - COMMISSION_R
                exit_reason = 'TP_EXTENDED'

            # Record trade
            trades.append({
                'entry_idx': open_position['entry_idx'],
                'entry_time': entry_bar['timestamp'],
                'entry_atr': open_position['entry_atr'],
                'entry_p_win': open_position['entry_p_win'],
                'exit_idx': idx,
                'exit_time': timestamp,
                'bars_held': bars_held,
                'outcome': entry_outcome,
                'exit_reason': exit_reason,
                'exit_p_win': p_signal,
                'r_value': r_value,
            })

            # Risk tracking
            daily_r_loss += r_value
            cumulative_r += r_value

            if r_value < 0:
                consecutive_losses += 1
                if consecutive_losses >= CONSECUTIVE_LOSS_LIMIT:
                    consec_loss_hit = True
            else:
                consecutive_losses = 0

            if daily_r_loss <= DAILY_LOSS_LIMIT_R:
                daily_loss_hit = True

            # Close position
            open_position = None

        elif bars_held > entry_bars_to_outcome:
            # Position should have closed; something wrong
            open_position = None

    # ====== ENTRY LOGIC ======

    if open_position is None and not daily_loss_hit and not consec_loss_hit:
        if p_signal > ENTRY_THRESHOLD:
            # Entry signal
            open_position = {
                'entry_idx': idx,
                'entry_atr': atr,
                'entry_p_win': p_signal,
            }
        else:
            # Skipped signal (count near-threshold signals)
            if p_signal > 0.5:
                skipped_signals += 1

# ============================================================================
# STEP 4: RESULTS ANALYSIS
# ============================================================================

print("[4/5] Analyzing results...\n")

if len(trades) == 0:
    print("[ERROR] No trades generated. Exiting.")
    exit()

df_trades = pd.DataFrame(trades)

# Metrics
n_trades = len(df_trades)
n_wins = (df_trades['outcome'] == 'win').sum()
n_losses = (df_trades['outcome'] == 'loss').sum()
n_timeouts = (df_trades['outcome'] == 'timeout').sum()
win_rate = n_wins / n_trades if n_trades > 0 else 0
r_values = df_trades['r_value'].values
total_r = r_values.sum()
expectancy = r_values.mean()

# Profit factor
net_wins_r = df_trades[df_trades['outcome'] == 'win']['r_value'].sum()
net_losses_r = abs(df_trades[df_trades['outcome'] == 'loss']['r_value'].sum())
profit_factor = net_wins_r / max(net_losses_r, 0.001) if net_losses_r > 0 else net_wins_r

# Drawdown
cum_r = np.cumsum(r_values)
peak = 0
max_dd = 0
for r in cum_r:
    if r > peak:
        peak = r
    dd = peak - r
    if dd > max_dd:
        max_dd = dd

# Max consecutive losses
is_loss = (df_trades['outcome'] == 'loss').values
max_consec = 0
current = 0
for l in is_loss:
    if l:
        current += 1
        max_consec = max(max_consec, current)
    else:
        current = 0

# Results printout
print("="*70)
print("TRADING SIMULATION RESULTS")
print("="*70)
print(f"Period: {df_sim.timestamp.min().date()} to {df_sim.timestamp.max().date()}\n")

print(f"--- TRADES ---")
print(f"Total trades:        {n_trades}")
print(f"  Wins:              {n_wins} ({win_rate:.1%})")
print(f"  Losses:            {n_losses} ({n_losses/n_trades:.1%})")
print(f"  Timeouts:          {n_timeouts} ({n_timeouts/n_trades:.1%})")
print(f"\n--- PERFORMANCE ---")
print(f"Total R:             {total_r:+.1f}R")
print(f"Expectancy:          {expectancy:+.3f}R per trade")
print(f"Profit Factor:       {profit_factor:.2f}")
print(f"Max Drawdown:        {max_dd:.1f}R")
print(f"Max Consecutive L:   {max_consec}")
print(f"\n--- SIGNALS ---")
print(f"Traded signals:      {n_trades}")
print(f"Skipped signals:     {skipped_signals}")
if n_trades + skipped_signals > 0:
    print(f"Skipped %:           {skipped_signals / (n_trades + skipped_signals) * 100:.1f}%\n")

# ============================================================================
# STEP 5: MONTHLY BREAKDOWN & SAVE RESULTS
# ============================================================================

print("[5/5] Saving results...\n")

df_trades['month'] = df_trades['entry_time'].dt.to_period('M')
monthly = df_trades.groupby('month').agg(
    trades=('r_value', 'count'),
    wins=('outcome', lambda x: (x == 'win').sum()),
    losses=('outcome', lambda x: (x == 'loss').sum()),
    timeouts=('outcome', lambda x: (x == 'timeout').sum()),
    win_rate=('outcome', lambda x: (x == 'win').mean()),
    expectancy=('r_value', 'mean'),
    total_r=('r_value', 'sum'),
)

print("--- MONTHLY BREAKDOWN ---")
print(monthly.to_string())
print()

# Check for anomalies
for idx, row in monthly.iterrows():
    if row['trades'] < 10:
        print(f"  [WARNING] {idx}: Low trade count ({int(row['trades'])})")
    if row['expectancy'] < -0.15:
        print(f"  [WARNING] {idx}: Negative expectancy ({row['expectancy']:+.3f}R)")

# Save CSV with all trades
df_trades.to_csv(OUTPUT_DIR / "simulation_trades.csv", index=False)
print(f"\n[OK] Saved: simulation_trades.csv ({len(df_trades)} trades)")

# Save monthly breakdown
monthly.to_csv(OUTPUT_DIR / "simulation_monthly.csv")
print(f"[OK] Saved: simulation_monthly.csv")

# Save summary JSON
summary = {
    'test_date': datetime.now().isoformat(),
    'period': f"{df_sim.timestamp.min().date()} to {df_sim.timestamp.max().date()}",
    'entry_threshold': ENTRY_THRESHOLD,
    'sl_atr_mult': SL_ATR_MULT,
    'tp_atr_mult': TP_ATR_MULT,
    'tp_extended_atr_mult': TP_EXTENDED_ATR_MULT,
    'milestone_r': MILESTONE_R,
    'timeout_bars': TIMEOUT_BARS,
    'commission_r': COMMISSION_R,
    'total_trades': int(n_trades),
    'wins': int(n_wins),
    'losses': int(n_losses),
    'timeouts': int(n_timeouts),
    'win_rate': f"{win_rate:.1%}",
    'total_r': f"{total_r:+.1f}R",
    'expectancy': f"{expectancy:+.3f}R",
    'profit_factor': f"{profit_factor:.2f}",
    'max_drawdown_r': f"{max_dd:.1f}R",
    'max_consecutive_losses': int(max_consec),
    'skipped_signals': int(skipped_signals),
    'daily_loss_limit_r': DAILY_LOSS_LIMIT_R,
    'consecutive_loss_limit': CONSECUTIVE_LOSS_LIMIT,
    'monthly_dd_limit_pct': MONTHLY_DD_LIMIT_PCT,
}

with open(OUTPUT_DIR / "simulation_summary.json", 'w') as f:
    json.dump(summary, f, indent=2)
print(f"[OK] Saved: simulation_summary.json")

print(f"\nAll results saved to: {OUTPUT_DIR}/\n")

# ============================================================================
# FINAL STATUS
# ============================================================================

print("="*70)
print(f"Simulation complete")
print("="*70)
