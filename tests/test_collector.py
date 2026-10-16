import os
import sys

import pandas as pd
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "collector"))

import candles  # noqa: E402
import collect_yahoo  # noqa: E402

HOUR = 3_600_000


def test_a_forming_candle_is_not_closed():
    now = 10 * HOUR + 1234
    assert candles.is_closed(9 * HOUR, "1h", now) is True    # the 09:00 candle ended at 10:00
    assert candles.is_closed(10 * HOUR, "1h", now) is False  # the 10:00 candle is still forming


def test_a_candle_is_closed_exactly_when_it_ends():
    assert candles.is_closed(9 * HOUR, "1h", 10 * HOUR) is True
    assert candles.is_closed(9 * HOUR, "1h", 10 * HOUR - 1) is False


def test_longer_timeframes():
    day = 24 * HOUR
    assert candles.is_closed(0, "4h", 4 * HOUR) is True
    assert candles.is_closed(0, "4h", 4 * HOUR - 1) is False
    assert candles.is_closed(0, "1d", day - 1) is False
    assert candles.is_closed(0, "1d", day) is True


def test_unknown_timeframe_is_an_error_not_a_silent_save():
    with pytest.raises(ValueError):
        candles.is_closed(0, "7x", 10 * HOUR)


def test_insert_statement_refreshes_stored_candles():
    assert "ON DUPLICATE KEY UPDATE" in candles.UPSERT_CANDLE_SQL
    assert "INSERT IGNORE" not in candles.UPSERT_CANDLE_SQL


class FakeCursor:
    def __init__(self):
        self.calls = []

    def executemany(self, sql, rows):
        self.calls.append((sql, list(rows)))

    def close(self):
        pass


class FakeDb:
    def __init__(self):
        self.cursor_obj = FakeCursor()
        self.commits = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1


def hourly_frame(periods=4):
    """The last row is the hour that is happening right now, like Yahoo returns it."""
    end = pd.Timestamp.now(tz="UTC").floor("h")
    index = pd.date_range(end=end, periods=periods, freq="h")
    values = [100.0 + i for i in range(periods)]
    return pd.DataFrame(
        {"Open": values, "High": values, "Low": values, "Close": values, "Volume": [1.0] * periods},
        index=index,
    ), end


def test_yahoo_collector_leaves_the_forming_candle_out(monkeypatch):
    frame, forming_hour = hourly_frame(4)
    monkeypatch.setattr(collect_yahoo, "fetch", lambda ticker, timeframe: frame)
    db = FakeDb()

    saved = collect_yahoo.collect("BTC-USD", "1h", db)

    sql, rows = db.cursor_obj.calls[0]
    stored_times = [r[3] for r in rows]
    assert saved == 3 and len(rows) == 3
    assert int(forming_hour.timestamp() * 1000) not in stored_times
    assert sql == candles.UPSERT_CANDLE_SQL
    assert db.commits == 1


def test_yahoo_collector_saves_nothing_when_only_a_forming_candle_exists(monkeypatch):
    frame, _ = hourly_frame(1)
    monkeypatch.setattr(collect_yahoo, "fetch", lambda ticker, timeframe: frame)
    db = FakeDb()

    assert collect_yahoo.collect("BTC-USD", "1h", db) == 0
    assert db.cursor_obj.calls == []
