import math

from metrics import HOURS_PER_YEAR, min_segment_candles, periods_per_year, sharpe
from strategies import STRATEGIES, backtest

MIN_PART_CANDLES = 200  # hourly default; slower timeframes use min_segment_candles()


def axis_values(param: dict, count: int = 9, include=None) -> list:
    """Evenly spaced values from the setting's minimum to its maximum.

    `include` (your current slider value) is added so you can find your own setting on the map.
    """
    lo, hi = param["min"], param["max"]
    count = max(2, count)
    raw = [lo + (hi - lo) * i / (count - 1) for i in range(count)]
    is_float = param.get("type") == "float"
    values = []
    for v in raw:
        v = round(v, 2) if is_float else int(round(v))
        if v not in values:
            values.append(v)
    if include is not None and lo <= include <= hi and include not in values:
        values.append(include)
    return sorted(values)


def segment_numbers(result, start: int, end: int, ppy: int = HOURS_PER_YEAR) -> dict:
    ret = result["strategy_ret"].iloc[start:end]
    sh = sharpe(ret, ppy)
    total = float((1 + ret).prod() - 1)
    return {
        "sharpe": sh if math.isfinite(sh) else 0.0,
        "return": total if math.isfinite(total) else 0.0,
        "trades": int(result["trade"].iloc[start:end].sum()),
    }


def _hold_numbers(data, start: int, end: int, ppy: int = HOURS_PER_YEAR) -> dict:
    """Buy and hold over the same period, for comparison with the grid."""
    ret = data["close"].pct_change().fillna(0).iloc[start:end]
    sh = sharpe(ret, ppy)
    total = float((1 + ret).prod() - 1)
    return {
        "sharpe": sh if math.isfinite(sh) else 0.0,
        "return": total if math.isfinite(total) else 0.0,
    }


def _share(cells, part):
    return sum(c[part]["sharpe"] > 0 for c in cells) / len(cells)


def run_sensitivity(data, strategy, x_name, y_name, fixed, fee=0.001, holdout=0.3, count=9,
                    timeframe="1h") -> dict:
    spec = STRATEGIES[strategy]
    by_name = {p["name"]: p for p in spec["params"]}

    if x_name not in by_name:
        raise ValueError(f"Unknown setting '{x_name}'.")
    if y_name is not None and (y_name not in by_name or y_name == x_name):
        raise ValueError("Pick two different settings for the two axes.")

    ppy = periods_per_year(timeframe)
    min_part = min_segment_candles(timeframe)
    n = len(data)
    cut = int(n * (1 - holdout))
    if cut < min_part or n - cut < min_part:
        raise ValueError("Not enough data to split into a training and an unseen part.")

    xs = axis_values(by_name[x_name], count, fixed.get(x_name))
    ys = axis_values(by_name[y_name], count, fixed.get(y_name)) if y_name else [None]

    cells = []
    for yi, yv in enumerate(ys):
        for xi, xv in enumerate(xs):
            params = dict(fixed)
            params[x_name] = xv
            if y_name:
                params[y_name] = yv
            if spec["validate"](params):
                continue  # not a valid combination (for example fast >= slow)
            result = backtest(data, strategy, params, fee)
            cells.append(
                {"xi": xi, "yi": yi, "x": xv, "y": yv,
                 "train": segment_numbers(result, 0, cut, ppy), "test": segment_numbers(result, cut, n, ppy)}
            )

    if not cells:
        raise ValueError("No valid settings in this range.")

    best = max(cells, key=lambda c: c["train"]["sharpe"])
    neighbours = [
        c for c in cells
        if c is not best and abs(c["xi"] - best["xi"]) <= 1 and abs(c["yi"] - best["yi"]) <= 1
    ]

    def average(items, part):
        return sum(c[part]["sharpe"] for c in items) / len(items) if items else 0.0

    return {
        "strategy": strategy,
        "timeframe": timeframe,
        "fee": fee,
        "holdout": holdout,
        "fixed": fixed,
        "x": {"name": x_name, "label": by_name[x_name]["label"], "values": xs},
        "y": {"name": y_name, "label": by_name[y_name]["label"] if y_name else None, "values": ys},
        "current": {
            "xi": xs.index(fixed[x_name]) if fixed.get(x_name) in xs else -1,
            "yi": ys.index(fixed[y_name]) if y_name and fixed.get(y_name) in ys else (0 if not y_name else -1),
        },
        "hold": {"train": _hold_numbers(data, 0, cut, ppy), "test": _hold_numbers(data, cut, n, ppy)},
        "cells": cells,
        "summary": {
            "valid": len(cells),
            "share_positive_train": _share(cells, "train"),
            "share_positive_test": _share(cells, "test"),
            "best": {
                "xi": best["xi"], "yi": best["yi"], "x": best["x"], "y": best["y"],
                "train_sharpe": best["train"]["sharpe"],
                "test_sharpe": best["test"]["sharpe"],
                "test_return": best["test"]["return"],
            },
            "neighbors": {
                "count": len(neighbours),
                "avg_train": average(neighbours, "train"),
                "avg_test": average(neighbours, "test"),
            },
        },
    }