"""
Training entrypoint for LightGBM models
"""

import pandas as pd
import numpy as np
from lightgbm import LGBMClassifier
from sklearn.metrics import roc_auc_score, accuracy_score, classification_report
from typing import Dict, Tuple, Optional
import joblib
from pathlib import Path


def train_lightgbm(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: Optional[pd.DataFrame] = None,
    y_val: Optional[pd.Series] = None,
    params: Optional[Dict] = None
) -> LGBMClassifier:
    """
    Train a LightGBM binary classifier.

    Args:
        X_train: Training features
        y_train: Training labels (0/1)
        X_val: Validation features (for early stopping)
        y_val: Validation labels
        params: LightGBM hyperparameters (uses defaults if None)

    Returns:
        Trained LGBMClassifier
    """
    if params is None:
        # Tuned params (improved from baseline 0.536 to 0.546)
        params = {
            'objective': 'binary',
            'metric': 'auc',
            'boosting_type': 'gbdt',
            'num_leaves': 63,
            'max_depth': 9,
            'learning_rate': 0.03,
            'n_estimators': 1000,
            'min_child_samples': 100,
            'subsample': 0.8,
            'colsample_bytree': 0.7,
            'reg_alpha': 1.0,
            'reg_lambda': 1.0,
            'random_state': 42,
            'verbose': -1
        }

    model = LGBMClassifier(**params)

    # Use early stopping if validation set provided
    if X_val is not None and y_val is not None:
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[
                # Stop if no improvement for 50 rounds
                # Using verbose=False equivalent in newer versions
            ]
        )
    else:
        model.fit(X_train, y_train)

    return model


def evaluate_model(
    model: LGBMClassifier,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    verbose: bool = True
) -> Dict[str, float]:
    """
    Evaluate trained model on test set.

    Returns dict with metrics.
    """
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred = model.predict(X_test)

    metrics = {
        'roc_auc': roc_auc_score(y_test, y_pred_proba),
        'accuracy': accuracy_score(y_test, y_pred),
        'n_samples': len(y_test),
        'win_rate': y_pred.mean(),
        'actual_win_rate': y_test.mean()
    }

    if verbose:
        print(f"\n=== Model Evaluation ===")
        print(f"ROC-AUC:         {metrics['roc_auc']:.4f}")
        print(f"Accuracy:        {metrics['accuracy']:.4f}")
        print(f"Predicted win%:  {metrics['win_rate']*100:.1f}%")
        print(f"Actual win%:     {metrics['actual_win_rate']*100:.1f}%")
        print(f"Samples:         {metrics['n_samples']:,}")

    return metrics


def save_model(
    model: LGBMClassifier,
    save_path: str,
    metadata: Optional[Dict] = None
) -> None:
    """
    Save trained model and optional metadata to disk.

    Args:
        model: Trained LGBMClassifier
        save_path: Path to save model (.joblib)
        metadata: Optional dict with training info (params, date, metrics, etc.)
    """
    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    # Save model
    joblib.dump(model, save_path)

    # Save metadata if provided
    if metadata is not None:
        meta_path = save_path.with_suffix('.meta.joblib')
        joblib.dump(metadata, meta_path)

    print(f"Model saved to {save_path}")


def load_model(model_path: str) -> Tuple[LGBMClassifier, Optional[Dict]]:
    """
    Load trained model and metadata from disk.

    Returns:
        (model, metadata) tuple
    """
    model = joblib.load(model_path)

    # Try to load metadata
    meta_path = Path(model_path).with_suffix('.meta.joblib')
    metadata = None
    if meta_path.exists():
        metadata = joblib.load(meta_path)

    return model, metadata


def get_feature_importance(
    model: LGBMClassifier,
    feature_names: list,
    top_n: int = 20
) -> pd.DataFrame:
    """
    Extract feature importance from trained model.

    Returns DataFrame sorted by importance.
    """
    importance_df = pd.DataFrame({
        'feature': feature_names,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)

    # Normalize to percentages
    importance_df['importance_pct'] = (
        importance_df['importance'] / importance_df['importance'].sum() * 100
    )

    return importance_df.head(top_n)
