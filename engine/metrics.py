import numpy as np
import pandas as pd

HOURS_PER_YEAR = 24 * 365  # use 365 for daily candles


def max_drawdown(equity: pd.Series) -> float:
    """Worst peak-to-trough fall, as a negative fraction (-0.25 = -25%)."""
    peak = equity.cummax()
    return float((equity / peak - 1).min())


def sharpe(returns: pd.Series, periods_per_year=HOURS_PER_YEAR) -> float:
    """Annualised return per unit of total volatility (risk-free rate = 0)."""
    std = returns.std()
    if std == 0 or np.isnan(std):
        return 0.0
    return float(returns.mean() / std * np.sqrt(periods_per_year))


def sortino(returns: pd.Series, periods_per_year=HOURS_PER_YEAR) -> float:
    """Like Sharpe, but only penalises downside volatility."""
    downside = returns[returns < 0].std()
    if downside == 0 or np.isnan(downside):
        return 0.0
    return float(returns.mean() / downside * np.sqrt(periods_per_year))


def win_rate(df: pd.DataFrame) -> float:
    """Share of completed trades that made money."""
    trade_id = (df["position"].diff().fillna(0) > 0).cumsum()
    in_trade = df[df["position"] == 1].copy()
    in_trade["trade_id"] = trade_id[in_trade.index]
    per_trade = in_trade.groupby("trade_id")["strategy_ret"].apply(
        lambda r: (1 + r).prod() - 1
    )
    return float((per_trade > 0).mean()) if len(per_trade) else 0.0


def summary(df: pd.DataFrame) -> dict:
    return {
        "total_return": float(df["equity"].iloc[-1] - 1),
        "buy_hold_return": float(df["buy_hold"].iloc[-1] - 1),
        "max_drawdown": max_drawdown(df["equity"]),
        "buy_hold_max_drawdown": max_drawdown(df["buy_hold"]),
        "sharpe": sharpe(df["strategy_ret"]),
        "sortino": sortino(df["strategy_ret"]),
        "win_rate": win_rate(df),
    }


def position_size(balance: float, risk_pct: float, entry: float, stop: float) -> float:
    """Units to buy so that hitting the stop loses only risk_pct of the balance."""
    risk_amount = balance * risk_pct
    per_unit_loss = abs(entry - stop)
    return risk_amount / per_unit_loss if per_unit_loss else 0.0