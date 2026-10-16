import os
import time
import ccxt
import mysql.connector
from dotenv import load_dotenv

from candles import UPSERT_CANDLE_SQL, is_closed

load_dotenv()

EXCHANGE = "bybit"
SYMBOL = "BTC/USDT"
TIMEFRAME = "1h"
START = "2024-01-01T00:00:00Z"


def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )


def collect():
    ex = getattr(ccxt, EXCHANGE)({"enableRateLimit": True})
    since = ex.parse8601(START)
    db = get_db()
    cur = db.cursor()
    total = 0

    while True:
        candles = ex.fetch_ohlcv(SYMBOL, TIMEFRAME, since=since, limit=1000)
        if not candles:
            break

        # the last candle is usually still forming and has partial values, so only keep finished ones
        rows = [(EXCHANGE, SYMBOL, TIMEFRAME, *c) for c in candles if is_closed(c[0], TIMEFRAME)]
        if rows:
            cur.executemany(UPSERT_CANDLE_SQL, rows)
            db.commit()
            total += len(rows)

        since = candles[-1][0] + 1
        print(f"Saved {total} candles...")
        if len(candles) < 1000:
            break
        time.sleep(0.2)

    cur.close()
    db.close()
    print("Done.")


if __name__ == "__main__":
    collect()