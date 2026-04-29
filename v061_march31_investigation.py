"""
March 31, 2026 SHORT Failure Investigation

Holdout SHORT @ thr=0.55 fired 37 trades on this single day. All 37 lost.
Net -37R, 24% of total holdout profit destroyed in one session.

This script answers:
  1. What did EURUSD do on March 31? (price move, ATR, range)
  2. Were the 37 entries clustered or spread out?
  3. What was the H4 regime that day? Was it FLIPPING during the day?
  4. Which features distinguish March 31 losing entries from typical wins?
  5. How does March 31 compare to the surrounding ~5 days of the 39-loss streak?
"""

import pandas as pd
import numpy as np
from pathlib import Path
import joblib

DATA_PATH = Path("data/DataCollector_EURUSD_M5_20230102_000000.csv")
EQUITY_CSV = Path("outputs/holdout_test_v061/short/holdout_equity_curve.csv")
MODEL_PATH = Path("models/eurusd_short_v061.joblib")

print("=" * 70)
print("MARCH 31, 2026 -- SHORT FAILURE FORENSICS")
print("=" * 70)

# Load the full bar data for context
df = pd.read_csv(DATA_PATH, parse_dates=['timestamp'])
df = df.sort_values('timestamp').reset_index(drop=True)

# March 30 - April 1 window for full context
window = df[(df['timestamp'] >= '2026-03-29') & (df['timestamp'] <= '2026-04-01')].copy()
print(f"\nLoaded {len(window)} M5 bars from 2026-03-29 to 2026-04-01")

# Load equity curve to see WHICH bars on Mar 31 were traded
eq = pd.read_csv(EQUITY_CSV, parse_dates=['timestamp'])
mar31 = eq[eq['timestamp'].dt.date == pd.to_datetime('2026-03-31').date()].copy()
print(f"\n{len(mar31)} traded bars on Mar 31, all SHORT entries")

# ----- 1. Price action on March 31 -----
print("\n" + "=" * 70)
print("1. PRICE ACTION (Mar 30 -> Apr 1)")
print("=" * 70)

# Need close column - check what columns we have
print(f"\nAvailable columns: {[c for c in window.columns if c in ['close','open','high','low','atr_m5','atr_m15','atr_h1']]}")

# We don't have raw OHLC -- need to derive what we can from features
# But we can look at slope and atr behaviour
mar31_bars = window[window['timestamp'].dt.date == pd.to_datetime('2026-03-31').date()]
print(f"\nMar 31 bar count: {len(mar31_bars)}")

# Daily summary using slope features
print(f"\nKey feature ranges on Mar 31:")
for col in ['slope_sma_h4_200', 'slope_sma_h1_200', 'slope_sma_m5_200',
            'mtf_with_h4_score', 'h4_alignment_duration', 'mtf_alignment_duration',
            'atr_m5', 'atr_h1', 'rsi_m5', 'rsi_h1', 'adx_m5']:
    if col in mar31_bars.columns:
        vals = mar31_bars[col]
        print(f"  {col:<28} min={vals.min():>+9.4f} max={vals.max():>+9.4f} mean={vals.mean():>+9.4f}")

# ----- 2. Entry timing on March 31 -----
print("\n" + "=" * 70)
print("2. ENTRY TIMING ON MAR 31")
print("=" * 70)
mar31_sorted = mar31.sort_values('timestamp')
print(f"\nFirst entry: {mar31_sorted['timestamp'].min()}")
print(f"Last entry:  {mar31_sorted['timestamp'].max()}")
print(f"\nEntry hour distribution:")
mar31_sorted['hour'] = mar31_sorted['timestamp'].dt.hour
hour_counts = mar31_sorted.groupby('hour').size()
for h, cnt in hour_counts.items():
    print(f"  {h:02d}:00 UTC -> {cnt} entries")

# Time gaps between consecutive entries
mar31_sorted['gap_min'] = mar31_sorted['timestamp'].diff().dt.total_seconds() / 60
print(f"\nEntry gap stats (min between consecutive trades):")
print(f"  Mean: {mar31_sorted['gap_min'].mean():.1f}, Median: {mar31_sorted['gap_min'].median():.1f}, Max: {mar31_sorted['gap_min'].max():.1f}")
back_to_back = (mar31_sorted['gap_min'] <= 5).sum()
print(f"  Back-to-back (5min apart): {back_to_back}/{len(mar31_sorted)-1} consecutive pairs")

# ----- 3. H4 regime stability on March 31 -----
print("\n" + "=" * 70)
print("3. H4 REGIME ON MAR 31")
print("=" * 70)
# h4_alignment_duration: positive = bullish run, negative = bearish run
mar31_full = window[window['timestamp'].dt.date == pd.to_datetime('2026-03-31').date()]
print(f"\nh4_alignment_duration over the day:")
print(f"  Bar 1 (00:00): {mar31_full.iloc[0]['h4_alignment_duration']:+.0f}")
print(f"  Bar 144 (mid):  {mar31_full.iloc[len(mar31_full)//2]['h4_alignment_duration']:+.0f}")
print(f"  Last bar:       {mar31_full.iloc[-1]['h4_alignment_duration']:+.0f}")
print(f"  Range:  min={mar31_full['h4_alignment_duration'].min():+.0f}, max={mar31_full['h4_alignment_duration'].max():+.0f}")
flips = (mar31_full['h4_alignment_duration'].diff().abs() > 1).sum()
print(f"  H4 alignment flips during day: {flips}")

