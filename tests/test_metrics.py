import os
import sys

import numpy as np
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "engine"))

from metrics import max_drawdown, position_size, sharpe, sortino, trade_returns, win_rate  # noqa: E402
from strategies import run_signal  # noqa: E402


def test_max_drawdown_finds_worst_fall():
    equity = pd.Series([1.0, 1.2, 0.9, 1.1])
    # peak 1.2 -> trough 0.9 is a 25% fall
    assert abs(max_drawdown(equity) - (-0.25)) < 1e-9


def test_max_drawdown_is_zero_when_always_rising():
    equity = pd.Series([1.0, 1.1, 1.2, 1.3])
    assert max_drawdown(equity) == 0.0


def test_position_size_matches_risk_budget():
    # risk 1% of 1000 = 10 USD; stop is 2000 away -> 0.005 units
    assert abs(position_size(1000, 0.01, 60000, 58000) - 0.005) < 1e-12


def test_position_size_handles_zero_stop_distance():
    assert position_size(1000, 0.01, 60000, 60000) == 0.0


def test_sharpe_is_zero_when_returns_do_not_vary():
    returns = pd.Series([0.0, 0.0, 0.0, 0.0])
    assert sharpe(returns) == 0.0


# ---------- Sortino ----------

def test_sortino_uses_downside_deviation_over_all_candles():
    r = pd.Series([0.01, -0.02, 0.0, 0.03, -0.01])
    # downside deviation = sqrt(mean([0, 0.0004, 0, 0, 0.0001])) = 0.01; mean return = 0.002
    assert abs(sortino(r, periods_per_year=1) - 0.2) < 1e-12


def test_sortino_is_not_inflated_by_similar_sized_losses():
    rng = np.random.default_rng(0)
    r = pd.Series(np.where(rng.random(2000) < 0.99, 0.0005, -0.005 + rng.normal(0, 0.0001, 2000)))
    reference = r.mean() / np.sqrt(np.mean(np.minimum(r, 0) ** 2)) * np.sqrt(24 * 365)
    assert abs(sortino(r) - reference) < 1e-9 * abs(reference)


def test_sortino_is_zero_without_losses_or_data():
    assert sortino(pd.Series([0.01, 0.02, 0.0])) == 0.0
    assert sortino(pd.Series([], dtype=float)) == 0.0


# ---------- win rate: the exit fee belongs to the trade ----------

def test_win_rate_counts_the_exit_fee():
    # price rises 0.15% while we hold; fee 0.1% on the way in and on the way out
    close = [100, 100, 100.15, 100.15, 100.15, 100.15]
    df = pd.DataFrame({"close": close}, index=pd.date_range("2024-01-01", periods=6, freq="h"))
    signal = pd.Series([0, 1, 1, 0, 0, 0], index=df.index)
    result = run_signal(df, signal, fee=0.001)

    trades = trade_returns(result)
    assert len(trades) == 1
    assert trades[0] < 0                                   # 0.15% gain minus 0.2% of fees
    assert abs(trades[0] - (result["equity"].iloc[-1] - 1)) < 1e-12
    assert win_rate(result) == 0.0


def test_trade_returns_multiply_to_the_equity_curve_for_long_only():
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.normal(0, 1, 400))
    df = pd.DataFrame({"close": close}, index=pd.date_range("2024-01-01", periods=400, freq="h"))
    signal = (df["close"] > df["close"].rolling(10).mean()).astype(int)
    signal.iloc[-3:] = 0                                   # make sure the last trade is closed
    result = run_signal(df, signal, fee=0.002)

    trades = trade_returns(result)
    assert len(trades) >= 5
    assert abs(np.prod(1 + np.array(trades)) - result["equity"].iloc[-1]) < 1e-9


def test_a_flip_splits_its_cost_between_the_two_trades():
    # flat price, 1% fee: long in/out = 2%, short in/out = 2%; the flip pays the middle two halves
    df = pd.DataFrame({"close": [100.0] * 7}, index=pd.date_range("2024-01-01", periods=7, freq="h"))
    signal = pd.Series([0, 1, 1, -1, -1, 0, 0], index=df.index)
    result = run_signal(df, signal, fee=0.01)

    long_trade, short_trade = trade_returns(result)
    assert abs(long_trade - (0.99 * 0.99 - 1)) < 1e-9
    assert abs(short_trade - (0.99 * 0.99 - 1)) < 1e-9


def test_win_rate_still_works_without_the_cost_columns():
    df = pd.DataFrame({"position": [0, 1, 1, 0], "strategy_ret": [0.0, 0.01, 0.01, 0.0]})
    assert win_rate(df) == 1.0
