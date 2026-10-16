import argparse
import os

import mysql.connector
import yfinance as yf
from dotenv import load_dotenv

from candles import UPSERT_CANDLE_SQL, is_closed

load_dotenv()

SOURCE = "yahoo"
DEFAULT_TICKERS = ["BTC-USD"]
TIMEFRAMES = ["1h", "4h", "1d"]


def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )


def fetch(ticker: str, timeframe: str):
    """Download candles. Yahoo has no 4-hour interval, so those are built from hourly candles."""
    if timeframe == "1d":
        return yf.Ticker(ticker).history(period="max", interval="1d")

    hourly = yf.Ticker(ticker).history(period="700d", interval="1h")  # Yahoo keeps about 730 days
    if timeframe == "1h" or hourly.empty:
        return hourly

    return (
        hourly.resample("4h")
        .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
        .dropna()
    )


def collect(ticker: str, timeframe: str, db) -> int:
    symbol = ticker.upper().replace("-", "/")
    df = fetch(ticker, timeframe)
    if df.empty:
        print(f"{ticker}: no data returned (check the ticker and your connection).")
        return 0

    rows = [
        (
            SOURCE, symbol, timeframe,
            int(idx.timestamp() * 1000),
            float(r["Open"]), float(r["High"]), float(r["Low"]),
            float(r["Close"]), float(r["Volume"]),
        )
        for idx, r in df.iterrows()
    ]

    # Yahoo includes the candle that is still forming; its values are partial, so leave it for the next run
    rows = [r for r in rows if is_closed(r[3], timeframe)]
    if not rows:
        print(f"{ticker}: no finished candles yet.")
        return 0

    cur = db.cursor()
    cur.executemany(UPSERT_CANDLE_SQL, rows)
    db.commit()
    cur.close()
    print(f"{ticker}: saved {len(rows)} finished candles as {symbol} ({timeframe}); candles already stored are refreshed.")
    return len(rows)


def main(tickers, timeframe="1h"):
    db = get_db()
    try:
        for ticker in tickers:
            collect(ticker, timeframe, db)
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download candles from Yahoo Finance into MySQL.")
    parser.add_argument("tickers", nargs="*", default=DEFAULT_TICKERS, help="Yahoo tickers, for example BTC-USD ETH-USD")
    parser.add_argument("--timeframe", choices=TIMEFRAMES, default="1h", help="candle size (default: 1h)")
    args = parser.parse_args()
    main(args.tickers, args.timeframe)