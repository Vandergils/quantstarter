import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "engine"))

from metrics import max_drawdown, position_size, sharpe  # noqa: E402


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
