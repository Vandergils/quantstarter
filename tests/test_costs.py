import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "engine"))

from costs import COST_LEVELS, break_even, cost_stress  # noqa: E402
from strategies import STRATEGIES  # noqa: E402


def make_df(n=4000, seed=31):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0001, 0.006, n)))
    return pd.DataFrame({"close": close}, index=pd.date_range("2024-01-01", periods=n, freq="h"))


def defaults(strategy):
    return {p["name"]: p["default"] for p in STRATEGIES[strategy]["params"]}


def test_higher_costs_never_increase_the_return():
    out = cost_stress(make_df(), "sma", defaults("sma"))
    for part in ("train", "test"):
        returns = [row[part]["return"] for row in out["rows"]]
        assert all(later <= earlier + 1e-12 for earlier, later in zip(returns, returns[1:]))


def test_trade_count_does_not_depend_on_cost():
    out = cost_stress(make_df(), "rsi", defaults("rsi"))
    trades = {row["test"]["trades"] for row in out["rows"]}
    assert len(trades) == 1


def test_rows_follow_the_cost_levels():
    out = cost_stress(make_df(), "breakout", defaults("breakout"))
    assert [row["cost"] for row in out["rows"]] == COST_LEVELS


def test_break_even_interpolates_between_levels():
    levels = [0.0, 0.001, 0.002, 0.003]
    result = break_even(levels, [0.20, 0.10, -0.10, -0.30])
    assert result["status"] == "crosses"
    assert abs(result["cost"] - 0.0015) < 1e-12   # zero is halfway between 0.10 and -0.10


def test_break_even_when_never_profitable():
    assert break_even([0.0, 0.001], [-0.05, -0.10])["status"] == "not_profitable_at_zero"
    assert break_even([0.0, 0.001], [0.0, -0.10])["status"] == "not_profitable_at_zero"


def test_break_even_when_always_profitable():
    result = break_even([0.0, 0.005, 0.01], [0.50, 0.30, 0.10])
    assert result == {"status": "positive_throughout", "cost": 0.01}


def test_too_little_data_raises():
    with pytest.raises(ValueError):
        cost_stress(make_df(300), "sma", defaults("sma"))