"""
Re-score the v0.6.1 holdout with realistic execution guards layered on
top of the raw ML signals. Three layers, in order:

  1. MaxPositions=1   -- only one open position at a time (cBot already
                         enforces this; backtest must too)
  2. Stretch guard    -- skip SHORT when dist_sma_h4_200 < -20
                         skip LONG  when dist_sma_h4_200 > +20
  3. MTF counter-trend guard
                      -- skip SHORT when mtf_alignment_duration > +20
                         skip LONG  when mtf_alignment_duration < -20
  4. Post-SL cooldown -- 12 bars (~1 hour M5) pause after any stop-out

Goal: confirm Mar 31 SHORT collapses to ~0 entries while preserving the
positive-month edge. If yes, v0.6.2 retrain can apply the same filters
to training data for distribution parity.
"""

import pandas as pd
import numpy as np
from joblib import load
from pathlib import Path
import json

DATA_PATH = Path("data/DataCollector_EURUSD_M5_20230102_000000.csv")
MODEL_DIR = Path("models")
OUT_DIR = Path("outputs/holdout_test_v061_guarded")
OUT_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_END = pd.Timestamp('2025-09-30 23:59:59')
HOLDOUT_END = pd.Timestamp('2026-03-31 23:59:59')

LABEL_COLS = ['timestamp', 'symbol',
              'outcome_long', 'bars_to_outcome_long',
              'outcome_short', 'bars_to_outcome_short']

GUARDS = {
    'stretch_threshold': 20.0,        # |dist_sma_h4_200| > 20 ATR = skip
    'mtf_counter_threshold': 20,      # |mtf_alignment_duration| > 20 = skip
    'cooldown_bars': 12,              # bars to skip after SL
}

CONFIGS = [
    {'direction': 'long',  'model_file': 'eurusd_long_v061.joblib',  'threshold': 0.65,
     'outcome_col': 'outcome_long',  'bars_col': 'bars_to_outcome_long'},
    {'direction': 'short', 'model_file': 'eurusd_short_v061.joblib', 'threshold': 0.55,
     'outcome_col': 'outcome_short', 'bars_col': 'bars_to_outcome_short'},
]


def stretch_guard_blocks(direction: str, dist_h4: float) -> bool:
    if direction == 'short' and dist_h4 < -GUARDS['stretch_threshold']:
        return True
    if direction == 'long' and dist_h4 > GUARDS['stretch_threshold']:
        return True
    return False


def mtf_guard_blocks(direction: str, mtf_dur: float) -> bool:
    if direction == 'short' and mtf_dur > GUARDS['mtf_counter_threshold']:
        return True
    if direction == 'long' and mtf_dur < -GUARDS['mtf_counter_threshold']:
        return True
    return False


def simulate_bot(df: pd.DataFrame, direction: str, p_win: np.ndarray,
                 threshold: float, outcome_col: str, bars_col: str,
                 use_guards: bool = True) -> pd.DataFrame:
    """Walk bars in order, applying MaxPositions=1, guards, and cooldown."""
    n = len(df)
    position_open_until = -1
    cooldown_until = -1
    trades = []
    skipped = {'p_below_thr': 0, 'position_open': 0, 'cooldown': 0,
               'stretch_guard': 0, 'mtf_guard': 0}

    for i in range(n):
        if p_win[i] <= threshold:
            skipped['p_below_thr'] += 1
            continue
        if i <= position_open_until:
            skipped['position_open'] += 1
            continue
        if i <= cooldown_until:
            skipped['cooldown'] += 1
            continue
        if use_guards:
            dist_h4 = df['dist_sma_h4_200'].iat[i]
            mtf_dur = df['mtf_alignment_duration'].iat[i]
            if stretch_guard_blocks(direction, dist_h4):
                skipped['stretch_guard'] += 1
                continue
            if mtf_guard_blocks(direction, mtf_dur):
                skipped['mtf_guard'] += 1
                continue

        # Take the trade
        outcome = df[outcome_col].iat[i]
        bars = int(df[bars_col].iat[i])
        position_open_until = i + bars
        if outcome == 'loss':
            cooldown_until = position_open_until + GUARDS['cooldown_bars']

        r_map = {'win': 3.0, 'loss': -1.0, 'timeout': 0.0}
        trades.append({
            'idx': i,
            'timestamp': df['timestamp'].iat[i],
            'p_win': p_win[i],
            'outcome': outcome,
            'r': r_map[outcome],
            'dist_sma_h4_200': df['dist_sma_h4_200'].iat[i],
            'mtf_alignment_duration': df['mtf_alignment_duration'].iat[i],
        })

    return pd.DataFrame(trades), skipped


