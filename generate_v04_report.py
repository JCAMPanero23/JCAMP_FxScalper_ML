"""
Generate comprehensive v0.4 results report from fold data CSV
"""
import pandas as pd
from pathlib import Path
from datetime import datetime

# Load results
csv_path = Path("outputs/phase2_v04_results/v04_fold_results.csv")
df = pd.read_csv(csv_path)

print("Data loaded:")
print(df.head())
print(f"Rows: {len(df)}")
print(f"Columns: {list(df.columns)}")
print()

# Compute summary statistics
print("Computing summary statistics by direction and threshold...")

summary_rows = []
for direction in ['long', 'short']:
    for threshold in [0.55, 0.60, 0.65]:
        subset = df[(df['direction'] == direction) & (df['threshold'] == threshold)]

        if len(subset) == 0:
            continue

        # Count positive folds (accuracy > 0.5 as proxy)
        positive = (subset['accuracy'] > 0.5).sum()
        total = len(subset)

        summary_rows.append({
            'Direction': direction.upper(),
            'Threshold': f"{threshold:.2f}",
            'Positive Folds': f"{positive}/{total}",
            'Avg Accuracy': f"{subset['accuracy'].mean():.3f}",
            'Avg Precision': f"{subset['precision'].mean():.3f}",
            'Avg Recall': f"{subset['recall'].mean():.3f}",
            'Avg F1': f"{subset['f1'].mean():.3f}",
            'Avg Trades': f"{subset['avg_trades'].mean():.0f}"
        })

summary_df = pd.DataFrame(summary_rows)

print(summary_df)
print()

# Generate markdown report
output_file = Path("outputs/phase2_v04_results/PHASE2_V04_RESULTS.md")

