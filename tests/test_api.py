import os
import sys

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "api"))

import main  # noqa: E402


def make_prices(n, freq, seed):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, n)))
    df = pd.DataFrame({"open": close, "high": close * 1.004, "low": close * 0.996, "close": close, "volume": 1.0},
                      index=pd.date_range("2022-01-01", periods=n, freq=freq))
    return df


SERIES = {
    ("BTC/USD", "1h"): make_prices(3000, "h", 1),
    ("BTC/USD", "1d"): make_prices(1500, "D", 2),
    ("ETH/USD", "1d"): make_prices(1500, "D", 3),
    ("TINY/USD", "1d"): make_prices(100, "D", 4),     # too short for most tools
}


def fake_load_candles(exchange="yahoo", symbol="BTC/USD", timeframe="1h"):
    return SERIES.get((symbol, timeframe), SERIES[("TINY/USD", "1d")].iloc[:0])


def fake_list_datasets():
    return [
        {"exchange": "yahoo", "symbol": sym, "timeframe": tf, "candles": len(df),
         "start": str(df.index[0].date()), "end": str(df.index[-1].date())}
        for (sym, tf), df in SERIES.items()
    ]


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(main, "load_candles", fake_load_candles)
    monkeypatch.setattr(main, "list_datasets", fake_list_datasets)
    return TestClient(main.app)


DAILY = {"symbol": "BTC/USD", "timeframe": "1d"}


# ---------- basics ----------

def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_strategies_list_matches_the_registry(client):
    data = client.get("/strategies").json()
    assert set(data) == set(main.STRATEGIES)
    for key, spec in data.items():
        assert spec["params"] and spec["supports_short"] is True


def test_datasets_are_listed(client):
    symbols = {(d["symbol"], d["timeframe"]) for d in client.get("/datasets").json()}
    assert ("BTC/USD", "1d") in symbols and ("ETH/USD", "1d") in symbols


def test_position_size_calculator(client):
    r = client.get("/position-size", params={"balance": 1000, "entry": 60000, "stop": 58000})
    assert r.json()["units"] == pytest.approx(0.005)


# ---------- backtest ----------

def test_backtest_splits_into_training_and_unseen(client):
    r = client.get("/backtest", params={"strategy": "sma", **DAILY}).json()
    assert [p["name"] for p in r["periods"]] == ["Training", "Unseen test"]
    assert r["mode"] == "long" and r["size"] == 1


def test_backtest_without_a_holdout_has_one_period(client):
    r = client.get("/backtest", params={"strategy": "sma", "holdout": 0, **DAILY}).json()
    assert [p["name"] for p in r["periods"]] == ["All data"]


def test_long_short_mode_goes_short(client):
    r = client.get("/backtest", params={"strategy": "sma", "mode": "long_short", **DAILY}).json()
    assert r["mode"] == "long_short"
    assert any(p["metrics"]["short_time"] > 0 for p in r["periods"])


def test_slippage_is_added_to_the_fee(client):
    r = client.get("/backtest", params={"strategy": "sma", "fee": 0.001, "slippage": 0.0005, **DAILY}).json()
    assert r["fee"] == pytest.approx(0.0015)


def test_a_bigger_size_gives_a_deeper_drawdown(client):
    one = client.get("/backtest", params={"strategy": "sma", "size": 1, "holdout": 0, **DAILY}).json()
    three = client.get("/backtest", params={"strategy": "sma", "size": 3, "holdout": 0, **DAILY}).json()
    assert three["periods"][0]["metrics"]["max_drawdown"] < one["periods"][0]["metrics"]["max_drawdown"]


def test_borrowing_cost_does_nothing_at_one_times(client):
    base = {"strategy": "sma", "size": 1, **DAILY}
    a = client.get("/backtest", params=base).json()["periods"][1]["metrics"]["total_return"]
    b = client.get("/backtest", params={**base, "borrow_cost": 0.2}).json()["periods"][1]["metrics"]["total_return"]
    assert a == b


def test_every_strategy_runs_in_both_modes(client):
    for key in main.STRATEGIES:
        for mode in ("long", "long_short"):
            r = client.get("/backtest", params={"strategy": key, "mode": mode, **DAILY})
            assert r.status_code == 200, (key, mode, r.text)


# ---------- the other tools ----------

def test_optimizer(client):
    r = client.get("/optimize", params={"strategy": "sma", **DAILY}).json()
    assert r["best"]["params"] and len(r["top"]) <= 5 and r["tested"] > 0


def test_walk_forward_uses_the_chosen_timeframe(client):
    r = client.get("/walkforward", params={"strategy": "sma", "folds": 4, **DAILY}).json()
    assert r["timeframe"] == "1d" and len(r["fold_results"]) == 4


def test_settings_map_and_axis_validation(client):
    ok = client.get("/sensitivity", params={"strategy": "sma", "x": "fast", "y": "slow", **DAILY})
    assert ok.status_code == 200 and ok.json()["cells"]
    same = client.get("/sensitivity", params={"strategy": "sma", "x": "fast", "y": "fast", **DAILY})
    assert same.status_code == 400


def test_cost_stress_test(client):
    r = client.get("/cost-test", params={"strategy": "breakout", **DAILY}).json()
    assert len(r["rows"]) == 9 and set(r["break_even"]) == {"train", "test"}


def test_comparison_skips_series_that_are_too_short(client):
    r = client.get("/compare", params={"strategy": "sma", "timeframe": "1d"}).json()
    assert {a["asset"] for a in r["assets"]} == {"BTC/USD", "ETH/USD"}
    assert [x["asset"] for x in r["skipped"]] == ["TINY/USD"]


def test_new_settings_reach_every_tool(client):
    extra = {"mode": "long_short", "size": 2, "borrow_cost": 0.05, "short_cost": 0.03}
    for endpoint, more in [("/optimize", {}), ("/walkforward", {"folds": 4}), ("/sensitivity", {}),
                           ("/cost-test", {}), ("/compare", {})]:
        r = client.get(endpoint, params={"strategy": "sma", **DAILY, **more, **extra})
        assert r.status_code == 200, (endpoint, r.text)
        assert r.json()["size"] == 2 and r.json()["mode"] == "long_short"


# ---------- errors are clear ----------

@pytest.mark.parametrize(
    "params, status",
    [
        ({"timeframe": "3d"}, 400),                                  # unsupported timeframe
        ({"mode": "short_only", **DAILY}, 400),                      # unknown mode
        ({"size": 9, **DAILY}, 422),                                 # above the allowed size
        ({"size": 0, **DAILY}, 422),
        ({"strategy": "nope", **DAILY}, 404),                        # unknown strategy
        ({"symbol": "TINY/USD", "timeframe": "1d"}, 404),            # not enough candles
        ({"symbol": "NOPE/USD", "timeframe": "1d"}, 404),            # nothing stored for it
        ({"fast": 80, "slow": 50, **DAILY}, 400),                    # fast must be below slow
        ({"holdout": 0.05, **DAILY}, 400),                           # holdout too small to be useful
        ({"short_cost": 2, **DAILY}, 422),                           # funding above 100% a year
    ],
)
def test_bad_requests_get_clear_errors(client, params, status):
    r = client.get("/backtest", params={"strategy": "sma", **params})
    assert r.status_code == status
    assert "detail" in r.json()


# ---------- configuration ----------

def test_allowed_origins_default_to_everything():
    assert main.cors_origins(None) == ["*"]
    assert main.cors_origins("") == ["*"]


def test_allowed_origins_can_be_restricted():
    assert main.cors_origins("http://localhost:8080, null ") == ["http://localhost:8080", "null"]