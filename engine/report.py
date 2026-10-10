import itertools

from backtest import load_candles
from metrics import summary
from strategies import STRATEGIES, backtest, slice_result

HOLDOUT = 0.3
FEE = 0.001


def stats(result, start, end):
    seg = slice_result(result, start, end)
    s = summary(seg)
    s["trades"] = int(seg["trade"].sum())
    s["exposure"] = float(seg["position"].mean())
    return s


def line(label, s):
    return (
        f"  {label:<10} strategy {s['total_return']:>8.2%}  hold {s['buy_hold_return']:>8.2%}  "
        f"maxDD {s['max_drawdown']:>8.2%}  holdDD {s['buy_hold_max_drawdown']:>8.2%}  "
        f"Sharpe {s['sharpe']:>5.2f}  trades {s['trades']:>4}  inMarket {s['exposure']:>4.0%}"
    )


def main():
    data = load_candles()
    n = len(data)
    cut = int(n * (1 - HOLDOUT))
    print(f"Candles: {n}")
    print(f"Training: {data.index[0].date()} to {data.index[cut - 1].date()}  ({cut} candles)")
    print(f"Test:     {data.index[cut].date()} to {data.index[-1].date()}  ({n - cut} candles)")
    print(f"Fee: {FEE:.2%}\n")

    for key, spec in STRATEGIES.items():
        defaults = {p["name"]: p["default"] for p in spec["params"]}
        result = backtest(data, key, defaults, FEE)
        print(f"== {spec['label']}  (default settings: {defaults})")
        print(line("Training", stats(result, 0, cut)))
        print(line("Test", stats(result, cut, n)))

        # same search as the "Find best settings" button
        names = list(spec["grid"])
        best = None
        for values in itertools.product(*spec["grid"].values()):
            params = dict(zip(names, values))
            if spec["validate"](params):
                continue
            res = backtest(data, key, params, FEE)
            train = stats(res, 0, cut)
            if best is None or train["sharpe"] > best[1]["sharpe"]:
                best = (params, train, stats(res, cut, n))
        print(f"  Best on training: {best[0]}")
        print(line("  Training", best[1]))
        print(line("  Test", best[2]))
        print()


if __name__ == "__main__":
    main()