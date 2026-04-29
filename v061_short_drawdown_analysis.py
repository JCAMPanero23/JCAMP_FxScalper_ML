"""
v0.6.1 SHORT Drawdown Forensics

Deep-dive into the holdout SHORT result to understand whether the 51R
max drawdown / 39 consecutive losses are concentrated (one bad streak,
recoverable) or systemic (model breaks in specific regimes).

Inputs:
  outputs/holdout_test_v061/short/holdout_equity_curve.csv

Reports:
  - Loss-streak distribution and timing
  - Drawdown timeline (peak -> trough -> recovery)
  - Worst N consecutive trading days
  - Win rate / expectancy by hour-of-day and day-of-week
  - Regime correlation: did losing trades cluster when H4 trend was
    actually UP (regime mismatch)?
"""

import pandas as pd
import numpy as np
from pathlib import Path

EQUITY_CSV = Path("outputs/holdout_test_v061/short/holdout_equity_curve.csv")
HOLDOUT_CSV = Path("data/DataCollector_EURUSD_M5_20230102_000000.csv")

print("=" * 70)
print("v0.6.1 SHORT Drawdown Forensics")
print("=" * 70)

eq = pd.read_csv(EQUITY_CSV, parse_dates=['timestamp'])
print(f"\nLoaded {len(eq)} traded bars ({eq['timestamp'].min()} -> {eq['timestamp'].max()})")
print(f"Net R: {eq['r'].sum():+.1f}, Mean R: {eq['r'].mean():+.3f}, Win%: {(eq['outcome_short']=='win').mean()*100:.1f}\n")

# ----- 1. Loss-streak distribution -----
print("=" * 70)
print("1. LOSS STREAK DISTRIBUTION")
print("=" * 70)
is_loss = (eq['outcome_short'] == 'loss').values
streaks = []
cur = 0
streak_starts = []
streak_start_idx = None
for i, l in enumerate(is_loss):
    if l:
        if cur == 0:
            streak_start_idx = i
        cur += 1
    else:
        if cur > 0:
            streaks.append((cur, streak_start_idx, i - 1))
        cur = 0
if cur > 0:
    streaks.append((cur, streak_start_idx, len(is_loss) - 1))

streaks.sort(key=lambda x: -x[0])
print(f"\nTop 10 longest loss streaks:")
print(f"  {'Length':>7} {'Start':>20} {'End':>20} {'Span days':>10}")
for length, si, ei in streaks[:10]:
    start_t = eq.iloc[si]['timestamp']
    end_t = eq.iloc[ei]['timestamp']
    span = (end_t - start_t).total_seconds() / 86400
    print(f"  {length:>7} {str(start_t):>20} {str(end_t):>20} {span:>10.1f}")

streak_lens = [s[0] for s in streaks]
print(f"\nStreak histogram (all losses chunks):")
print(f"  1-3 losses:   {sum(1 for s in streak_lens if 1 <= s <= 3)}")
print(f"  4-7 losses:   {sum(1 for s in streak_lens if 4 <= s <= 7)}")
print(f"  8-15 losses:  {sum(1 for s in streak_lens if 8 <= s <= 15)}")
print(f"  16-30 losses: {sum(1 for s in streak_lens if 16 <= s <= 30)}")
print(f"  31+ losses:   {sum(1 for s in streak_lens if s >= 31)}")

# ----- 2. Drawdown timeline -----
print("\n" + "=" * 70)
print("2. DRAWDOWN TIMELINE")
print("=" * 70)
eq['peak'] = eq['cum_r'].cummax()
eq['dd'] = eq['peak'] - eq['cum_r']
worst_idx = eq['dd'].idxmax()
peak_before_idx = eq.loc[:worst_idx, 'cum_r'].idxmax()

# Recovery: first index after worst_idx where cum_r >= peak_before
peak_value = eq.loc[peak_before_idx, 'cum_r']
recovery_mask = (eq.index > worst_idx) & (eq['cum_r'] >= peak_value)
recovered_at = eq.index[recovery_mask].min() if recovery_mask.any() else None

