import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "engine"))

from compare import compare_assets  # noqa: E402
from costs import cost_stress  # noqa: E402
from metrics import time_in_market, time_short, win_rate  # noqa: E402
from sensitivity import run_sensitivity  # noqa: E402
from strategies import STRATEGIES, backtest, build_signal, run_signal  # noqa: E402
from walkforward import run_walk_forward, stats  # noqa: E402


def frame(prices):
    return pd.DataFrame({"close": prices}, index=pd.date_range("2024-01-01", periods=len(prices), freq="h"))


def random_df(n=3000, seed=17):
    rng = np.random.default_rng(seed)
    return frame(100 * np.exp(np.cumsum(rng.normal(0, 0.006, n))))


def defaults(strategy):
    return {p["name"]: p["default"] for p in STRATEGIES[strategy]["params"]}


# ---------- the simulation ----------

def test_a_short_profits_when_the_price_falls():
    df = frame([100, 100, 90, 81, 81])
    signal = pd.Series([0, -1, -1, 0, 0], index=df.index)
    result = run_signal(df, signal, fee=0)
    assert result["position"].tolist() == [0, 0, -1, -1, 0]   # delayed by one candle
    assert result["equity"].iloc[-1] > 1.19                   # about +10% then +10% from the two falls


def test_a_short_loses_when_the_price_rises():
    df = frame([100, 100, 110, 121, 121])
    signal = pd.Series([0, -1, -1, 0, 0], index=df.index)
    # two rises of 10% while short: 0.9 * 0.9
    assert run_signal(df, signal, fee=0)["equity"].iloc[-1] == pytest.approx(0.81)


def test_flipping_from_long_to_short_pays_the_fee_twice():
    df = frame([100] * 6)
    signal = pd.Series([0, 1, 1, -1, -1, 0], index=df.index)
    result = run_signal(df, signal, fee=0.01)
    # the position lags the signal: [0, 0, 1, 1, -1, -1], so 0 -> 1 costs one trade and 1 -> -1 costs two
    assert result["position"].tolist() == [0, 0, 1, 1, -1, -1]
    assert result["trade"].sum() == 3
    assert abs(result["strategy_ret"].sum() - (-0.03)) < 1e-12


def test_funding_is_charged_only_while_short():
    df = frame([100] * 6)
    long_run = run_signal(df, pd.Series([1] * 6, index=df.index), fee=0, short_cost=0.01)
    short_run = run_signal(df, pd.Series([-1] * 6, index=df.index), fee=0, short_cost=0.01)
    assert long_run["equity"].iloc[-1] == 1.0
    assert short_run["equity"].iloc[-1] < 1.0
    # shifted by one candle, so the short is held on 5 of the 6 candles
    assert abs(short_run["strategy_ret"].sum() - (-0.05)) < 1e-12


def test_one_candle_cannot_lose_more_than_the_whole_account():
    df = frame([100, 100, 500, 500])          # the price quintuples while we are short
    signal = pd.Series([-1, -1, -1, -1], index=df.index)
    result = run_signal(df, signal, fee=0)
    assert result["strategy_ret"].min() >= -1.0
    assert result["equity"].min() >= 0.0


# ---------- metrics ----------

def test_win_rate_counts_short_trades():
    df = frame([100, 100, 90, 80, 80, 90, 100])
    signal = pd.Series([0, -1, -1, 0, 1, 1, 0], index=df.index)
    result = run_signal(df, signal, fee=0)
    # short trade: price fell (win). long trade after it: price rose (win)
    assert win_rate(result) == 1.0


def test_win_rate_for_long_only_is_unchanged():
    df = frame([100, 110, 121, 121, 100, 90])
    signal = pd.Series([1, 1, 0, 1, 1, 1], index=df.index)
    result = run_signal(df, signal, fee=0)
    assert result["position"].tolist() == [0, 1, 1, 0, 1, 1]
    # first trade gains 21%, second loses (121 -> 100 -> 90) -> half of the trades won
    assert win_rate(result) == 0.5


