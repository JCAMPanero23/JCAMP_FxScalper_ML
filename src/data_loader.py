"""
Data loading utilities for JCAMP FxScalper ML
Loads CSV from DataCollector and prepares train/test splits
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Tuple, Optional
from datetime import datetime


def load_datacollector_csv(
    csv_path: str,
    parse_dates: bool = True
) -> pd.DataFrame:
    """
    Load CSV from DataCollector cBot.

    Args:
        csv_path: Path to CSV file
        parse_dates: Whether to parse timestamp column

    Returns:
        DataFrame with all features and labels
    """
    df = pd.read_csv(csv_path)

    if parse_dates and 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])

    return df


def get_data_splits(
    df: pd.DataFrame,
    train_end: str = "2025-09-30",
    test_end: str = "2026-03-31",
    timestamp_col: str = "timestamp"
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Split data into train/CV, held-out test, and live forward sets.

    As per PRD:
    - Train/CV: Jan 2023 - Sep 2025 (for walk-forward CV)
    - Held-out test: Oct 2025 - Mar 2026 (TOUCH ONCE ONLY)
    - Live forward: Apr 2026 onward

    Args:
        df: Full dataframe with timestamp column
        train_end: End date for training set (inclusive)
        test_end: End date for held-out test set (inclusive)
        timestamp_col: Name of timestamp column

    Returns:
        (train_cv, held_out_test, live_forward) DataFrames
    """
    df = df.sort_values(timestamp_col).reset_index(drop=True)

    train_cv = df[df[timestamp_col] <= train_end].copy()
    held_out_test = df[
        (df[timestamp_col] > train_end) &
        (df[timestamp_col] <= test_end)
    ].copy()
    live_forward = df[df[timestamp_col] > test_end].copy()

    return train_cv, held_out_test, live_forward


def validate_data_quality(df: pd.DataFrame, verbose: bool = True) -> dict:
    """
    Run data quality checks on loaded DataFrame.

    Returns dict with check results.
    """
    results = {
        "total_rows": len(df),
        "nan_count": df.isna().sum().sum(),
        "inf_count": np.isinf(df.select_dtypes(include=[np.number])).sum().sum(),
        "duplicate_timestamps": df.duplicated(subset=['timestamp']).sum() if 'timestamp' in df.columns else 0,
        "passed": True
    }

    # Check for NaN/Inf
    if results["nan_count"] > 0 or results["inf_count"] > 0:
        results["passed"] = False

    if verbose:
        print(f"Data quality check:")
        print(f"  Total rows: {results['total_rows']:,}")
        print(f"  NaN values: {results['nan_count']}")
        print(f"  Inf values: {results['inf_count']}")
        print(f"  Duplicate timestamps: {results['duplicate_timestamps']}")
        print(f"  Status: {'✓ PASSED' if results['passed'] else '✗ FAILED'}")

    return results
