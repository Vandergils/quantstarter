import numpy as np
import pandas as pd

import fast as fast_indicators  # C++ if built, pandas otherwise


def run_signal(df: pd.DataFrame, signal: pd.Series, fee: float = 0.001, short_cost: float = 0.0) -> pd.DataFrame:
    """Turn a signal into equity curves. Shared by every strategy.

    The signal is +1 (hold the coin), 0 (cash) or -1 (short: profit when the price falls).
    `fee` is charged on every change of position, so flipping from long to short pays it twice.
    `short_cost` is charged on every candle spent short (funding or borrow cost, per candle).
    """
    df = df.copy()
    # shift(1): act on the NEXT candle, so we never trade on information we did not have yet
    df["position"] = signal.shift(1).fillna(0)
    df["market_ret"] = df["close"].pct_change().fillna(0)
    df["trade"] = df["position"].diff().abs().fillna(0)
    df["strategy_ret"] = (
        df["position"] * df["market_ret"] - df["trade"] * fee - (df["position"] < 0) * short_cost
    ).clip(lower=-1.0)  # one candle cannot lose more than the whole account (liquidation is not modelled)
    df["equity"] = (1 + df["strategy_ret"]).cumprod()
    df["buy_hold"] = (1 + df["market_ret"]).cumprod()
    return df


def slice_result(result: pd.DataFrame, start: int, end: int) -> pd.DataFrame:
    """Cut out one period (for example train or test) and restart both curves at 1.0."""
    seg = result.iloc[start:end].copy()
    seg["equity"] = (1 + seg["strategy_ret"]).cumprod()
    seg["buy_hold"] = (1 + seg["market_ret"]).cumprod()
    return seg


def _hold_until_changed(df: pd.DataFrame, enter: pd.Series, leave: pd.Series) -> pd.Series:
    """Enter on one condition, leave on another, keep the last decision in between."""
    signal = pd.Series(np.nan, index=df.index)
    signal.loc[enter] = 1
    signal.loc[leave] = 0
    return signal.ffill().fillna(0)


# ---------- strategies: each returns a 0/1 signal ----------

def sig_sma(df, fast=20, slow=50):
    """Hold while the fast average is above the slow average."""
    f = fast_indicators.sma(df["close"], fast)
    s = fast_indicators.sma(df["close"], slow)
    return (f > s).astype(int)


def sig_rsi(df, period=14, buy_below=30, sell_above=55):
    """Buy when RSI says 'oversold', sell when it has recovered."""
    rsi = fast_indicators.rsi(df["close"], period)
    return _hold_until_changed(df, rsi < buy_below, rsi > sell_above)