def test_time_in_market_and_time_short():
    df = frame([100] * 8)
    signal = pd.Series([0, 1, 1, -1, -1, 0, 0, 0], index=df.index)
    result = run_signal(df, signal, fee=0)
    assert time_in_market(result) == pytest.approx(4 / 8)
    assert time_short(result) == pytest.approx(2 / 8)
    s = stats(result)
    assert s["exposure"] == pytest.approx(4 / 8) and s["short_time"] == pytest.approx(2 / 8)


# ---------- the strategies ----------

def test_long_mode_is_exactly_what_it_was_before():
    df = random_df()
    for key, spec in STRATEGIES.items():
        params = defaults(key)
        old = run_signal(df, spec["func"](df, **params), 0.001)
        new = backtest(df, key, params, 0.001, "long")
        assert old["equity"].equals(new["equity"])


def test_every_builtin_strategy_has_a_short_side():
    for key, spec in STRATEGIES.items():
        assert "short_func" in spec, key


def test_long_short_signals_stay_within_minus_one_zero_one():
    df = random_df()
    for key in STRATEGIES:
        signal = build_signal(df, key, defaults(key), "long_short")
        assert set(signal.dropna().unique()) <= {-1, 0, 1}, key


def test_the_moving_average_is_flat_while_the_averages_warm_up():
    df = random_df()
    params = {"fast": 20, "slow": 50}
    signal = build_signal(df, "sma", params, "long_short")
    assert (signal.iloc[:49] == 0).all()        # no short before the slow average exists


def test_long_short_mode_actually_goes_short():
    df = random_df()
    for key in STRATEGIES:
        result = backtest(df, key, defaults(key), 0.001, "long_short")
        assert time_short(result) > 0, key


def test_unknown_mode_and_missing_short_side_are_clear_errors():
    df = random_df()
    with pytest.raises(ValueError, match="Unknown mode"):
        build_signal(df, "sma", defaults("sma"), "short_only")
    STRATEGIES["no_short"] = {**STRATEGIES["sma"]}
    del STRATEGIES["no_short"]["short_func"]
    try:
        with pytest.raises(ValueError, match="no short side"):
            build_signal(df, "no_short", defaults("sma"), "long_short")
    finally:
        del STRATEGIES["no_short"]


# ---------- the tools that sit on top ----------

def test_walk_forward_settings_map_cost_test_and_comparison_accept_long_short():
    df = random_df(4000)
    wf = run_walk_forward(df, "sma", fee=0.001, folds=4, mode="long_short", short_cost=0.00001)
    assert wf["mode"] == "long_short" and wf["stitched"]["metrics"]["short_time"] > 0

    sm = run_sensitivity(df, "sma", "fast", "slow", defaults("sma"), count=5, mode="long_short")
    assert sm["mode"] == "long_short" and sm["cells"]

    ct = cost_stress(df, "breakout", defaults("breakout"), mode="long_short")
    assert ct["mode"] == "long_short"

    cp = compare_assets({"A": random_df(3000, 1), "B": random_df(3000, 2)}, "rsi", defaults("rsi"), mode="long_short")
    assert cp["mode"] == "long_short" and len(cp["assets"]) == 2


def test_the_two_modes_give_different_results():
    df = random_df(4000)
    long_only = run_walk_forward(df, "sma", folds=4, mode="long")["stitched"]["metrics"]["total_return"]
    both = run_walk_forward(df, "sma", folds=4, mode="long_short")["stitched"]["metrics"]["total_return"]
    assert long_only != both


def test_higher_funding_lowers_the_result():
    df = random_df(4000)
    free = backtest(df, "sma", defaults("sma"), 0.001, "long_short", 0.0)["equity"].iloc[-1]
    costly = backtest(df, "sma", defaults("sma"), 0.001, "long_short", 0.0005)["equity"].iloc[-1]
    assert costly < free