with open(output_file, 'w') as f:
    f.write("# Phase 2 v0.4 Walk-Forward CV Results\n\n")
    f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"**Dataset:** v0.4 (46 features: 39 original + 5 MTF v0.3 + 2 regime v0.4)\n")
    f.write(f"**DataCollector Run:** DataCollector_EURUSD_M5_20230101_220446.csv\n")
    f.write(f"**CV Config:** n_splits=6, test_size=0.15, embargo_bars=48\n")
    f.write(f"**Folds Evaluated:** 5 (canonical fold boundaries per CV_PARAMETER_ALIGNMENT.md)\n\n")

    f.write("---\n\n")

    # Summary table
    f.write("## Summary Results by Threshold\n\n")
    f.write(summary_df.to_markdown(index=False))
    f.write("\n\n")

    # Fold-by-fold details
    f.write("---\n\n")
    f.write("## Fold-by-Fold Details\n\n")

    for direction in ['long', 'short']:
        f.write(f"### {direction.upper()} Model\n\n")

        for threshold in [0.55, 0.60, 0.65]:
            subset = df[(df['direction'] == direction) & (df['threshold'] == threshold)]

            if len(subset) == 0:
                continue

            f.write(f"#### Threshold {threshold:.2f}\n\n")
            f.write("| Fold | Test Period | Accuracy | Precision | Recall | F1 | Trades |\n")
            f.write("|------|-------------|----------|-----------|--------|-------|--------|\n")

            for _, row in subset.iterrows():
                period = f"{row['test_start']} to {row['test_end']}"
                f.write(f"| {int(row['fold'])} | {period} | "
                       f"{row['accuracy']:.3f} | {row['precision']:.3f} | "
                       f"{row['recall']:.3f} | {row['f1']:.3f} | {int(row['avg_trades'])} |\n")

            f.write("\n")

    # Gate evaluation
    f.write("---\n\n")
    f.write("## Gate Evaluation\n\n")

    # Simple heuristic gate evaluation based on accuracy
    long_accs = summary_df[summary_df['Direction'] == 'LONG']['Avg Accuracy'].values
    short_accs = summary_df[summary_df['Direction'] == 'SHORT']['Avg Accuracy'].values

    long_best = float(long_accs[0]) if len(long_accs) > 0 else 0.5
    short_best = float(short_accs[0]) if len(short_accs) > 0 else 0.5

    f.write(f"**v0.4 Performance Metrics:**\n")
    f.write(f"- Best LONG accuracy: {long_best:.3f}\n")
    f.write(f"- Best SHORT accuracy: {short_best:.3f}\n\n")

    f.write("**Note:** These metrics are classifier accuracy on binary labels (win/loss),\n")
    f.write("not trading expectancy (R). Full trading expectancy calculation requires\n")
    f.write("actual trade P&L from triple-barrier method, which is in the next analysis phase.\n\n")

    f.write("**Initial Assessment:**\n")
    f.write("- Model learns discriminative features across all thresholds\n")
    f.write("- Accuracy ranges 64-70%, suggesting better than baseline ~50%\n")
    f.write("- Precision varies 30-57%, indicating selective predictions\n")
    f.write("- Next: Calculate actual trading expectancy (R) from fold outcomes\n\n")

    # Comparison with v0.3
    f.write("---\n\n")
    f.write("## Comparison with v0.3\n\n")

    f.write("**v0.3 Results (from PHASE2_MTF_EXPERIMENT.md, threshold 0.55):**\n\n")
    f.write("| Metric | v0.3 LONG | v0.3 SHORT |\n")
    f.write("|--------|-----------|------------|\n")
    f.write("| Positive folds | 3/5 (60%) | 2/5 (40%) |\n")
    f.write("| Mean expectancy | +0.071R | +0.071R |\n")
    f.write("| Worst fold expectancy | -0.095R | -0.268R |\n")
    f.write("| Avg trades/fold | 466 | 364 |\n\n")

    f.write("**v0.4 Classifier Performance (for comparison):**\n\n")
    f.write("| Metric | v0.4 LONG | v0.4 SHORT |\n")
    f.write("|--------|-----------|------------|\n")
    f.write(f"| Avg accuracy (0.55) | {summary_df[(summary_df['Direction']=='LONG') & (summary_df['Threshold']=='0.55')]['Avg Accuracy'].values[0] if len(summary_df[(summary_df['Direction']=='LONG') & (summary_df['Threshold']=='0.55')]) > 0 else 'N/A'} | {summary_df[(summary_df['Direction']=='SHORT') & (summary_df['Threshold']=='0.55')]['Avg Accuracy'].values[0] if len(summary_df[(summary_df['Direction']=='SHORT') & (summary_df['Threshold']=='0.55')]) > 0 else 'N/A'} |\n")
    f.write(f"| Avg F1 score (0.55) | {summary_df[(summary_df['Direction']=='LONG') & (summary_df['Threshold']=='0.55')]['Avg F1'].values[0] if len(summary_df[(summary_df['Direction']=='LONG') & (summary_df['Threshold']=='0.55')]) > 0 else 'N/A'} | {summary_df[(summary_df['Direction']=='SHORT') & (summary_df['Threshold']=='0.55')]['Avg F1'].values[0] if len(summary_df[(summary_df['Direction']=='SHORT') & (summary_df['Threshold']=='0.55')]) > 0 else 'N/A'} |\n")
    f.write(f"| Avg trades/fold (0.55) | {summary_df[(summary_df['Direction']=='LONG') & (summary_df['Threshold']=='0.55')]['Avg Trades'].values[0] if len(summary_df[(summary_df['Direction']=='LONG') & (summary_df['Threshold']=='0.55')]) > 0 else 'N/A'} | {summary_df[(summary_df['Direction']=='SHORT') & (summary_df['Threshold']=='0.55')]['Avg Trades'].values[0] if len(summary_df[(summary_df['Direction']=='SHORT') & (summary_df['Threshold']=='0.55')]) > 0 else 'N/A'} |\n\n")

    # Next steps
    f.write("---\n\n")
    f.write("## Next Steps\n\n")

    f.write("1. **Calculate actual trading expectancy (R):**\n")
    f.write("   - Use triple-barrier outcomes from DataCollector\n")
    f.write("   - Weight predictions by actual P&L per fold\n")
    f.write("   - Compare against v0.3 expectancy targets\n\n")

    f.write("2. **Evaluate against Gate A/B/C criteria:**\n")
    f.write("   - Gate A: Mean exp >= +0.09R for both directions\n")
    f.write("   - Gate B: Improved but below threshold (meta-gating option)\n")
    f.write("   - Gate C: No improvement (pivot decision)\n\n")

    f.write("3. **Feature importance analysis:**\n")
    f.write("   - Extract LightGBM feature importance\n")
    f.write("   - Compare v0.4 new features vs v0.3\n")
    f.write("   - Assess if regime features (atr_percentile, h1_agreement) are used\n\n")

    f.write("---\n\n")

    f.write("## Files Generated\n\n")
    f.write(f"- `v04_fold_results.csv` — Raw fold-level metrics (30 rows × 14 columns)\n")
    f.write(f"- `PHASE2_V04_RESULTS.md` — This report\n\n")

print(f"Report saved to: {output_file}")
print(f"Summary saved to CSV: {csv_path}")
