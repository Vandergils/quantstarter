"""Rules shared by the collectors."""
import time

# length of one candle, in milliseconds
PERIOD_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
    "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000, "6h": 21_600_000,
    "12h": 43_200_000, "1d": 86_400_000,
}

# Insert a candle, or refresh it if it is already stored. Refreshing matters because an earlier run
# may have saved a candle before it was finished. (VALUES() is deprecated in MySQL 8 but still works
# in 8.4 and 9.x, and MariaDB needs it.)
UPSERT_CANDLE_SQL = """INSERT INTO candles
    (exchange, symbol, timeframe, ts, open, high, low, close, volume)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON DUPLICATE KEY UPDATE
    open=VALUES(open), high=VALUES(high), low=VALUES(low), close=VALUES(close), volume=VALUES(volume)"""


def is_closed(ts_ms: int, timeframe: str, now_ms: float = None) -> bool:
    """True once the candle that opened at `ts_ms` has finished (a forming candle has partial values)."""
    if timeframe not in PERIOD_MS:
        raise ValueError(f"Unknown timeframe '{timeframe}'. Use one of: {', '.join(PERIOD_MS)}.")
    now = time.time() * 1000 if now_ms is None else now_ms
    return ts_ms + PERIOD_MS[timeframe] <= now
