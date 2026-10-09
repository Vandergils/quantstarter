import os
import mysql.connector
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

SOURCE = "yahoo"
SYMBOL = "BTC/USD"      # label stored in the DB
YF_TICKER = "BTC-USD"   # Yahoo's ticker
TIMEFRAME = "1h"        # "1h" or "1d"
PERIOD = "700d"         # hourly data is limited to ~730 days; use "max" for 1d


def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )


def collect():
    df = yf.Ticker(YF_TICKER).history(period=PERIOD, interval=TIMEFRAME)
    if df.empty:
        print("No data returned. Check your connection or ticker.")
        return

    rows = [
        (
            SOURCE, SYMBOL, TIMEFRAME,
            int(idx.timestamp() * 1000),
            float(r["Open"]), float(r["High"]), float(r["Low"]),
            float(r["Close"]), float(r["Volume"]),
        )
        for idx, r in df.iterrows()
    ]

    db = get_db()
    cur = db.cursor()
    cur.executemany(
        """INSERT IGNORE INTO candles
           (exchange, symbol, timeframe, ts, open, high, low, close, volume)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        rows,
    )
    db.commit()
    print(f"Saved {len(rows)} candles from {YF_TICKER} ({TIMEFRAME}).")
    cur.close()
    db.close()


if __name__ == "__main__":
    collect()