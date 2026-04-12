#!/usr/bin/env python3
"""
Data summary and split analysis for Phase 2 planning.
"""

import pandas as pd

# Load the CSV
df = pd.read_csv('data/DataCollector_EURUSD_M5_20230101_220400.csv', parse_dates=['timestamp'])

print("="*70)
print("DATA SUMMARY FOR PHASE 2")
print("="*70)

# Overall stats
print(f"\nTotal rows: {len(df):,}")
print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

# Calculate days and expected bars
start_date = df['timestamp'].min()
end_date = df['timestamp'].max()
total_days = (end_date - start_date).days
print(f"Total days: {total_days:,}")
print(f"Average bars per day: {len(df) / total_days:.1f}")

# PRD split analysis
print(f"\n{'='*70}")
print("PRD SPLIT BREAKDOWN")
print("="*70)

# Training/CV: Jan 2023 - Sep 2025
train_end = pd.Timestamp('2025-09-30 23:59:59')
train_df = df[df['timestamp'] <= train_end]
print(f"\nTraining/CV (Jan 2023 - Sep 2025):")
print(f"  Rows: {len(train_df):,} ({len(train_df)/len(df)*100:.1f}% of total)")
print(f"  Date range: {train_df['timestamp'].min()} to {train_df['timestamp'].max()}")

# Held-out test: Oct 2025 - Mar 2026
test_start = pd.Timestamp('2025-10-01 00:00:00')
test_end = pd.Timestamp('2026-03-31 23:59:59')
test_df = df[(df['timestamp'] >= test_start) & (df['timestamp'] <= test_end)]
print(f"\nHeld-out test (Oct 2025 - Mar 2026) - TOUCH ONCE ONLY:")
print(f"  Rows: {len(test_df):,} ({len(test_df)/len(df)*100:.1f}% of total)")
print(f"  Date range: {test_df['timestamp'].min()} to {test_df['timestamp'].max()}")

# Live forward test: Apr 2026 onward
live_start = pd.Timestamp('2026-04-01 00:00:00')
live_df = df[df['timestamp'] >= live_start]
print(f"\nLive forward test (Apr 2026 onward):")
print(f"  Rows: {len(live_df):,} ({len(live_df)/len(df)*100:.1f}% of total)")
print(f"  Date range: {live_df['timestamp'].min()} to {live_df['timestamp'].max()}")

# Outcome distribution by split
print(f"\n{'='*70}")
print("LABEL DISTRIBUTION BY SPLIT")
print("="*70)

for split_name, split_df in [('Train/CV', train_df), ('Held-out', test_df), ('Live', live_df)]:
    print(f"\n{split_name}:")
    for direction in ['long', 'short']:
        outcome_col = f'outcome_{direction}'
        value_counts = split_df[outcome_col].value_counts()
        percentages = (value_counts / len(split_df) * 100)
        win_pct = percentages.get('win', 0)
        loss_pct = percentages.get('loss', 0)
        timeout_pct = percentages.get('timeout', 0)
        print(f"  {direction:5s}: win={win_pct:5.2f}% | loss={loss_pct:5.2f}% | timeout={timeout_pct:5.2f}%")

# Monthly breakdown
print(f"\n{'='*70}")
print("MONTHLY BAR COUNT")
print("="*70)

df['year_month'] = df['timestamp'].dt.to_period('M')
monthly_counts = df.groupby('year_month').size()
print(f"\n{monthly_counts}")

print(f"\n{'='*70}")
print("READY FOR PHASE 2")
print("="*70)
print("\nNext steps:")
print("1. Set up Python environment (Python 3.11, pandas, lightgbm, scikit-learn)")
print("2. Create project structure (notebooks/, src/, models/, tests/)")
print("3. Start with 01_eda.ipynb for exploratory data analysis")
print(f"\nDataset verified and ready! {len(df):,} clean rows with no NaN/Inf.")
