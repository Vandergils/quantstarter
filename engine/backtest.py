import os

import mysql.connector
import pandas as pd
from dotenv import load_dotenv

from strategies import STRATEGIES, backtest as run_strategy, run_signal, sig_sma

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "collector", ".env"))


def load_candles(exchange="yahoo", symbol="BTC/USD", timeframe="1h"):
    db = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )
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
    """Kept so older scripts (like sweep.py) still work. Returns (result, number_of_trades)."""
    result = run_signal(df, sig_sma(df, fast, slow), fee)
    return result, int(result["trade"].sum())


if __name__ == "__main__":
    from metrics import summary

    data = load_candles()
    print(f"Candles: {len(data)}\n")

    for key, spec in STRATEGIES.items():
        params = {p["name"]: p["default"] for p in spec["params"]}
        res = run_strategy(data, key, params, fee=0.001)
        s = summary(res)
        print(
            f"{spec['label']:<26} return {s['total_return']:>8.2%}   "
            f"maxDD {s['max_drawdown']:>8.2%}   Sharpe {s['sharpe']:>5.2f}   "
            f"trades {int(res['trade'].sum())}"
        )

    print(f"\n{'Buy and hold':<26} return {s['buy_hold_return']:>8.2%}   maxDD {s['buy_hold_max_drawdown']:>8.2%}")