print(f"\nslope_sma_h4_200 over the day (positive = uptrend, negative = downtrend):")
print(f"  Min: {mar31_full['slope_sma_h4_200'].min():+.4f} | Max: {mar31_full['slope_sma_h4_200'].max():+.4f}")
print(f"  Pct of bars with H4 slope > 0 (BULLISH): {(mar31_full['slope_sma_h4_200'] > 0).mean()*100:.1f}%")

# ----- 4. Compare Mar 31 entries to typical winning entries -----
print("\n" + "=" * 70)
print("4. MAR 31 LOSING ENTRIES vs HOLDOUT WINNING ENTRIES")
print("=" * 70)

# Merge equity with full feature data (drop duplicate outcome col before merge)
df_full = pd.read_csv(DATA_PATH, parse_dates=['timestamp'])
df_full_no_outcome = df_full.drop(columns=['outcome_short', 'outcome_long'], errors='ignore')
eq_features = eq.merge(df_full_no_outcome, on='timestamp', how='left')

mar31_features = eq_features[eq_features['timestamp'].dt.date == pd.to_datetime('2026-03-31').date()]
winning_features = eq_features[(eq_features['outcome_short'] == 'win') &
                                (eq_features['timestamp'].dt.date != pd.to_datetime('2026-03-31').date())]

key_feats = ['p_win', 'slope_sma_h4_200', 'slope_sma_h1_200', 'slope_sma_m5_200',
             'mtf_with_h4_score', 'h4_alignment_duration', 'mtf_alignment_duration',
             'rsi_m5', 'rsi_h1', 'rsi_h4', 'atr_m5', 'atr_h1', 'adx_m5',
             'dist_sma_h4_200', 'dist_sma_h1_200']

key_feats = [f for f in key_feats if f in eq_features.columns]
print(f"\nFeature comparison (median values):")
print(f"  {'Feature':<28} {'Mar31 loss':>12} {'Other wins':>12} {'Delta':>10}")
for f in key_feats:
    m31 = mar31_features[f].median()
    win = winning_features[f].median()
    delta = m31 - win
    flag = "  <-- DIFFERS" if abs(delta) > abs(win) * 0.5 and abs(win) > 0.01 else ""
    print(f"  {f:<28} {m31:>+12.4f} {win:>+12.4f} {delta:>+10.4f}{flag}")

# ----- 5. Day-by-day during 39-loss streak -----
print("\n" + "=" * 70)
print("5. THE 39-LOSS STREAK (Mar 20 -> Mar 31) - DAY BY DAY")
print("=" * 70)
streak_window = eq[(eq['timestamp'] >= '2026-03-20') & (eq['timestamp'] <= '2026-03-31')].copy()
streak_window['date'] = streak_window['timestamp'].dt.date
daily = streak_window.groupby('date').agg(
    trades=('r', 'count'),
    wins=('outcome_short', lambda x: (x == 'win').sum()),
    losses=('outcome_short', lambda x: (x == 'loss').sum()),
    net_r=('r', 'sum'),
    p_win_mean=('p_win', 'mean'),
    p_win_max=('p_win', 'max'),
)
print(daily.to_string())

# ----- 6. p_win distribution on Mar 31 vs avg -----
print("\n" + "=" * 70)
print("6. MODEL CONFIDENCE ON MAR 31")
print("=" * 70)
print(f"\nMar 31 p_win stats: n={len(mar31)}, mean={mar31['p_win'].mean():.4f}, "
      f"median={mar31['p_win'].median():.4f}, max={mar31['p_win'].max():.4f}")
print(f"All winning trades p_win: mean={winning_features['p_win'].mean():.4f}, "
      f"median={winning_features['p_win'].median():.4f}")
print(f"\nWere Mar 31 entries low-confidence (just above 0.55 threshold)?")
high_conf_m31 = (mar31['p_win'] > 0.65).sum()
high_conf_wins = (winning_features['p_win'] > 0.65).sum()
print(f"  Mar 31 entries with p > 0.65: {high_conf_m31}/{len(mar31)} ({high_conf_m31/len(mar31)*100:.0f}%)")
print(f"  Winning entries with p > 0.65: {high_conf_wins}/{len(winning_features)} ({high_conf_wins/len(winning_features)*100:.0f}%)")

# Would a higher threshold have skipped Mar 31?
print(f"\nWhat if we'd used a higher threshold on Mar 31?")
for thr in [0.60, 0.65, 0.70]:
    n_at_thr = (mar31['p_win'] > thr).sum()
    print(f"  thr {thr}: would have taken {n_at_thr} trades on Mar 31 (vs 37 actual)")