def sig_breakout(df, lookback=100):
    """Buy a new high over the last N candles, sell a new low over the last N/2."""
    high = fast_indicators.rolling_max(df["close"], lookback).shift(1)
    low = fast_indicators.rolling_min(df["close"], max(lookback // 2, 2)).shift(1)
    return _hold_until_changed(df, df["close"] > high, df["close"] < low)


def sig_bollinger(df, period=20, width=2.0):
    """Buy when price drops below the lower band, sell when it climbs back to the middle band.

    Middle band = average of the last `period` closes.
    Lower band  = middle band minus `width` standard deviations.
    """
    mid = fast_indicators.sma(df["close"], period)
    std = df["close"].rolling(period).std()
    lower = mid - width * std
    return _hold_until_changed(df, df["close"] < lower, df["close"] > mid)


# ---------- short side: 1 means "be short", 0 means "not short" ----------

def short_sma(df, fast=20, slow=50):
    """Short while the fast average is below the slow average."""
    f = fast_indicators.sma(df["close"], fast)
    s = fast_indicators.sma(df["close"], slow)
    return (f < s).astype(int)


def short_rsi(df, period=14, buy_below=30, sell_above=55):
    """Mirror image of the long side: short an overbought spike, cover once it has cooled off."""
    rsi = fast_indicators.rsi(df["close"], period)
    return _hold_until_changed(df, rsi > 100 - buy_below, rsi < 100 - sell_above)


def short_breakout(df, lookback=100):
    """Short a new N-candle low, cover on a new high over half that period."""
    low = fast_indicators.rolling_min(df["close"], lookback).shift(1)
    high = fast_indicators.rolling_max(df["close"], max(lookback // 2, 2)).shift(1)
    return _hold_until_changed(df, df["close"] < low, df["close"] > high)


def short_bollinger(df, period=20, width=2.0):
    """Short a spike above the upper band, cover when it returns to the middle band."""
    mid = fast_indicators.sma(df["close"], period)
    std = df["close"].rolling(period).std()
    upper = mid + width * std
    return _hold_until_changed(df, df["close"] > upper, df["close"] < mid)


MODES = ("long", "long_short")


def build_signal(df, strategy: str, params: dict, mode: str = "long") -> pd.Series:
    """+1 / 0 for long only. In long_short mode the short side is subtracted, giving +1 / 0 / -1."""
    if mode not in MODES:
        raise ValueError(f"Unknown mode '{mode}'. Use one of: {', '.join(MODES)}.")
    spec = STRATEGIES[strategy]
    long_signal = spec["func"](df, **params)
    if mode == "long":
        return long_signal
    if "short_func" not in spec:
        raise ValueError(f"The '{strategy}' strategy has no short side, so it cannot run in long and short mode.")
    return long_signal - spec["short_func"](df, **params)


def backtest(df, strategy: str, params: dict, fee: float = 0.001, mode: str = "long",
             short_cost: float = 0.0) -> pd.DataFrame:
    return run_signal(df, build_signal(df, strategy, params, mode), fee, short_cost)


# ---------- registry (drives the API and the dashboard) ----------

STRATEGIES = {
    "sma": {
        "label": "Moving average crossover",
        "description": "Trend following. Buy when the fast average rises above the slow average, sell when it falls below.",
        "func": sig_sma,
        "short_func": short_sma,
        "params": [
            {"name": "fast", "label": "Fast average (candles)", "min": 5, "max": 100, "step": 1, "default": 20,
             "hint": "Reacts quickly to price changes."},
            {"name": "slow", "label": "Slow average (candles)", "min": 20, "max": 400, "step": 1, "default": 50,
             "hint": "Shows the longer trend. Must be larger than fast."},
        ],
        "grid": {"fast": [5, 10, 20, 30, 50], "slow": [50, 100, 150, 200, 300]},
        "validate": lambda p: "Fast average must be smaller than slow average." if p["fast"] >= p["slow"] else None,
    },
    "rsi": {
        "label": "RSI mean reversion",
        "description": "Bet on bounces. Buy after a sharp drop (low RSI), sell once the price has recovered.",
        "func": sig_rsi,
        "short_func": short_rsi,
        "params": [
            {"name": "period", "label": "RSI period (candles)", "min": 5, "max": 30, "step": 1, "default": 14,
             "hint": "How many candles RSI looks back."},
            {"name": "buy_below", "label": "Buy when RSI is below", "min": 10, "max": 45, "step": 1, "default": 30,
             "hint": "Lower means waiting for a deeper drop."},
            {"name": "sell_above", "label": "Sell when RSI is above", "min": 50, "max": 90, "step": 1, "default": 55,
             "hint": "Higher means holding for a bigger recovery."},
        ],
        "grid": {"period": [7, 14, 21], "buy_below": [20, 25, 30, 35], "sell_above": [50, 55, 60, 70]},
        "validate": lambda p: "Buy level must be below the sell level." if p["buy_below"] >= p["sell_above"] else None,
    },
    "breakout": {
        "label": "Breakout",
        "description": "Momentum. Buy when price makes a new high over the last N candles, sell on a new low over half that.",
        "func": sig_breakout,
        "short_func": short_breakout,
        "params": [
            {"name": "lookback", "label": "Lookback (candles)", "min": 20, "max": 400, "step": 1, "default": 100,
             "hint": "Longer means fewer but slower signals."},
        ],
        "grid": {"lookback": [24, 48, 100, 200, 300]},
        "validate": lambda p: None,
    },
    "bollinger": {
        "label": "Bollinger Bands",
        "description": "Bet on bounces inside a normal range. Buy when price falls below the lower band, sell when it climbs back to the average.",
        "func": sig_bollinger,
        "short_func": short_bollinger,
        "params": [
            {"name": "period", "label": "Average period (candles)", "min": 10, "max": 100, "step": 1, "default": 20,
             "hint": "How many candles the average and the bands look back."},
            {"name": "width", "label": "Band width (standard deviations)", "type": "float",
             "min": 0.5, "max": 3.5, "step": 0.1, "default": 2.0,
             "hint": "Wider bands wait for bigger drops, so there are fewer trades."},
        ],
        "grid": {"period": [10, 20, 30, 50], "width": [1.5, 2.0, 2.5, 3.0]},
        "validate": lambda p: None,
    },
}