def summarize(trades: pd.DataFrame, label: str) -> dict:
    if len(trades) == 0:
        print(f"\n  {label}: 0 trades")
        return {'label': label, 'n_trades': 0}
    n = len(trades)
    wins = (trades['outcome'] == 'win').sum()
    losses = (trades['outcome'] == 'loss').sum()
    timeouts = (trades['outcome'] == 'timeout').sum()
    exp = trades['r'].mean()
    net = trades['r'].sum()
    gw = wins * 3.0
    gl = losses * 1.0
    pf = gw / max(gl, 0.001)

    is_loss = (trades['outcome'] == 'loss').values
    max_consec = 0; cur = 0
    for l in is_loss:
        cur = cur + 1 if l else 0
        max_consec = max(max_consec, cur)

    cum = trades['r'].cumsum()
    peak = -np.inf; max_dd = 0
    for r in cum:
        peak = max(peak, r)
        max_dd = max(max_dd, peak - r)

    print(f"\n  {label}")
    print(f"    Trades: {n} | Win%: {wins/n*100:.1f} | Exp: {exp:+.3f}R | Net: {net:+.1f}R | PF: {pf:.2f}")
    print(f"    Max consec L: {max_consec} | Max DD: {max_dd:.1f}R")
    return {
        'label': label, 'n_trades': int(n), 'wins': int(wins), 'losses': int(losses),
        'timeouts': int(timeouts), 'expectancy_r': float(exp), 'net_r': float(net),
        'profit_factor': float(pf), 'max_consec_losses': int(max_consec),
        'max_drawdown_r': float(max_dd),
    }


# ---- main ----
print("=" * 70)
print("v0.6.1 HOLDOUT WITH RUNTIME GUARDS")
print("=" * 70)
print(f"Guards: stretch |dist_h4| > {GUARDS['stretch_threshold']}, "
      f"mtf |duration| > {GUARDS['mtf_counter_threshold']}, "
      f"cooldown {GUARDS['cooldown_bars']} bars after SL\n")

df = pd.read_csv(DATA_PATH, parse_dates=['timestamp']).sort_values('timestamp').reset_index(drop=True)
df_holdout = df[(df.timestamp > TRAIN_END) & (df.timestamp <= HOLDOUT_END)].reset_index(drop=True)
FEATURE_COLS = [c for c in df.columns if c not in LABEL_COLS]
print(f"Holdout: {len(df_holdout):,} bars | Features: {len(FEATURE_COLS)}\n")

X_holdout = df_holdout[FEATURE_COLS]
all_results = {}

