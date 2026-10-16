import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "engine"))

import fast  # noqa: E402

needs_cpp = pytest.mark.skipif(
    not fast.using_cpp(), reason="C++ library not built (run: python cpp/build.py)"
)


def prices(n=2000):
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    return pd.Series(close, index=pd.date_range("2024-01-01", periods=n, freq="h"))


def same(a, b):
    # NaN must be in the same places, and the numbers must agree
    assert a.isna().equals(b.isna())
    assert np.allclose(a.dropna().to_numpy(), b.dropna().to_numpy(), rtol=1e-9, atol=1e-9)


def test_fallback_functions_always_work():
    s = prices()
    assert len(fast.sma(s, 20)) == len(s)
    assert len(fast.rsi(s, 14)) == len(s)


@needs_cpp
def test_sma_matches_pandas():
    s = prices()
    for window in (5, 20, 50, 200):
        same(fast.sma(s, window), fast.py_sma(s, window))


@needs_cpp
def test_rsi_matches_pandas():
    s = prices()
    for period in (7, 14, 21):
        same(fast.rsi(s, period), fast.py_rsi(s, period))


@needs_cpp
def test_rolling_max_min_match_pandas():
    s = prices()
    for window in (10, 50, 100):
        same(fast.rolling_max(s, window), fast.py_rolling_max(s, window))
        same(fast.rolling_min(s, window), fast.py_rolling_min(s, window))


def with_gaps():
    s = prices(600).copy()
    s.iloc[[0, 1, 100, 101, 102, 350]] = np.nan   # missing at the start, a run, and a lone one
    return s


@needs_cpp
def test_missing_prices_behave_like_pandas():
    s = with_gaps()
    for window in (5, 20, 50):
        same(fast.sma(s, window), fast.py_sma(s, window))
        same(fast.rolling_max(s, window), fast.py_rolling_max(s, window))
        same(fast.rolling_min(s, window), fast.py_rolling_min(s, window))
    for period in (7, 14):
        same(fast.rsi(s, period), fast.py_rsi(s, period))


@needs_cpp
def test_one_missing_price_does_not_wreck_the_rest_of_the_series():
    s = prices(1000).copy()
    s.iloc[500] = np.nan
    assert fast.sma(s, 20).iloc[600:].notna().all()
