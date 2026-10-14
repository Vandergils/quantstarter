import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "engine"))

from compare import compare_assets  # noqa: E402
from costs import cost_stress  # noqa: E402
from metrics import account_wiped  # noqa: E402
from sensitivity import run_sensitivity  # noqa: E402
from strategies import STRATEGIES, backtest, run_signal  # noqa: E402
from walkforward import run_walk_forward, stats  # noqa: E402


def frame(prices, with_range=False, low=None, high=None):
    df = pd.DataFrame({"close": prices}, index=pd.date_range("2024-01-01", periods=len(prices), freq="h"))
    if with_range:
        df["low"] = low if low is not None else df["close"]
        df["high"] = high if high is not None else df["close"]
    return df


def random_df(n=3000, seed=23, with_range=False):
    rng = np.random.default_rng(seed)
    df = frame(100 * np.exp(np.cumsum(rng.normal(0, 0.006, n))))
    if with_range:
        df["high"] = df["close"] * 1.002
        df["low"] = df["close"] * 0.998
    return df


def defaults(strategy):
    return {p["name"]: p["default"] for p in STRATEGIES[strategy]["params"]}


def always_long(df):
    return pd.Series(1, index=df.index)


# ---------- size scales the exposure ----------

def test_returns_scale_with_the_position_size():
    df = frame([100 * 1.01 ** i for i in range(8)])            # +1% every candle
    for size in (0.5, 1.0, 2.0, 3.0):
        result = run_signal(df, always_long(df), fee=0, size=size)
        assert result["strategy_ret"].iloc[2:].tolist() == pytest.approx([0.01 * size] * 6)


def test_fee_scales_with_the_size_and_trades_are_still_counted_as_orders():
    df = frame([100] * 6)
    signal = pd.Series([0, 1, 1, 0, 0, 0], index=df.index)
    one = run_signal(df, signal, fee=0.01, size=1.0)
    two = run_signal(df, signal, fee=0.01, size=2.0)
    assert one["trade"].sum() == two["trade"].sum() == 2         # one buy, one sell, whatever the size
    assert one["strategy_ret"].sum() == pytest.approx(-0.02)
    assert two["strategy_ret"].sum() == pytest.approx(-0.04)     # twice as much was traded


def test_borrowing_cost_applies_only_above_one_times_and_only_while_in_a_position():
    df = frame([100] * 6)
    signal = pd.Series([1, 1, 1, 0, 0, 0], index=df.index)       # position: 0, 1, 1, 1, 0, 0
    flat = run_signal(df, signal, fee=0, size=1.0, borrow_cost=0.01)
    leveraged = run_signal(df, signal, fee=0, size=3.0, borrow_cost=0.01)
    assert flat["strategy_ret"].sum() == 0                       # nothing borrowed at 1x
    assert leveraged["strategy_ret"].sum() == pytest.approx(-0.01 * 2 * 3)   # 2 borrowed, 3 candles in


def test_short_funding_scales_with_the_size():
    df = frame([100] * 5)
    signal = pd.Series([-1] * 5, index=df.index)
    one = run_signal(df, signal, fee=0, short_cost=0.01, size=1.0)["strategy_ret"].sum()
    two = run_signal(df, signal, fee=0, short_cost=0.01, size=2.0)["strategy_ret"].sum()
    assert two == pytest.approx(2 * one)


# ---------- ruin ----------

def test_leverage_can_wipe_out_the_account_on_a_close_to_close_move():
    df = frame([100, 100, 60, 100, 120])                         # a 40% drop
    signal = pd.Series([1] * 5, index=df.index)
    assert not account_wiped(run_signal(df, signal, fee=0, size=1.0))
    wiped = run_signal(df, signal, fee=0, size=3.0)              # 3 x 40% = 120% of the account
    assert account_wiped(wiped)
    assert wiped["equity"].iloc[-1] == 0                         # and it never comes back


