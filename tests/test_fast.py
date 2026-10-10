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