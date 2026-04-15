"""
Feature engineering and post-processing utilities
"""

import pandas as pd
import numpy as np
from typing import List, Optional


def get_feature_columns(df: pd.DataFrame) -> List[str]:
    """
    Extract feature column names from DataCollector CSV.

    Excludes timestamp, outcome columns, and bars_to_outcome columns.
    """
    exclude_patterns = [
        'timestamp',
        'symbol',  # string column, not a feature
        'outcome_long', 'outcome_short',
        'bars_to_outcome_long', 'bars_to_outcome_short',
        'label'  # if binary label was added
    ]

    features = [
        col for col in df.columns
        if not any(pattern in col for pattern in exclude_patterns)
    ]

    return features


def check_feature_distributions(
    df: pd.DataFrame,
    features: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Generate summary statistics for all features.

    Useful for sanity checking feature ranges and identifying outliers.
    """
    if features is None:
        features = get_feature_columns(df)

    stats = df[features].describe().T
    stats['nan_count'] = df[features].isna().sum()
    stats['inf_count'] = np.isinf(df[features]).sum()

    return stats


def drop_low_variance_features(
    df: pd.DataFrame,
    features: List[str],
    threshold: float = 0.01
) -> List[str]:
    """
    Identify and drop features with very low variance.

    Args:
        df: DataFrame
        features: List of feature column names
        threshold: Variance threshold (features below this are dropped)

    Returns:
        List of features to keep
    """
    variances = df[features].var()
    low_var = variances[variances < threshold].index.tolist()

    if low_var:
        print(f"Dropping {len(low_var)} low-variance features: {low_var}")

    keep_features = [f for f in features if f not in low_var]
    return keep_features


def get_highly_correlated_features(
    df: pd.DataFrame,
    features: List[str],
    threshold: float = 0.95
) -> List[tuple]:
    """
    Find pairs of highly correlated features.

    Returns list of (feature1, feature2, correlation) tuples.
    """
    corr_matrix = df[features].corr().abs()

    # Get upper triangle (avoid duplicates)
    upper = corr_matrix.where(
        np.triu(np.ones(corr_matrix.shape), k=1).astype(bool)
    )

    high_corr = [
        (col, row, corr_matrix.loc[row, col])
        for col in upper.columns
        for row in upper.index
        if upper.loc[row, col] > threshold
    ]

    return high_corr
