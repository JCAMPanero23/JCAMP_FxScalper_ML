"""
Purged walk-forward cross-validation implementation
Uses mlfinlab's PurgedKFold to prevent leakage across folds
"""

import numpy as np
import pandas as pd
from typing import Generator, Tuple
from sklearn.model_selection import KFold


class PurgedWalkForward:
    """
    Purged walk-forward cross-validation for time series.

    Implements embargo period to prevent look-ahead bias when labels
    have variable time horizons (triple-barrier labels can take 1-48 bars).

    Based on Advances in Financial Machine Learning (Lopez de Prado, 2018).
    """

    def __init__(
        self,
        n_splits: int = 6,
        embargo_bars: int = 48,
        test_size: float = 0.15
    ):
        """
        Args:
            n_splits: Number of CV folds
            embargo_bars: Number of bars to embargo between train/test
                         (set to max bars_to_outcome to prevent leakage)
            test_size: Fraction of each fold to use for testing
        """
        self.n_splits = n_splits
        self.embargo_bars = embargo_bars
        self.test_size = test_size

    def split(
        self,
        X: pd.DataFrame,
        y: pd.Series = None,
        bars_to_outcome: pd.Series = None
    ) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        """
        Generate train/test splits with purging and embargo.

        Args:
            X: Feature matrix (needs index for chronological ordering)
            y: Target labels (optional, not used but kept for sklearn compat)
            bars_to_outcome: Number of bars each label looks forward
                           (if provided, enables precise purging)

        Yields:
            (train_indices, test_indices) for each fold
        """
        n_samples = len(X)
        indices = np.arange(n_samples)

        # Calculate fold size
        fold_size = n_samples // self.n_splits
        test_fold_size = int(fold_size * self.test_size)

        for fold_idx in range(self.n_splits):
            # Walk-forward: test set moves forward each fold
            test_start = fold_idx * fold_size
            test_end = test_start + test_fold_size

            if test_end > n_samples:
                break

            # Test indices
            test_indices = indices[test_start:test_end]

            # Train indices: everything before test set
            # Apply embargo: exclude embargo_bars before test set
            train_end = max(0, test_start - self.embargo_bars)
            train_indices = indices[:train_end]

            # Purge: if we have bars_to_outcome, remove training samples
            # whose labels overlap with the test period
            if bars_to_outcome is not None:
                train_indices = self._purge_train_set(
                    train_indices,
                    test_start,
                    bars_to_outcome
                )

            if len(train_indices) > 0 and len(test_indices) > 0:
                yield train_indices, test_indices

    def _purge_train_set(
        self,
        train_indices: np.ndarray,
        test_start: int,
        bars_to_outcome: pd.Series
    ) -> np.ndarray:
        """
        Remove training samples whose labels overlap with test period.

        A training sample at index i should be removed if:
            i + bars_to_outcome[i] >= test_start
        """
        bars_array = bars_to_outcome.iloc[train_indices].values
        end_indices = train_indices + bars_array

        # Keep only samples that end before test period
        valid_mask = end_indices < test_start
        purged_train = train_indices[valid_mask]

        return purged_train

    def get_n_splits(self, X=None, y=None, groups=None):
        """Return number of splits (for sklearn compatibility)."""
        return self.n_splits
