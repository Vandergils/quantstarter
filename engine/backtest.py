import os
import mysql.connector
import pandas as pd
from dotenv import load_dotenv

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
    """Long when fast SMA > slow SMA, otherwise flat. fee = cost per trade (0.001 = 0.1%)."""
    df = df.copy()
    df["fast"] = df["close"].rolling(fast).mean()
    df["slow"] = df["close"].rolling(slow).mean()

    signal = (df["fast"] > df["slow"]).astype(int)
    # shift(1): act on the NEXT candle, so we never trade on info we didn't have yet
    df["position"] = signal.shift(1).fillna(0)

    df["market_ret"] = df["close"].pct_change().fillna(0)
    trades = df["position"].diff().abs().fillna(0)
    df["strategy_ret"] = df["position"] * df["market_ret"] - trades * fee

    df["equity"] = (1 + df["strategy_ret"]).cumprod()
    df["buy_hold"] = (1 + df["market_ret"]).cumprod()
    return df, int(trades.sum())


if __name__ == "__main__":
    from metrics import summary, position_size

    data = load_candles()
    result, n_trades = sma_crossover(data)
    s = summary(result)

    print(f"Candles:            {len(result)}")
    print(f"Trades:             {n_trades}")
    print(f"Strategy return:    {s['total_return']:.2%}")
    print(f"Buy & hold return:  {s['buy_hold_return']:.2%}")
    print(f"Max drawdown:       {s['max_drawdown']:.2%}  (buy & hold: {s['buy_hold_max_drawdown']:.2%})")
    print(f"Sharpe:             {s['sharpe']:.2f}")
    print(f"Sortino:            {s['sortino']:.2f}")
    print(f"Win rate:           {s['win_rate']:.2%}")

    # Example: $1,000 account, risk 1%, entry 60000, stop 58000
    print(f"Position size:      {position_size(1000, 0.01, 60000, 58000):.6f} BTC")