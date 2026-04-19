"""
Model evaluation utilities: metrics, equity curves, performance reports
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, Optional, List
from sklearn.metrics import confusion_matrix, roc_curve, auc


def calculate_trading_metrics(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    threshold: float = 0.55,
    risk_reward: float = 3.0,
    commission_r: float = 0.0
) -> Dict[str, float]:
    """
    Calculate trading metrics for a probability-based entry filter.

    Only counts trades where y_pred_proba >= threshold. For each such trade,
    a win returns +risk_reward R and a loss returns -1 R, minus commission_r
    applied to every trade.

    Args:
        y_true: Actual outcomes (0=loss, 1=win)
        y_pred_proba: Predicted win probabilities (0-1)
        threshold: Minimum probability to take trade
        risk_reward: Reward/risk ratio (TP/SL), e.g., 4.5/1.5 = 3.0
        commission_r: Commission cost as fraction of R (e.g., 0.04 = 4% of 1R)

    Returns:
        Dict with total_trades, wins, losses, win_rate, profit_factor,
        expectancy_r, net_profit_r, gross_profit_r, gross_loss_r,
        selection_rate, threshold_used
    """
    # Filter to high-confidence bars only
    selected = y_pred_proba >= threshold
    n_total_bars = len(y_true)
    n_trades = int(selected.sum())

    if n_trades == 0:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "expectancy_r": 0.0,
            "net_profit_r": 0.0,
            "gross_profit_r": 0.0,
            "gross_loss_r": 0.0,
            "selection_rate": 0.0,
            "threshold_used": float(threshold),
        }

    y_selected = y_true[selected]
    wins = int((y_selected == 1).sum())
    losses = int((y_selected == 0).sum())

    # P&L per trade, net of commission
    gross_profit_r = wins * risk_reward - wins * commission_r
    gross_loss_r = losses * 1.0 + losses * commission_r
    net_profit_r = gross_profit_r - gross_loss_r

    win_rate = wins / n_trades
    profit_factor = (
        gross_profit_r / gross_loss_r if gross_loss_r > 0 else float("inf")
    )
    expectancy_r = net_profit_r / n_trades

    return {
        "total_trades": n_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 4),
        "profit_factor": round(profit_factor, 4),
        "expectancy_r": round(expectancy_r, 4),
        "net_profit_r": round(net_profit_r, 2),
        "gross_profit_r": round(gross_profit_r, 2),
        "gross_loss_r": round(gross_loss_r, 2),
        "selection_rate": round(n_trades / n_total_bars, 4),
        "threshold_used": float(threshold),
    }


def simulate_equity_curve(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    threshold: float = 0.5,
    risk_reward: float = 3.0,
    starting_capital_r: float = 100.0
) -> pd.DataFrame:
    """
    Simulate equity curve from model predictions.

    Args:
        y_true: Actual outcomes
        y_pred_proba: Predicted win probabilities
        threshold: Probability threshold for taking trades
        risk_reward: Reward/risk ratio
        starting_capital_r: Starting capital in R-multiples

    Returns:
        DataFrame with trade-by-trade equity curve
    """
    # Filter trades by threshold
    trade_mask = (y_pred_proba >= threshold)

    if trade_mask.sum() == 0:
        return pd.DataFrame({'equity_r': [starting_capital_r]})

    y_true_filtered = y_true[trade_mask]

    # Calculate P&L per trade
    pnl_per_trade = np.where(y_true_filtered == 1, risk_reward, -1.0)

    # Cumulative equity
    equity = starting_capital_r + np.cumsum(pnl_per_trade)
    equity = np.concatenate([[starting_capital_r], equity])

    equity_df = pd.DataFrame({
        'trade_num': range(len(equity)),
        'equity_r': equity
    })

    return equity_df


def plot_equity_curve(
    equity_df: pd.DataFrame,
    title: str = "Equity Curve",
    figsize: tuple = (12, 6)
) -> plt.Figure:
    """
    Plot equity curve.

    Returns matplotlib Figure.
    """
    fig, ax = plt.subplots(figsize=figsize)

    ax.plot(equity_df['trade_num'], equity_df['equity_r'], linewidth=1.5)
    ax.axhline(y=equity_df['equity_r'].iloc[0], color='gray', linestyle='--', alpha=0.5)
    ax.set_xlabel('Trade Number')
    ax.set_ylabel('Equity (R-multiples)')
    ax.set_title(title)
    ax.grid(True, alpha=0.3)

    # Add final stats as text
    final_r = equity_df['equity_r'].iloc[-1]
    start_r = equity_df['equity_r'].iloc[0]
    net_r = final_r - start_r

    ax.text(
        0.02, 0.98,
        f'Net P&L: {net_r:+.1f}R\nFinal: {final_r:.1f}R',
        transform=ax.transAxes,
        verticalalignment='top',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    )

    plt.tight_layout()
    return fig


def plot_roc_curve(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    title: str = "ROC Curve",
    figsize: tuple = (8, 6)
) -> plt.Figure:
    """
    Plot ROC curve.
    """
    fpr, tpr, thresholds = roc_curve(y_true, y_pred_proba)
    roc_auc = auc(fpr, tpr)

    fig, ax = plt.subplots(figsize=figsize)

    ax.plot(fpr, tpr, linewidth=2, label=f'ROC (AUC = {roc_auc:.3f})')
    ax.plot([0, 1], [0, 1], 'k--', linewidth=1, label='Random')
    ax.set_xlabel('False Positive Rate')
    ax.set_ylabel('True Positive Rate')
    ax.set_title(title)
    ax.legend(loc='lower right')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    return fig


def print_performance_summary(
    metrics: Dict[str, float],
    model_name: str = "Model"
) -> None:
    """
    Print formatted performance summary.
    """
    print(f"\n{'='*50}")
    print(f"{model_name} Performance Summary")
    print(f"{'='*50}")
    print(f"Total trades:     {metrics['total_trades']:,}")
    print(f"Wins:             {metrics['wins']:,}")
    print(f"Losses:           {metrics['losses']:,}")
    print(f"Win rate:         {metrics['win_rate']*100:.1f}%")
    print(f"Profit factor:    {metrics['profit_factor']:.2f}")
    print(f"Expectancy:       {metrics['expectancy_r']:+.3f}R")
    print(f"Net P&L:          {metrics['net_profit_r']:+.1f}R")
    print(f"{'='*50}\n")


def plot_threshold_sensitivity(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    risk_reward: float = 3.0,
    commission_r: float = 0.04,
    thresholds: np.ndarray = None,
    title: str = "Threshold Sensitivity",
):
    """
    Plot how trade count, win rate, profit factor, and expectancy vary across
    probability thresholds. A robust edge shows a wide plateau of positive
    expectancy. An overfit edge shows a sharp peak.

    Args:
        y_true: Actual outcomes
        y_pred_proba: Predicted probabilities
        risk_reward: Reward/risk ratio
        commission_r: Commission as fraction of R
        thresholds: Array of thresholds to test (default: 0.40 to 0.80)
        title: Plot title

    Returns:
        (fig, df) tuple with matplotlib Figure and results DataFrame
    """
    if thresholds is None:
        thresholds = np.arange(0.40, 0.81, 0.01)

    rows = []
    for thr in thresholds:
        m = calculate_trading_metrics(
            y_true, y_pred_proba,
            threshold=thr,
            risk_reward=risk_reward,
            commission_r=commission_r,
        )
        rows.append({
            "threshold": thr,
            "n_trades": m["total_trades"],
            "win_rate": m["win_rate"],
            "profit_factor": m["profit_factor"],
            "expectancy_r": m["expectancy_r"],
            "net_profit_r": m["net_profit_r"],
        })

    df = pd.DataFrame(rows)

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    fig.suptitle(title, fontsize=14)

    axes[0, 0].plot(df["threshold"], df["n_trades"], marker=".")
    axes[0, 0].set_xlabel("Threshold")
    axes[0, 0].set_ylabel("Trade count")
    axes[0, 0].set_title("Trades taken vs threshold")
    axes[0, 0].grid(alpha=0.3)

    axes[0, 1].plot(df["threshold"], df["win_rate"], marker=".", color="green")
    axes[0, 1].axhline(1 / (1 + risk_reward), ls="--", color="gray",
                       label=f"Breakeven (RR={risk_reward})")
    axes[0, 1].set_xlabel("Threshold")
    axes[0, 1].set_ylabel("Win rate")
    axes[0, 1].set_title("Win rate vs threshold")
    axes[0, 1].legend()
    axes[0, 1].grid(alpha=0.3)

    axes[1, 0].plot(df["threshold"], df["profit_factor"], marker=".", color="purple")
    axes[1, 0].axhline(1.0, ls="--", color="red", label="PF = 1 (breakeven)")
    axes[1, 0].axhline(1.3, ls="--", color="orange", label="PF = 1.3 (target)")
    axes[1, 0].set_xlabel("Threshold")
    axes[1, 0].set_ylabel("Profit factor")
    axes[1, 0].set_title("Profit factor vs threshold")
    axes[1, 0].legend()
    axes[1, 0].grid(alpha=0.3)

    axes[1, 1].plot(df["threshold"], df["expectancy_r"], marker=".", color="navy")
    axes[1, 1].axhline(0, ls="--", color="red")
    axes[1, 1].set_xlabel("Threshold")
    axes[1, 1].set_ylabel("Expectancy (R per trade)")
    axes[1, 1].set_title("Expectancy vs threshold")
    axes[1, 1].grid(alpha=0.3)

    plt.tight_layout()
    return fig, df