print(f"\nPeak before max DD: {peak_value:+.1f}R at {eq.loc[peak_before_idx, 'timestamp']}")
print(f"Trough:             {eq.loc[worst_idx, 'cum_r']:+.1f}R at {eq.loc[worst_idx, 'timestamp']}")
print(f"Max DD:             {eq.loc[worst_idx, 'dd']:.1f}R")

if recovered_at is not None:
    rec_t = eq.loc[recovered_at, 'timestamp']
    dd_duration = (rec_t - eq.loc[peak_before_idx, 'timestamp']).total_seconds() / 86400
    trades_in_dd = recovered_at - peak_before_idx
    print(f"Recovered at:       {rec_t}")
    print(f"DD duration:        {dd_duration:.1f} days, {trades_in_dd} trades from peak to recovery")
else:
    final_cum = eq['cum_r'].iloc[-1]
    still_below = peak_value - final_cum
    print(f"NOT YET RECOVERED at end of holdout (still {still_below:.1f}R below peak)")

# Top-5 drawdowns
print(f"\nTop 5 drawdowns >= 10R (with start/end peak):")
in_dd = False
dd_episodes = []
peak = -np.inf
peak_t = None
peak_idx = None
for idx, row in eq.iterrows():
    if row['cum_r'] > peak:
        if in_dd and (peak - eq.loc[trough_idx_local, 'cum_r']) >= 10:
            dd_episodes.append({
                'peak_t': peak_t, 'peak': peak,
                'trough_t': eq.loc[trough_idx_local, 'timestamp'],
                'trough': eq.loc[trough_idx_local, 'cum_r'],
                'dd': peak - eq.loc[trough_idx_local, 'cum_r'],
                'recovered_t': row['timestamp'],
                'days': (row['timestamp'] - peak_t).total_seconds() / 86400,
            })
        peak = row['cum_r']
        peak_t = row['timestamp']
        peak_idx = idx
        in_dd = False
        trough_local = peak
        trough_idx_local = idx
    else:
        if not in_dd:
            in_dd = True
            trough_local = row['cum_r']
            trough_idx_local = idx
        if row['cum_r'] < trough_local:
            trough_local = row['cum_r']
            trough_idx_local = idx
# tail open DD
if in_dd and (peak - eq.loc[trough_idx_local, 'cum_r']) >= 10:
    dd_episodes.append({
        'peak_t': peak_t, 'peak': peak,
        'trough_t': eq.loc[trough_idx_local, 'timestamp'],
        'trough': eq.loc[trough_idx_local, 'cum_r'],
        'dd': peak - eq.loc[trough_idx_local, 'cum_r'],
        'recovered_t': None,
        'days': (eq['timestamp'].iloc[-1] - peak_t).total_seconds() / 86400,
    })

dd_episodes.sort(key=lambda x: -x['dd'])
for d in dd_episodes[:5]:
    rec_str = str(d['recovered_t'])[:10] if d['recovered_t'] is not None else "OPEN"
    print(f"  DD {d['dd']:>5.1f}R | peak {d['peak']:>+5.1f} on {str(d['peak_t'])[:10]} -> trough {d['trough']:>+5.1f} on {str(d['trough_t'])[:10]} | recovered {rec_str} | {d['days']:.0f}d")

# ----- 3. Worst rolling 5-day window -----
print("\n" + "=" * 70)
print("3. WORST 5-TRADING-DAY WINDOWS")
print("=" * 70)
eq['date'] = eq['timestamp'].dt.date
daily = eq.groupby('date')['r'].sum().reset_index()
daily['rolling_5d'] = daily['r'].rolling(5).sum()
worst_5d = daily.nsmallest(5, 'rolling_5d')[['date', 'rolling_5d']]
print(f"\n{worst_5d.to_string(index=False)}")

