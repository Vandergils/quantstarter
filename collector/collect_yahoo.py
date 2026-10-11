import os
import sys

import mysql.connector
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

SOURCE = "yahoo"
TIMEFRAME = "1h"      # the metrics in this project assume hourly candles
PERIOD = "700d"       # Yahoo keeps about 730 days of hourly data
DEFAULT_TICKERS = ["BTC-USD"]


def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )


def collect(ticker: str, db) -> int:
    symbol = ticker.upper().replace("-", "/")
    df = yf.Ticker(ticker).history(period=PERIOD, interval=TIMEFRAME)
    if df.empty:
        print(f"{ticker}: no data returned (check the ticker and your connection).")
        return 0

    rows = [
        (
            SOURCE, symbol, TIMEFRAME,
            int(idx.timestamp() * 1000),
            float(r["Open"]), float(r["High"]), float(r["Low"]),
            float(r["Close"]), float(r["Volume"]),
        )
        for idx, r in df.iterrows()
    ]

    cur = db.cursor()
    cur.executemany(
        """INSERT IGNORE INTO candles
           (exchange, symbol, timeframe, ts, open, high, low, close, volume)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        rows,
    )
    db.commit()
    added = cur.rowcount
    cur.close()
    print(f"{ticker}: downloaded {len(rows)} candles, {added} new, stored as {symbol} ({TIMEFRAME}).")
    return len(rows)


def main(tickers):
    db = get_db()
    try:
        for ticker in tickers:
            collect(ticker, db)
    finally:
        db.close()


if __name__ == "__main__":
    main(sys.argv[1:] or DEFAULT_TICKERS)