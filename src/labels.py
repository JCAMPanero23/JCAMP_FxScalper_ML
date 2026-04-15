"""
Label processing utilities for triple-barrier outcomes
Converts 3-class outcomes (win/loss/timeout) to binary classification
"""

import pandas as pd
import numpy as np
from typing import Literal


def collapse_to_binary(
    df: pd.DataFrame,
    direction: Literal["long", "short"],
    timeout_as: Literal["loss", "win", "drop"] = "loss"
) -> pd.DataFrame:
    """
    Convert 3-class triple-barrier labels to binary classification.

    Args:
        df: DataFrame with outcome_long/outcome_short columns
        direction: "long" or "short"
        timeout_as: How to handle timeout cases:
            - "loss": treat timeouts as losses (pessimistic, default)
            - "win": treat timeouts as wins (optimistic)
            - "drop": remove timeout rows from dataset

    Returns:
        DataFrame with new binary 'label' column (1=win, 0=loss)
    """
    df = df.copy()
    outcome_col = f"outcome_{direction}"

    if outcome_col not in df.columns:
        raise ValueError(f"Column '{outcome_col}' not found in DataFrame")

    # Create binary label
    if timeout_as == "drop":
        df = df[df[outcome_col] != "timeout"].copy()
        df["label"] = (df[outcome_col] == "win").astype(int)
    elif timeout_as == "loss":
        df["label"] = (df[outcome_col] == "win").astype(int)
    elif timeout_as == "win":
        df["label"] = ((df[outcome_col] == "win") | (df[outcome_col] == "timeout")).astype(int)
    else:
        raise ValueError(f"Invalid timeout_as value: {timeout_as}")

    return df


def get_label_balance(df: pd.DataFrame, direction: Literal["long", "short"]) -> dict:
    """
    Calculate label balance statistics for a direction.

    Returns dict with counts and percentages.
    """
    outcome_col = f"outcome_{direction}"

    if outcome_col not in df.columns:
        raise ValueError(f"Column '{outcome_col}' not found")

    counts = df[outcome_col].value_counts()
    total = len(df)

    balance = {
        "total": total,
        "win_count": counts.get("win", 0),
        "loss_count": counts.get("loss", 0),
        "timeout_count": counts.get("timeout", 0),
        "win_pct": counts.get("win", 0) / total * 100,
        "loss_pct": counts.get("loss", 0) / total * 100,
        "timeout_pct": counts.get("timeout", 0) / total * 100,
    }

    return balance


def print_label_summary(df: pd.DataFrame) -> None:
    """
    Print label balance for both long and short directions.
    """
    print("\n=== Label Balance Summary ===")

    for direction in ["long", "short"]:
        balance = get_label_balance(df, direction)
        print(f"\n{direction.upper()}:")
        print(f"  Win:     {balance['win_count']:6,} ({balance['win_pct']:5.1f}%)")
        print(f"  Loss:    {balance['loss_count']:6,} ({balance['loss_pct']:5.1f}%)")
        print(f"  Timeout: {balance['timeout_count']:6,} ({balance['timeout_pct']:5.1f}%)")
        print(f"  Total:   {balance['total']:6,}")
