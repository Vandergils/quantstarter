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
    """Like Sharpe, but only penalises downside volatility.

    Downside deviation is the root mean square of the losses over ALL candles (target return 0),
    not the spread among the losing candles only.
    """
    values = returns.to_numpy(dtype=float)
    if len(values) == 0:
        return 0.0
    downside = float(np.sqrt(np.mean(np.minimum(values, 0.0) ** 2)))
    if downside == 0 or np.isnan(downside):
        return 0.0
    return float(returns.mean() / downside * np.sqrt(periods_per_year))


def trade_returns(df: pd.DataFrame) -> list:
    """Net return of every trade: one unbroken stretch long or short, entry AND exit costs included.

    The simulation charges a trade's exit cost on the candle after the trade, and a flip from long to
    short pays for closing one trade and opening the next on the same candle. This splits that cost
    so each trade carries its own entry and exit. A trade still open at the end has no exit cost yet.
    Without the `cost` and `exposure` columns, only the costs inside the stretch are counted.
    """
    pos = df["position"].to_numpy(dtype=float)
    ret = df["strategy_ret"].to_numpy(dtype=float)
    n = len(pos)
    if n == 0:
        return []
    has_costs = "cost" in df.columns and "exposure" in df.columns
    if has_costs:
        cost = df["cost"].to_numpy(dtype=float)
        exposure = df["exposure"].to_numpy(dtype=float)

    def closing_cost(i: int) -> float:
        """Part of candle i's trading cost that closes the position held on candle i-1."""
        if not has_costs or i <= 0 or i >= n or exposure[i - 1] == 0 or cost[i] == 0:
            return 0.0
        moved = abs(exposure[i] - exposure[i - 1])
        return float(cost[i] * abs(exposure[i - 1]) / moved) if moved else 0.0

    changes = np.flatnonzero(np.diff(pos) != 0) + 1
    starts = np.concatenate(([0], changes))
    ends = np.concatenate((changes, [n])) - 1          # inclusive
    trades = []
    for s, e in zip(starts, ends):
        if pos[s] == 0:
            continue
        # the first candle also carries the cost of closing the previous trade; hand that back
        growth = (1 + ret[s] + closing_cost(s)) * np.prod(1 + ret[s + 1:e + 1])
        growth *= 1 - closing_cost(e + 1)
        trades.append(float(growth - 1))
    return trades


def win_rate(df: pd.DataFrame) -> float:
    """Share of trades that made money, after the fees on both entry and exit."""
    trades = trade_returns(df)
    return float(np.mean(np.array(trades) > 0)) if trades else 0.0


def time_in_market(df: pd.DataFrame) -> float:
    """Share of candles spent in a position, long or short (the rest is cash)."""
    return float(df["position"].abs().mean())


def account_wiped(df: pd.DataFrame) -> bool:
    """True if the account lost everything at some point (possible with leverage or shorts)."""
    return bool((df["equity"] <= 1e-9).any())


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