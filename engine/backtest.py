import os

import mysql.connector
import pandas as pd
from dotenv import load_dotenv

from strategies import STRATEGIES, backtest as run_strategy, run_signal, sig_sma

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "collector", ".env"))


def _connect():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )


def list_datasets():
    """Every exchange / symbol / timeframe stored in the database, with its size and date range."""
    db = _connect()
    cur = db.cursor()
    cur.execute(
        """SELECT exchange, symbol, timeframe, COUNT(*), MIN(ts), MAX(ts)
           FROM candles GROUP BY exchange, symbol, timeframe
           ORDER BY symbol, exchange, timeframe"""
    )
    rows = cur.fetchall()
    cur.close()
    db.close()
    return [
        {
            "exchange": e,
            "symbol": sym,
            "timeframe": tf,
            "candles": int(n),
            "start": pd.to_datetime(int(lo), unit="ms").strftime("%Y-%m-%d"),
            "end": pd.to_datetime(int(hi), unit="ms").strftime("%Y-%m-%d"),
        }
        for e, sym, tf, n, lo, hi in rows
    ]


def load_candles(exchange="yahoo", symbol="BTC/USD", timeframe="1h"):
    db = _connect()
    cur = db.cursor()
    cur.execute(
        """SELECT ts, open, high, low, close, volume FROM candles
           WHERE exchange=%s AND symbol=%s AND timeframe=%s ORDER BY ts""",
        (exchange, symbol, timeframe),
    )
    df = pd.DataFrame(
        cur.fetchall(), columns=["ts", "open", "high", "low", "close", "volume"]
    )
    cur.close()
    db.close()
    df["time"] = pd.to_datetime(df["ts"], unit="ms")
    return df.set_index("time")


def sma_crossover(df, fast=20, slow=50, fee=0.001):
    """Kept so older scripts still work. Returns (result, number_of_trades)."""
    result = run_signal(df, sig_sma(df, fast, slow), fee)
    return result, int(result["trade"].sum())


if __name__ == "__main__":
    import argparse

    from metrics import periods_per_year, summary

    parser = argparse.ArgumentParser(description="Every strategy with default settings, full period.")
    parser.add_argument("--exchange", default="yahoo")
    parser.add_argument("--symbol", default="BTC/USD")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--mode", choices=["long", "long_short"], default="long")
    parser.add_argument("--funding", type=float, default=0.0, help="yearly cost of holding a short, in percent")
    parser.add_argument("--size", type=float, default=1.0, help="position size: 1 = the whole account, 2 = twice the account")
    parser.add_argument("--borrow", type=float, default=0.0, help="yearly cost of borrowing the part above 1x, in percent")
    args = parser.parse_args()

    ppy = periods_per_year(args.timeframe)
    data = load_candles(args.exchange, args.symbol, args.timeframe)
    print(f"{args.symbol} ({args.exchange}, {args.timeframe}), mode: {args.mode}: {len(data)} candles\n")

    for key, spec in STRATEGIES.items():
        params = {p["name"]: p["default"] for p in spec["params"]}
        res = run_strategy(data, key, params, fee=0.001, mode=args.mode,
                           short_cost=args.funding / 100 / ppy, size=args.size, borrow_cost=args.borrow / 100 / ppy)
        s = summary(res, ppy)
        print(
            f"{spec['label']:<26} return {s['total_return']:>8.2%}   "
            f"maxDD {s['max_drawdown']:>8.2%}   Sharpe {s['sharpe']:>5.2f}   "
            f"trades {int(res['trade'].sum())}"
        )

    print(f"\n{'Buy and hold':<26} return {s['buy_hold_return']:>8.2%}   maxDD {s['buy_hold_max_drawdown']:>8.2%}")