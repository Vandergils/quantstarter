import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "engine"))

from compare import MIN_CANDLES, compare_assets  # noqa: E402
from strategies import STRATEGIES  # noqa: E402


def make_df(seed, n=3000, start="2024-01-01"):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.006, n)))
    return pd.DataFrame({"close": close}, index=pd.date_range(start, periods=n, freq="h"))


def defaults(strategy):
    return {p["name"]: p["default"] for p in STRATEGIES[strategy]["params"]}


def test_every_asset_gets_a_row_with_train_and_test():
    data = {"BTC/USD": make_df(1), "ETH/USD": make_df(2), "SOL/USD": make_df(3)}
    out = compare_assets(data, "sma", defaults("sma"))
    assert [r["asset"] for r in out["assets"]] == ["BTC/USD", "ETH/USD", "SOL/USD"]
    for row in out["assets"]:
        assert "total_return" in row["train"] and "total_return" in row["test"]
        assert 0.0 <= row["test"]["exposure"] <= 1.0


def test_summary_counts_are_consistent():
    data = {"A": make_df(4), "B": make_df(5), "C": make_df(6), "D": make_df(7)}
    s = compare_assets(data, "breakout", defaults("breakout"))["summary"]
    assert s["assets"] == 4
    for key in ("profitable", "beat_hold", "positive_sharpe"):
        assert 0 <= s[key] <= 4


def test_assets_with_too_little_data_are_skipped_not_fatal():
    data = {"BTC/USD": make_df(1), "NEW/USD": make_df(2, n=MIN_CANDLES - 1)}
    out = compare_assets(data, "sma", defaults("sma"))
    assert [r["asset"] for r in out["assets"]] == ["BTC/USD"]
    assert out["skipped"][0]["asset"] == "NEW/USD"


def test_nothing_to_compare_raises():
    with pytest.raises(ValueError):
        compare_assets({"NEW/USD": make_df(2, n=100)}, "sma", defaults("sma"))


def test_same_settings_are_used_for_every_asset():
    data = {"A": make_df(8), "B": make_df(9)}
    out = compare_assets(data, "sma", {"fast": 10, "slow": 40})
    assert out["params"] == {"fast": 10, "slow": 40}


def test_assets_are_compared_over_the_same_dates():
    data = {"A": make_df(1), "B": make_df(2, start="2024-02-01")}   # B has no data before February
    out = compare_assets(data, "sma", defaults("sma"))
    assert out["common_window"] is True
    assert len({r["start"] for r in out["assets"]}) == 1 and len({r["end"] for r in out["assets"]}) == 1
    assert out["window"]["start"] == "2024-02-01"


def test_common_window_can_be_turned_off():
    data = {"A": make_df(1), "B": make_df(2, start="2024-02-01")}
    out = compare_assets(data, "sma", defaults("sma"), common_window=False)
    assert out["common_window"] is False
    assert {r["start"] for r in out["assets"]} == {"2024-01-01", "2024-02-01"}


def test_assets_that_never_overlap_cannot_be_compared():
    data = {"A": make_df(1, n=500), "B": make_df(2, n=500, start="2025-01-01")}
    with pytest.raises(ValueError):
        compare_assets(data, "sma", defaults("sma"))


def test_average_correlation_is_reported():
    same_series = compare_assets({"A": make_df(1), "B": make_df(1)}, "sma", defaults("sma"))
    assert same_series["summary"]["avg_correlation"] == pytest.approx(1.0)
    independent = compare_assets({"A": make_df(1), "B": make_df(2)}, "sma", defaults("sma"))
    assert abs(independent["summary"]["avg_correlation"]) < 0.2
    single = compare_assets({"A": make_df(1)}, "sma", defaults("sma"))
    assert single["summary"]["avg_correlation"] is None
