import numpy as np
import pandas as pd

from metrics import HOURS_PER_YEAR, periods_per_year
from strategies import backtest, slice_result
from walkforward import stats

MIN_CANDLES = 400  # hourly default


def min_candles(timeframe: str) -> int:
    """400 candles for hourly or faster data, 200 for slower data such as daily candles."""
    return MIN_CANDLES if periods_per_year(timeframe) >= HOURS_PER_YEAR else 200


def average_correlation(datasets: dict):
    """Average correlation of candle-to-candle returns between every pair of assets (None if fewer than 2)."""
    if len(datasets) < 2:
        return None
    returns = pd.DataFrame({label: d["close"].pct_change() for label, d in datasets.items()}).dropna()
    if len(returns) < 3:
        return None
    corr = returns.corr().to_numpy()
    value = float(np.mean(corr[np.triu_indices_from(corr, k=1)]))
    return value if np.isfinite(value) else None


def compare_assets(datasets: dict, strategy: str, params: dict, fee: float = 0.001, holdout: float = 0.3,
                   timeframe: str = "1h", mode: str = "long", short_cost: float = 0.0,
                   size: float = 1.0, borrow_cost: float = 0.0, common_window: bool = True) -> dict:
    """`datasets` maps a label (such as "ETH/USD") to a price table with a `close` column.

    With `common_window` (the default) every asset is cut to the dates they all have, so the training and
    unseen parts cover the same period for every asset. Without it each asset uses its own full history,
    which means the "unseen" dates differ from one asset to the next.
    """
    ppy = periods_per_year(timeframe)
    minimum = min_candles(timeframe)
    skipped = []
    usable = {}
    for label, data in datasets.items():
        if len(data) < minimum:
            skipped.append({"asset": label, "reason": f"only {len(data)} candles"})
        else:
            usable[label] = data

    shared = bool(common_window) and len(usable) > 1
    if shared:
        start = max(d.index[0] for d in usable.values())
        end = min(d.index[-1] for d in usable.values())
        trimmed = {}
        for label, data in usable.items():
            part = data.loc[start:end]
            if len(part) < minimum:
                skipped.append({"asset": label, "reason": f"only {len(part)} candles in the period all assets share"})
            else:
                trimmed[label] = part
        usable = trimmed

    if not usable:
        raise ValueError("None of the assets has enough data to compare.")

    rows = []
    for label, data in usable.items():
        n = len(data)
        cut = int(n * (1 - holdout))
        result = backtest(data, strategy, params, fee, mode, short_cost, size, borrow_cost)
        rows.append(
            {
                "asset": label,
                "candles": n,
                "start": data.index[0].isoformat()[:10],
                "end": data.index[-1].isoformat()[:10],
                "train": stats(slice_result(result, 0, cut), ppy),
                "test": stats(slice_result(result, cut, n), ppy),
            }
        )

    tests = [r["test"] for r in rows]
    n_assets = len(rows)
    return {
        "strategy": strategy,
        "timeframe": timeframe,
        "mode": mode,
        "size": size,
        "params": params,
        "fee": fee,
        "holdout": holdout,
        "common_window": shared,
        "window": {"start": min(r["start"] for r in rows), "end": max(r["end"] for r in rows)},
        "assets": rows,
        "skipped": skipped,
        "summary": {
            "assets": n_assets,
            "profitable": sum(t["total_return"] > 0 for t in tests),
            "beat_hold": sum(t["total_return"] > t["buy_hold_return"] for t in tests),
            "positive_sharpe": sum(t["sharpe"] > 0 for t in tests),
            "avg_test_sharpe": sum(t["sharpe"] for t in tests) / n_assets,
            "avg_correlation": average_correlation(usable),
        },
    }