# ----- 4. Hour-of-day expectancy -----
print("\n" + "=" * 70)
print("4. HOUR-OF-DAY EXPECTANCY")
print("=" * 70)
eq['hour'] = eq['timestamp'].dt.hour
by_hour = eq.groupby('hour').agg(trades=('r', 'count'), win_rate=('outcome_short', lambda x: (x=='win').mean()), exp=('r', 'mean'), net=('r', 'sum'))
print(f"\n{by_hour.to_string()}")

# ----- 5. Day-of-week -----
print("\n" + "=" * 70)
print("5. DAY-OF-WEEK EXPECTANCY")
print("=" * 70)
eq['dow_num'] = eq['timestamp'].dt.dayofweek
by_dow = eq.groupby('dow_num').agg(trades=('r', 'count'), win_rate=('outcome_short', lambda x: (x=='win').mean()), exp=('r', 'mean'), net=('r', 'sum'))
by_dow.index = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][:len(by_dow)]
print(f"\n{by_dow.to_string()}")

# ----- 6. Regime correlation: were losses in WRONG regime? -----
print("\n" + "=" * 70)
print("6. REGIME ALIGNMENT OF LOSSES")
print("=" * 70)
df_full = pd.read_csv(HOLDOUT_CSV, parse_dates=['timestamp'])
df_full = df_full[['timestamp', 'slope_sma_h4_200', 'mtf_with_h4_score', 'h4_alignment_duration']]
eq_with_regime = eq.merge(df_full, on='timestamp', how='left')

# For SHORTs we want H4 to be DOWN (h4_align negative). h4_alignment_duration < 0 = bear regime
eq_with_regime['h4_bearish'] = eq_with_regime['h4_alignment_duration'] < 0
eq_with_regime['mtf_bearish'] = eq_with_regime['mtf_with_h4_score'] < 0

print(f"\nWin rate by H4 alignment at trade entry:")
g = eq_with_regime.groupby('h4_bearish').agg(
    trades=('r', 'count'),
    win_rate=('outcome_short', lambda x: (x=='win').mean()),
    exp=('r', 'mean'),
    net=('r', 'sum'),
)
g.index = ['H4 BULLISH (regime mismatch)', 'H4 BEARISH (regime aligned)']
print(g.to_string())

print(f"\nWin rate by MTF score sign:")
g2 = eq_with_regime.groupby('mtf_bearish').agg(
    trades=('r', 'count'),
    win_rate=('outcome_short', lambda x: (x=='win').mean()),
    exp=('r', 'mean'),
    net=('r', 'sum'),
)
g2.index = ['MTF >= 0 (mismatch)', 'MTF < 0 (aligned)']
print(g2.to_string())

print(f"\nLoss-only regime breakdown:")
losses_only = eq_with_regime[eq_with_regime['outcome_short'] == 'loss']
print(f"  Total losses: {len(losses_only)}")
print(f"  Losses with H4 BULLISH (model fired into uptrend): {(losses_only['h4_alignment_duration'] >= 0).sum()} ({(losses_only['h4_alignment_duration'] >= 0).mean()*100:.1f}%)")
print(f"  Losses with H4 BEARISH (regime correct, just lost): {(losses_only['h4_alignment_duration'] < 0).sum()} ({(losses_only['h4_alignment_duration'] < 0).mean()*100:.1f}%)")

# ----- 7. Worst-month scrutiny -----
print("\n" + "=" * 70)
print("7. WORST MONTH (March 2026) DETAIL")
print("=" * 70)
march = eq[eq['timestamp'].dt.to_period('M').astype(str) == '2026-03'].copy()
march['date'] = march['timestamp'].dt.date
march_daily = march.groupby('date').agg(
    trades=('r', 'count'),
    wins=('outcome_short', lambda x: (x=='win').sum()),
    net=('r', 'sum'),
)
print(f"\nMarch 2026 daily: {len(march_daily)} trading days, total {march['r'].sum():+.1f}R")
print(f"\nDays with worst net R:")
print(march_daily.nsmallest(5, 'net').to_string())
print(f"\nDays with best net R:")
print(march_daily.nlargest(5, 'net').to_string())
