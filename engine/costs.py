from sensitivity import segment_numbers
from strategies import STRATEGIES, run_signal

# total cost per trade (fee plus slippage), as fractions: 0%, 0.05%, 0.1% ... 1%
COST_LEVELS = [0.0, 0.0005, 0.001, 0.0015, 0.002, 0.003, 0.005, 0.0075, 0.01]


def break_even(levels, returns) -> dict:
    """Cost per trade at which `returns` crosses zero, by straight-line interpolation.

    status is one of:
      "not_profitable_at_zero"  the result is not positive even with no costs
      "crosses"                 positive at first, then turns negative at `cost`
      "positive_throughout"     still positive at the highest cost tested
    """
    if returns[0] <= 0:
        return {"status": "not_profitable_at_zero", "cost": None}
    for i in range(1, len(returns)):
        if returns[i] <= 0:
            lo, hi = levels[i - 1], levels[i]
            r_lo, r_hi = returns[i - 1], returns[i]
            return {"status": "crosses", "cost": lo + (hi - lo) * r_lo / (r_lo - r_hi)}
    return {"status": "positive_throughout", "cost": levels[-1]}


def cost_stress(data, strategy: str, params: dict, holdout: float = 0.3, levels=None) -> dict:
    levels = list(levels or COST_LEVELS)
    n = len(data)
    cut = int(n * (1 - holdout))
    if cut < 200 or n - cut < 200:
        raise ValueError("Not enough data to split into a training and an unseen part.")

    # the signal does not depend on costs, so compute it once
    signal = STRATEGIES[strategy]["func"](data, **params)

    rows = []
    for cost in levels:
        result = run_signal(data, signal, cost)
        rows.append(
            {
                "cost": cost,
                "train": segment_numbers(result, 0, cut),
                "test": segment_numbers(result, cut, n),
            }
        )

    return {
        "strategy": strategy,
        "params": params,
        "holdout": holdout,
        "rows": rows,
        "break_even": {
            "train": break_even(levels, [r["train"]["return"] for r in rows]),
            "test": break_even(levels, [r["test"]["return"] for r in rows]),
        },
    }