def test_an_intraday_spike_can_wipe_out_a_leveraged_account_even_if_the_close_recovers():
    df = frame([100, 100, 100, 100, 100], with_range=True, low=[100, 100, 60, 100, 100])
    signal = pd.Series([1] * 5, index=df.index)
    assert not account_wiped(run_signal(df, signal, fee=0, size=1.0))
    assert not account_wiped(run_signal(df, signal, fee=0, size=2.0))     # 2 x 40% = 80%, survives
    assert account_wiped(run_signal(df, signal, fee=0, size=3.0))         # 3 x 40% = 120%, liquidated


def test_a_short_is_wiped_out_by_an_intraday_spike_up():
    df = frame([100, 100, 100, 100], with_range=True, high=[100, 100, 210, 100])   # doubles inside the candle
    signal = pd.Series([-1] * 4, index=df.index)
    assert account_wiped(run_signal(df, signal, fee=0, size=1.0))


def test_stats_report_whether_the_account_was_wiped():
    df = frame([100, 100, 60, 100, 120])
    signal = pd.Series([1] * 5, index=df.index)
    assert stats(run_signal(df, signal, fee=0, size=3.0))["account_wiped"] is True
    assert stats(run_signal(df, signal, fee=0, size=1.0))["account_wiped"] is False


# ---------- nothing changes at the default size ----------

def test_size_one_without_borrowing_is_exactly_the_old_behaviour():
    df = random_df(with_range=True)
    for key in STRATEGIES:
        for mode in ("long", "long_short"):
            old = backtest(df, key, defaults(key), 0.001, mode, 0.00001)
            new = backtest(df, key, defaults(key), 0.001, mode, 0.00001, 1.0, 0.0)
            assert old["equity"].equals(new["equity"]), (key, mode)


def test_borrowing_cost_has_no_effect_at_one_times():
    df = random_df()
    a = backtest(df, "sma", defaults("sma"), 0.001, "long", 0.0, 1.0, 0.0)["equity"]
    b = backtest(df, "sma", defaults("sma"), 0.001, "long", 0.0, 1.0, 0.0005)["equity"]
    assert a.equals(b)


def test_leverage_raises_the_drawdown_while_sharpe_stays_close():
    from metrics import max_drawdown, sharpe

    df = random_df(4000)
    one = backtest(df, "sma", defaults("sma"), 0.0, "long", 0.0, 1.0)
    three = backtest(df, "sma", defaults("sma"), 0.0, "long", 0.0, 3.0)
    assert max_drawdown(three["equity"]) < max_drawdown(one["equity"])          # a deeper fall
    assert sharpe(three["strategy_ret"]) == pytest.approx(sharpe(one["strategy_ret"]), rel=0.15)


# ---------- the tools on top accept the new settings ----------

def test_walk_forward_settings_map_cost_test_and_comparison_accept_size_and_borrowing():
    df = random_df(4000)
    wf = run_walk_forward(df, "sma", folds=4, size=2.0, borrow_cost=0.00001)
    assert wf["size"] == 2.0

    sm = run_sensitivity(df, "sma", "fast", "slow", defaults("sma"), count=5, size=2.0, borrow_cost=0.00001)
    assert sm["size"] == 2.0 and sm["cells"]

    ct = cost_stress(df, "breakout", defaults("breakout"), size=2.0, borrow_cost=0.00001)
    assert ct["size"] == 2.0

    cp = compare_assets({"A": random_df(3000, 1), "B": random_df(3000, 2)}, "rsi", defaults("rsi"),
                        size=2.0, borrow_cost=0.00001)
    assert cp["size"] == 2.0 and len(cp["assets"]) == 2


def test_a_bigger_size_changes_the_walk_forward_result():
    df = random_df(4000)
    one = run_walk_forward(df, "sma", folds=4, size=1.0)["stitched"]["metrics"]["total_return"]
    three = run_walk_forward(df, "sma", folds=4, size=3.0)["stitched"]["metrics"]["total_return"]
    assert one != three