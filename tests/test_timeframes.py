import math
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "engine"))

from compare import compare_assets, min_candles  # noqa: E402
from costs import cost_stress  # noqa: E402
from metrics import (  # noqa: E402
    HOURS_PER_YEAR, SUPPORTED_TIMEFRAMES, min_segment_candles, periods_per_year, sharpe, sortino,
)
from sensitivity import run_sensitivity  # noqa: E402
from strategies import STRATEGIES  # noqa: E402
from walkforward import fold_windows, min_test_candles, run_walk_forward  # noqa: E402


def make_df(n, freq="D", seed=3):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
    return pd.DataFrame({"close": close}, index=pd.date_range("2020-01-01", periods=n, freq=freq))


def defaults(strategy):
    return {p["name"]: p["default"] for p in STRATEGIES[strategy]["params"]}


def test_candles_per_year_for_each_timeframe():
    assert periods_per_year("1h") == 24 * 365 == HOURS_PER_YEAR
    assert periods_per_year("4h") == 6 * 365
    assert periods_per_year("1d") == 365


def test_unsupported_timeframe_raises_a_clear_error():
    with pytest.raises(ValueError, match="Unsupported timeframe"):
        periods_per_year("3d")


def test_every_supported_timeframe_has_a_minimum():
    for tf in SUPPORTED_TIMEFRAMES:
        assert min_segment_candles(tf) in (100, 200)


def test_sharpe_scales_with_the_square_root_of_candles_per_year():
    rng = np.random.default_rng(1)
    returns = pd.Series(rng.normal(0.001, 0.01, 500))
    hourly = sharpe(returns, periods_per_year("1h"))
    daily = sharpe(returns, periods_per_year("1d"))
    assert math.isclose(hourly / daily, math.sqrt(24), rel_tol=1e-9)
    assert sortino(returns, 365) != sortino(returns, 8760)


def test_slower_timeframes_accept_smaller_windows():
    assert min_test_candles("1h") == 300
    assert min_test_candles("1d") == 60
    # 1,500 candles in 5 folds gives 187-candle test windows
    with pytest.raises(ValueError):
        fold_windows(1500, 5, min_test_candles("1h"))
    test_len, _, windows = fold_windows(1500, 5, min_test_candles("1d"))
    assert test_len == 187 and len(windows) == 5


def test_walk_forward_runs_on_daily_candles():
    out = run_walk_forward(make_df(1500), "sma", fee=0.001, folds=5, timeframe="1d")
    assert out["timeframe"] == "1d"
    assert len(out["fold_results"]) == 5


def test_walk_forward_rejects_the_same_data_as_hourly():
    with pytest.raises(ValueError):
        run_walk_forward(make_df(1500, freq="h"), "sma", fee=0.001, folds=5, timeframe="1h")


def test_walk_forward_sharpe_depends_on_the_timeframe():
    df = make_df(1500)
    daily = run_walk_forward(df, "sma", folds=5, timeframe="1d")["consistency"]["avg_test_sharpe"]
    hourly_scaled = run_walk_forward(df, "sma", folds=5, timeframe="4h")["consistency"]["avg_test_sharpe"]
    # same returns, annualised with a different number of candles per year
    assert daily != hourly_scaled
    assert math.isclose(hourly_scaled / daily, math.sqrt(6), rel_tol=1e-6) or daily == 0


def test_settings_map_accepts_smaller_daily_samples():
    df = make_df(500)
    out = run_sensitivity(df, "sma", "fast", "slow", defaults("sma"), count=5, timeframe="1d")
    assert out["timeframe"] == "1d" and out["cells"]
    with pytest.raises(ValueError):
        run_sensitivity(df, "sma", "fast", "slow", defaults("sma"), count=5, timeframe="1h")


def test_cost_test_accepts_smaller_daily_samples():
    df = make_df(500)
    assert cost_stress(df, "sma", defaults("sma"), timeframe="1d")["timeframe"] == "1d"
    with pytest.raises(ValueError):
        cost_stress(df, "sma", defaults("sma"), timeframe="1h")


def test_asset_comparison_uses_the_timeframe_minimum():
    assert min_candles("1h") == 400 and min_candles("1d") == 200
    data = {"A": make_df(250, seed=1), "B": make_df(250, seed=2)}
    daily = compare_assets(data, "sma", defaults("sma"), timeframe="1d")
    assert [r["asset"] for r in daily["assets"]] == ["A", "B"]
    with pytest.raises(ValueError):
        compare_assets(data, "sma", defaults("sma"), timeframe="1h")