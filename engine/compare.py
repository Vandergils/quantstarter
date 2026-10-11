from strategies import backtest, slice_result
from walkforward import stats

MIN_CANDLES = 400


def compare_assets(datasets: dict, strategy: str, params: dict, fee: float = 0.001, holdout: float = 0.3) -> dict:
    """`datasets` maps a label (such as "ETH/USD") to a price table with a `close` column."""
    rows = []
    skipped = []
    for label, data in datasets.items():
        n = len(data)
        if n < MIN_CANDLES:
            skipped.append({"asset": label, "reason": f"only {n} candles"})
            continue
        cut = int(n * (1 - holdout))
        result = backtest(data, strategy, params, fee)
        rows.append(
            {
                "asset": label,
                "candles": n,
                "start": data.index[0].isoformat()[:10],
                "end": data.index[-1].isoformat()[:10],
                "train": stats(slice_result(result, 0, cut)),
                "test": stats(slice_result(result, cut, n)),
            }
        )

    if not rows:
        raise ValueError("None of the assets has enough data to compare.")

    tests = [r["test"] for r in rows]
    n_assets = len(rows)
    return {
        "strategy": strategy,
        "params": params,
        "fee": fee,
        "holdout": holdout,
        "assets": rows,
        "skipped": skipped,
        "summary": {
            "assets": n_assets,
            "profitable": sum(t["total_return"] > 0 for t in tests),
            "beat_hold": sum(t["total_return"] > t["buy_hold_return"] for t in tests),
            "positive_sharpe": sum(t["sharpe"] > 0 for t in tests),
            "avg_test_sharpe": sum(t["sharpe"] for t in tests) / n_assets,
        },
    }