for cfg in CONFIGS:
    direction = cfg['direction']
    print("=" * 70)
    print(f"{direction.upper()} @ thr {cfg['threshold']}")
    print("=" * 70)

    model = load(MODEL_DIR / cfg['model_file'])
    p_win = model.predict_proba(X_holdout)[:, 1]

    # Naive: every bar that passes threshold = trade (matches v061_holdout_test.py)
    raw_trades = df_holdout[p_win > cfg['threshold']].copy()
    raw_trades['p_win'] = p_win[p_win > cfg['threshold']]
    r_map = {'win': 3.0, 'loss': -1.0, 'timeout': 0.0}
    raw_trades['outcome'] = raw_trades[cfg['outcome_col']]
    raw_trades['r'] = raw_trades['outcome'].map(r_map)
    raw_summary = summarize(raw_trades, "RAW (no guards, every signal = trade)")

    # MaxPositions=1 only
    pos_only_trades, sk1 = simulate_bot(df_holdout, direction, p_win, cfg['threshold'],
                                         cfg['outcome_col'], cfg['bars_col'], use_guards=False)
    pos_summary = summarize(pos_only_trades, "MAX_POSITIONS=1 ONLY")

    # MaxPositions + guards + cooldown
    guarded_trades, sk2 = simulate_bot(df_holdout, direction, p_win, cfg['threshold'],
                                        cfg['outcome_col'], cfg['bars_col'], use_guards=True)
    guarded_summary = summarize(guarded_trades, "MAX_POSITIONS=1 + GUARDS + COOLDOWN")
    print(f"    Skipped by guard: stretch={sk2['stretch_guard']}, mtf={sk2['mtf_guard']}, cooldown={sk2['cooldown']}, position_open={sk2['position_open']}")

    # Mar 31 specific check
    if direction == 'short':
        mar31_raw = raw_trades[raw_trades['timestamp'].dt.date == pd.to_datetime('2026-03-31').date()]
        mar31_pos = pos_only_trades[pos_only_trades['timestamp'].dt.date == pd.to_datetime('2026-03-31').date()] if len(pos_only_trades) else pd.DataFrame()
        mar31_guarded = guarded_trades[guarded_trades['timestamp'].dt.date == pd.to_datetime('2026-03-31').date()] if len(guarded_trades) else pd.DataFrame()
        print(f"\n  --- MAR 31 SHORT CHECK ---")
        print(f"    Raw:        {len(mar31_raw)} trades, net {mar31_raw['r'].sum():+.1f}R")
        print(f"    Pos-only:   {len(mar31_pos)} trades, net {mar31_pos['r'].sum() if len(mar31_pos) else 0:+.1f}R")
        print(f"    Guarded:    {len(mar31_guarded)} trades, net {mar31_guarded['r'].sum() if len(mar31_guarded) else 0:+.1f}R")

    # Monthly under guarded mode
    if len(guarded_trades):
        guarded_trades['month'] = guarded_trades['timestamp'].dt.to_period('M').astype(str)
        monthly = guarded_trades.groupby('month').agg(
            trades=('r', 'count'),
            wins=('outcome', lambda x: (x == 'win').sum()),
            net_r=('r', 'sum'),
            exp=('r', 'mean'),
        )
        print(f"\n  --- GUARDED MONTHLY ---")
        print(monthly.to_string())

    all_results[direction] = {
        'raw': raw_summary,
        'pos_only': pos_summary,
        'guarded': guarded_summary,
        'guard_skip_counts': {k: int(v) for k, v in sk2.items()},
    }

    # Save guarded equity curve
    if len(guarded_trades):
        guarded_trades['cum_r'] = guarded_trades['r'].cumsum()
        guarded_trades.to_csv(OUT_DIR / f"{direction}_guarded_equity.csv", index=False)

# ---- summary ----
print("\n" + "=" * 70)
print("SUMMARY -- RAW vs MAX_POS=1 vs FULLY GUARDED")
print("=" * 70)
for d, r in all_results.items():
    print(f"\n{d.upper()}:")
    print(f"  {'Mode':<28} {'Trades':>7} {'Net R':>9} {'Exp':>9} {'PF':>6} {'MaxDD':>7} {'MaxConsL':>9}")
    for mode in ['raw', 'pos_only', 'guarded']:
        s = r[mode]
        if s.get('n_trades', 0) == 0:
            print(f"  {s['label']:<28} {0:>7} {'  ---':>9}")
            continue
        print(f"  {s['label'][:28]:<28} {s['n_trades']:>7} {s['net_r']:>+9.1f} {s['expectancy_r']:>+9.3f} "
              f"{s['profit_factor']:>6.2f} {s['max_drawdown_r']:>7.1f} {s['max_consec_losses']:>9}")

with open(OUT_DIR / "summary.json", 'w') as f:
    json.dump(all_results, f, indent=2, default=str)
print(f"\nFull results: {OUT_DIR}/summary.json")
