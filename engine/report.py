import argparse
import itertools

from backtest import load_candles
from metrics import periods_per_year, summary, time_in_market, time_short
from strategies import STRATEGIES, backtest, slice_result

HOLDOUT = 0.3
FEE = 0.001


def stats(result, start, end, ppy):
    seg = slice_result(result, start, end)
    s = summary(seg, ppy)
    s["trades"] = int(seg["trade"].sum())
    s["exposure"] = time_in_market(seg)
    s["short_time"] = time_short(seg)
    return s


def line(label, s):
    return (
        f"  {label:<10} strategy {s['total_return']:>8.2%}  hold {s['buy_hold_return']:>8.2%}  "
        f"maxDD {s['max_drawdown']:>8.2%}  holdDD {s['buy_hold_max_drawdown']:>8.2%}  "
        f"Sharpe {s['sharpe']:>5.2f}  trades {s['trades']:>4}  inMarket {s['exposure']:>4.0%}  short {s['short_time']:>4.0%}"
    )


def main(exchange="yahoo", symbol="BTC/USD", timeframe="1h", mode="long", funding_percent=0.0):
    ppy = periods_per_year(timeframe)
    funding = funding_percent / 100 / ppy   # yearly cost of holding a short, turned into a cost per candle
    data = load_candles(exchange, symbol, timeframe)
    n = len(data)
    cut = int(n * (1 - HOLDOUT))
    print(f"{symbol} ({exchange}, {timeframe}), mode: {mode}" + (f", short funding {funding_percent}% a year" if mode == "long_short" else ""))
    print(f"Candles: {n}")
    print(f"Training: {data.index[0].date()} to {data.index[cut - 1].date()}  ({cut} candles)")
    print(f"Test:     {data.index[cut].date()} to {data.index[-1].date()}  ({n - cut} candles)")
    print(f"Fee: {FEE:.2%}\n")

    for key, spec in STRATEGIES.items():
        defaults = {p["name"]: p["default"] for p in spec["params"]}
        result = backtest(data, key, defaults, FEE, mode, funding)
        print(f"== {spec['label']}  (default settings: {defaults})")
        print(line("Training", stats(result, 0, cut, ppy)))
        print(line("Test", stats(result, cut, n, ppy)))

        # same search as the "Find best settings" button
        names = list(spec["grid"])
        best = None
        for values in itertools.product(*spec["grid"].values()):
            params = dict(zip(names, values))
            if spec["validate"](params):
                continue
            res = backtest(data, key, params, FEE, mode, funding)
            train = stats(res, 0, cut, ppy)
            if best is None or train["sharpe"] > best[1]["sharpe"]:
                best = (params, train, stats(res, cut, n, ppy))
        print(f"  Best on training: {best[0]}")
        print(line("  Training", best[1]))
        print(line("  Test", best[2]))
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Training vs unseen report for every strategy.")
    parser.add_argument("--exchange", default="yahoo")
    parser.add_argument("--symbol", default="BTC/USD")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--mode", choices=["long", "long_short"], default="long")
    parser.add_argument("--funding", type=float, default=0.0, help="yearly cost of holding a short, in percent")
    args = parser.parse_args()
    main(args.exchange, args.symbol, args.timeframe, args.mode, args.funding)