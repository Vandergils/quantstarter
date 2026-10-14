import itertools
import math

import pandas as pd

from metrics import HOURS_PER_YEAR, account_wiped, periods_per_year, sharpe, summary, time_in_market, time_short
from strategies import STRATEGIES, backtest, slice_result

TRAIN_MULTIPLE = 3      # each training window is 3x as long as its test window
MIN_TEST_CANDLES = 300  # about 12 days of hourly candles


def min_test_candles(timeframe: str) -> int:
    """300 candles for hourly or faster data, 60 for slower data such as daily candles."""
    return MIN_TEST_CANDLES if periods_per_year(timeframe) >= HOURS_PER_YEAR else 60


def fold_windows(n: int, folds: int, min_test: int = MIN_TEST_CANDLES):
    """Return (test_len, train_len, [(train_start, test_start, test_end), ...]).

    The windows end at the newest candle; a few of the oldest candles may be skipped
    when n does not divide evenly.
    """
    test_len = n // (TRAIN_MULTIPLE + folds)
    if test_len < min_test:
        raise ValueError(
            f"Not enough data for {folds} folds: each test window would have only {test_len} candles "
            f"(minimum {min_test}). Try fewer folds or collect more data."
        )
    train_len = TRAIN_MULTIPLE * test_len
    offset = n - (train_len + folds * test_len)
    windows = []
    for k in range(folds):
        start = offset + k * test_len
        windows.append((start, start + train_len, start + train_len + test_len))
    return test_len, train_len, windows


def stats(seg: pd.DataFrame, ppy: int = HOURS_PER_YEAR) -> dict:
    s = summary(seg, ppy)
    s["trades"] = int(seg["trade"].sum())
    s["exposure"] = time_in_market(seg)  # share of candles in a position, long or short
    s["short_time"] = time_short(seg)    # share of candles spent short
    s["account_wiped"] = account_wiped(seg)
    return {k: (v if math.isfinite(v) else 0.0) for k, v in s.items()}


def run_walk_forward(data: pd.DataFrame, strategy: str, fee: float = 0.001, folds: int = 5,
                     timeframe: str = "1h", mode: str = "long", short_cost: float = 0.0,
                     size: float = 1.0, borrow_cost: float = 0.0) -> dict:
    spec = STRATEGIES[strategy]
    ppy = periods_per_year(timeframe)
    test_len, train_len, windows = fold_windows(len(data), folds, min_test_candles(timeframe))

    # Run every setting once over all the data. Signals only look backwards,
    # so slicing the finished result afterwards does not leak the future.
    names = list(spec["grid"])
    combos, results = [], []
    for values in itertools.product(*spec["grid"].values()):
        params = dict(zip(names, values))
        if spec["validate"](params):
            continue
        combos.append(params)
        results.append(backtest(data, strategy, params, fee, mode, short_cost, size, borrow_cost))
    if not combos:
        raise ValueError("No valid settings to test.")

    fold_rows, pieces = [], []
    for k, (a, b, c) in enumerate(windows):
        # choose the setting using the TRAINING window only
        best_i, best_sharpe = 0, -math.inf
        for i, res in enumerate(results):
            sh = sharpe(res["strategy_ret"].iloc[a:b], ppy)
            if sh > best_sharpe:
                best_i, best_sharpe = i, sh
        res = results[best_i]
        fold_rows.append(
            {
                "fold": k + 1,
                "train_start": data.index[a].isoformat()[:10],
                "train_end": data.index[b - 1].isoformat()[:10],
                "test_start": data.index[b].isoformat()[:10],
                "test_end": data.index[c - 1].isoformat()[:10],
                "test_start_time": data.index[b].isoformat(),
                "params": combos[best_i],
                "train": stats(slice_result(res, a, b), ppy),
                "test": stats(slice_result(res, b, c), ppy),
            }
        )
        pieces.append(res.iloc[b:c][["position", "market_ret", "strategy_ret", "trade"]])

    # stitch the unseen windows into one out-of-sample curve
    stitched = pd.concat(pieces)
    stitched["equity"] = (1 + stitched["strategy_ret"]).cumprod()
    stitched["buy_hold"] = (1 + stitched["market_ret"]).cumprod()

    step = max(1, len(stitched) // 500)
    chart = stitched.iloc[::step]

    tests = [f["test"] for f in fold_rows]
    return {
        "strategy": strategy,
        "timeframe": timeframe,
        "mode": mode,
        "size": size,
        "fee": fee,
        "folds": folds,
        "train_len": train_len,
        "test_len": test_len,
        "fold_results": fold_rows,
        "stitched": {
            "candles": len(stitched),
            "metrics": stats(stitched, ppy),
            "chart": {
                "time": [t.isoformat() for t in chart.index],
                "equity": chart["equity"].round(4).tolist(),
                "buy_hold": chart["buy_hold"].round(4).tolist(),
                "fold_starts": [f["test_start_time"] for f in fold_rows],
            },
        },
        "consistency": {
            "folds": folds,
            "profitable": sum(t["total_return"] > 0 for t in tests),
            "beat_hold": sum(t["total_return"] > t["buy_hold_return"] for t in tests),
            "avg_test_sharpe": sum(t["sharpe"] for t in tests) / folds,
            "distinct_settings": len({tuple(sorted(f["params"].items())) for f in fold_rows}),
            "settings_tested": len(combos),
        },
    }