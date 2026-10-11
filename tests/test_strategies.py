import os
import sys

import numpy as np
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "engine"))

from strategies import STRATEGIES, run_signal, slice_result  # noqa: E402


def small_df():
    close = [100, 101, 103, 102, 105, 107]
    index = pd.date_range("2024-01-01", periods=6, freq="h")
    return pd.DataFrame({"close": close}, index=index)


def random_df(n=600):
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    index = pd.date_range("2024-01-01", periods=n, freq="h")
    return pd.DataFrame({"close": close}, index=index)


def test_signal_is_delayed_by_one_candle():
    df = small_df()
    signal = pd.Series([0, 1, 1, 0, 0, 0], index=df.index)
    result = run_signal(df, signal, fee=0)
    # the position must lag the signal by one candle (no look-ahead)
    assert result["position"].tolist() == [0, 0, 1, 1, 0, 0]


def test_trades_are_counted_and_fees_applied():
    df = small_df()
    signal = pd.Series([0, 1, 1, 0, 0, 0], index=df.index)
    free = run_signal(df, signal, fee=0)
    paid = run_signal(df, signal, fee=0.01)
    assert paid["trade"].sum() == 2          # one buy, one sell
    assert paid["equity"].iloc[-1] < free["equity"].iloc[-1]


def test_slice_result_restarts_curves_at_one():
    df = random_df()
    signal = pd.Series(1, index=df.index)
    result = run_signal(df, signal)
    seg = slice_result(result, 300, 600)
    first_ret = seg["strategy_ret"].iloc[0]
    assert abs(seg["equity"].iloc[0] - (1 + first_ret)) < 1e-12


def test_every_strategy_returns_a_zero_one_signal():
    df = random_df()
    for spec in STRATEGIES.values():
        params = {p["name"]: p["default"] for p in spec["params"]}
        signal = spec["func"](df, **params)
        assert set(signal.dropna().unique()) <= {0, 1}
        assert len(signal) == len(df)


def test_default_settings_pass_their_own_validation():
    for spec in STRATEGIES.values():
        params = {p["name"]: p["default"] for p in spec["params"]}
        assert spec["validate"](params) is None


def test_grid_covers_every_parameter():
    for spec in STRATEGIES.values():
        assert set(spec["grid"]) == {p["name"] for p in spec["params"]}


def test_bollinger_buys_a_sharp_drop_and_sells_the_recovery():
    from strategies import sig_bollinger

    close = [100.0] * 40 + [80.0] * 3 + [100.0] * 5
    df = pd.DataFrame({"close": close}, index=pd.date_range("2024-01-01", periods=len(close), freq="h"))
    signal = sig_bollinger(df, period=20, width=2.0)
    assert signal.iloc[39] == 0            # flat market: no trade
    assert signal.iloc[40] == 1            # the drop falls below the lower band: buy
    assert signal.iloc[-1] == 0            # back at the average: sold


def test_decimal_settings_are_declared_with_a_type():
    for spec in STRATEGIES.values():
        for p in spec["params"]:
            if isinstance(p["default"], float):
                assert p.get("type") == "float"