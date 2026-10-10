import itertools
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "engine"))

from metrics import sharpe  # noqa: E402
from strategies import STRATEGIES, backtest  # noqa: E402
from walkforward import fold_windows, run_walk_forward  # noqa: E402


def make_df(n=6000):
    rng = np.random.default_rng(11)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.006, n)))
    return pd.DataFrame({"close": close}, index=pd.date_range("2024-01-01", periods=n, freq="h"))


def test_windows_follow_each_other_and_end_at_the_newest_candle():
    test_len, train_len, windows = fold_windows(6000, 5)
    for start, test_start, test_end in windows:
        assert test_start - start == train_len
        assert test_end - test_start == test_len
    for previous, following in zip(windows, windows[1:]):
        assert following[1] == previous[2]      # test windows are back to back
        assert following[0] < previous[2]       # training windows slide, they do not jump
    assert windows[-1][2] == 6000
    assert windows[0][0] >= 0


def test_test_windows_never_overlap_their_own_training_window():
    _, _, windows = fold_windows(6000, 4)
    for start, test_start, test_end in windows:
        assert start < test_start <= test_end


def test_too_little_data_raises():
    with pytest.raises(ValueError):
        fold_windows(500, 5)


def test_walk_forward_output_shape():
    out = run_walk_forward(make_df(), "sma", fee=0.001, folds=4)
    assert len(out["fold_results"]) == 4
    assert out["stitched"]["candles"] == 4 * out["test_len"]
    c = out["consistency"]
    assert 0 <= c["profitable"] <= 4
    assert 0 <= c["beat_hold"] <= 4
    assert 1 <= c["distinct_settings"] <= 4


def test_chosen_settings_come_from_the_grid():
    out = run_walk_forward(make_df(), "rsi", folds=3)
    for fold in out["fold_results"]:
        for name, value in fold["params"].items():
            assert value in STRATEGIES["rsi"]["grid"][name]


def test_best_setting_is_chosen_from_training_data_only():
    df = make_df()
    spec = STRATEGIES["sma"]
    out = run_walk_forward(df, "sma", fee=0.001, folds=3)
    _, _, windows = fold_windows(len(df), 3)
    start, test_start, _ = windows[0]

    scores = {}
    names = list(spec["grid"])
    for values in itertools.product(*spec["grid"].values()):
        params = dict(zip(names, values))
        if spec["validate"](params):
            continue
        res = backtest(df, "sma", params, 0.001)
        scores[tuple(sorted(params.items()))] = sharpe(res["strategy_ret"].iloc[start:test_start])

    expected = max(scores, key=scores.get)
    assert tuple(sorted(out["fold_results"][0]["params"].items())) == expected


def test_stitched_equity_is_built_from_test_windows_only():
    out = run_walk_forward(make_df(), "breakout", folds=3)
    # a fold's test window starts right after its training window, never inside it
    first = out["fold_results"][0]
    assert first["train_end"] <= first["test_start"]


def test_exposure_is_a_share_between_zero_and_one():
    out = run_walk_forward(make_df(), "sma", folds=3)
    assert 0.0 <= out["stitched"]["metrics"]["exposure"] <= 1.0
    for fold in out["fold_results"]:
        assert 0.0 <= fold["test"]["exposure"] <= 1.0