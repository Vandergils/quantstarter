import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "engine"))

from sensitivity import axis_values, run_sensitivity  # noqa: E402
from strategies import STRATEGIES  # noqa: E402


def make_df(n=4000):
    rng = np.random.default_rng(21)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.006, n)))
    return pd.DataFrame({"close": close}, index=pd.date_range("2024-01-01", periods=n, freq="h"))


def defaults(strategy):
    return {p["name"]: p["default"] for p in STRATEGIES[strategy]["params"]}


def test_axis_values_cover_the_range_and_are_sorted():
    param = {"name": "fast", "min": 5, "max": 100}
    values = axis_values(param, 9)
    assert values[0] == 5 and values[-1] == 100
    assert values == sorted(set(values))
    assert all(isinstance(v, int) for v in values)


def test_axis_values_include_the_current_setting():
    param = {"name": "fast", "min": 5, "max": 100}
    assert 20 in axis_values(param, 9, include=20)
    assert 500 not in axis_values(param, 9, include=500)  # outside the range: ignored


def test_decimal_settings_stay_decimal():
    param = {"name": "width", "min": 0.5, "max": 3.5, "type": "float"}
    values = axis_values(param, 7)
    assert values[0] == 0.5 and values[-1] == 3.5
    assert all(round(v, 2) == v for v in values)


def test_two_axis_map_skips_invalid_combinations():
    out = run_sensitivity(make_df(), "sma", "fast", "slow", defaults("sma"), holdout=0.3, count=6)
    assert out["cells"]
    for cell in out["cells"]:
        assert cell["x"] < cell["y"]  # fast must stay below slow


def test_every_cell_has_training_and_test_numbers():
    out = run_sensitivity(make_df(), "bollinger", "period", "width", defaults("bollinger"), count=5)
    for cell in out["cells"]:
        for part in ("train", "test"):
            assert set(cell[part]) == {"sharpe", "return", "trades"}


def test_current_setting_is_located_on_the_map():
    fixed = defaults("sma")
    out = run_sensitivity(make_df(), "sma", "fast", "slow", fixed, count=6)
    xi, yi = out["current"]["xi"], out["current"]["yi"]
    assert out["x"]["values"][xi] == fixed["fast"]
    assert out["y"]["values"][yi] == fixed["slow"]


def test_summary_is_consistent_with_the_cells():
    out = run_sensitivity(make_df(), "rsi", "buy_below", "sell_above", defaults("rsi"), count=6)
    s = out["summary"]
    assert 0.0 <= s["share_positive_train"] <= 1.0
    assert 0.0 <= s["share_positive_test"] <= 1.0
    assert s["valid"] == len(out["cells"])
    assert s["best"]["train_sharpe"] == max(c["train"]["sharpe"] for c in out["cells"])


def test_one_setting_strategy_gives_a_single_row():
    out = run_sensitivity(make_df(), "breakout", "lookback", None, defaults("breakout"), count=7)
    assert out["y"]["values"] == [None]
    assert {c["yi"] for c in out["cells"]} == {0}


def test_bad_axes_raise():
    df = make_df()
    with pytest.raises(ValueError):
        run_sensitivity(df, "sma", "fast", "fast", defaults("sma"))
    with pytest.raises(ValueError):
        run_sensitivity(df, "sma", "nonsense", "slow", defaults("sma"))


def test_too_little_data_raises():
    with pytest.raises(ValueError):
        run_sensitivity(make_df(300), "sma", "fast", "slow", defaults("sma"))


def test_buy_and_hold_reference_matches_the_price_move():
    df = make_df()
    out = run_sensitivity(df, "sma", "fast", "slow", defaults("sma"), holdout=0.3, count=5)
    n = len(df)
    cut = int(n * 0.7)
    close = df["close"].to_numpy()
    assert abs(out["hold"]["train"]["return"] - (close[cut - 1] / close[0] - 1)) < 1e-9
    assert abs(out["hold"]["test"]["return"] - (close[n - 1] / close[cut - 1] - 1)) < 1e-9