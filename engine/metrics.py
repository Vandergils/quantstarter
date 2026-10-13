import numpy as np
import pandas as pd

# candles per year, for crypto that trades 24/7
PERIODS_PER_YEAR = {
    "15m": 4 * 24 * 365,
    "30m": 2 * 24 * 365,
    "1h": 24 * 365,
    "2h": 12 * 365,
    "4h": 6 * 365,
    "1d": 365,
}
SUPPORTED_TIMEFRAMES = list(PERIODS_PER_YEAR)
HOURS_PER_YEAR = PERIODS_PER_YEAR["1h"]  # default, and kept for older code


def periods_per_year(timeframe: str) -> int:
    try:
        return PERIODS_PER_YEAR[timeframe]
    except KeyError:
        raise ValueError(
            f"Unsupported timeframe '{timeframe}'. Use one of: {', '.join(SUPPORTED_TIMEFRAMES)}."
        )


def min_segment_candles(timeframe: str) -> int:
    """Smallest training or test part we accept: 200 candles for hourly or faster data, 100 for slower."""
    return 200 if periods_per_year(timeframe) >= HOURS_PER_YEAR else 100


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
    """Share of trades that made money. A trade is one unbroken stretch long or short."""
    position = df["position"]
    stretch = (position != position.shift()).cumsum()   # a new number whenever the position changes
    active = df[position != 0]
    per_trade = active.groupby(stretch[active.index])["strategy_ret"].apply(
        lambda r: (1 + r).prod() - 1
    )
    return float((per_trade > 0).mean()) if len(per_trade) else 0.0


def time_in_market(df: pd.DataFrame) -> float:
    """Share of candles spent in a position, long or short (the rest is cash)."""
    return float(df["position"].abs().mean())


def time_short(df: pd.DataFrame) -> float:
    """Share of candles spent short."""
    return float((df["position"] < 0).mean())


def summary(df: pd.DataFrame, periods_per_year=HOURS_PER_YEAR) -> dict:
    return {
        "total_return": float(df["equity"].iloc[-1] - 1),
        "buy_hold_return": float(df["buy_hold"].iloc[-1] - 1),
        "max_drawdown": max_drawdown(df["equity"]),
        "buy_hold_max_drawdown": max_drawdown(df["buy_hold"]),
        "sharpe": sharpe(df["strategy_ret"], periods_per_year),
        "sortino": sortino(df["strategy_ret"], periods_per_year),
        "win_rate": win_rate(df),
    }


def position_size(balance: float, risk_pct: float, entry: float, stop: float) -> float:
    """Units to buy so that hitting the stop loses only risk_pct of the balance."""
    risk_amount = balance * risk_pct
    per_unit_loss = abs(entry - stop)
    return risk_amount / per_unit_loss if per_unit_loss else 0.0