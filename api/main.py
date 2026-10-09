import itertools
import math
import os
import sys

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

# let the API import from ../engine
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "engine"))

from backtest import load_candles  # noqa: E402
from metrics import position_size, summary  # noqa: E402
from strategies import STRATEGIES, backtest, slice_result  # noqa: E402

app = FastAPI(title="QuantStarter API")

# allow the dashboard (a different origin) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # fine for local development; restrict this if you deploy
    allow_methods=["*"],
    allow_headers=["*"],
)

DISCLAIMER = "Historical simulation only. Not financial advice."
MIN_CANDLES = 300


# ---------- helpers ----------

def get_spec(strategy: str) -> dict:
    if strategy not in STRATEGIES:
        raise HTTPException(404, f"Unknown strategy '{strategy}'. Options: {', '.join(STRATEGIES)}")
    return STRATEGIES[strategy]


def parse_params(spec: dict, query) -> dict:
    """Read the strategy settings from the URL, check ranges, fall back to defaults."""
    params = {}
    for p in spec["params"]:
        raw = query.get(p["name"], p["default"])
        try:
            value = int(float(raw))
        except (TypeError, ValueError):
            raise HTTPException(400, f"{p['label']} must be a number.")
        if not p["min"] <= value <= p["max"]:
            raise HTTPException(400, f"{p['label']} must be between {p['min']} and {p['max']}.")
        params[p["name"]] = value
    error = spec["validate"](params)
    if error:
        raise HTTPException(400, error)
    return params


def seg_summary(seg) -> dict:
    s = summary(seg)
    s["trades"] = int(seg["trade"].sum())
    return {k: (v if math.isfinite(v) else 0.0) for k, v in s.items()}


def get_data(exchange: str, symbol: str, timeframe: str):
    data = load_candles(exchange, symbol, timeframe)
    if len(data) < MIN_CANDLES:
        raise HTTPException(404, "Not enough candles in the database. Run a collector first.")
    return data


# ---------- endpoints ----------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/strategies")
def list_strategies():
    """Everything the dashboard needs to build its controls."""
    return {
        key: {"label": s["label"], "description": s["description"], "params": s["params"]}
        for key, s in STRATEGIES.items()
    }


@app.get("/backtest")
def run_backtest(
    request: Request,
    strategy: str = "sma",
    fee: float = Query(0.001, ge=0, le=0.05),
    holdout: float = Query(0.3, ge=0, le=0.5, description="Share of the newest data kept as an unseen test. 0 = off."),
    exchange: str = "yahoo",
    symbol: str = "BTC/USD",
    timeframe: str = "1h",
):
    if 0 < holdout < 0.1:
        raise HTTPException(400, "Holdout must be 0 (off) or at least 0.1.")

    spec = get_spec(strategy)
    params = parse_params(spec, request.query_params)
    data = get_data(exchange, symbol, timeframe)

    result = backtest(data, strategy, params, fee)
    n = len(result)

    if holdout > 0:
        cut = int(n * (1 - holdout))
        parts = [("Training", 0, cut), ("Unseen test", cut, n)]
        split_time = result.index[cut].isoformat()
    else:
        parts = [("All data", 0, n)]
        split_time = None

    periods = []
    for name, start, end in parts:
        seg = slice_result(result, start, end)
        periods.append(
            {
                "name": name,
                "start": seg.index[0].isoformat()[:10],
                "end": seg.index[-1].isoformat()[:10],
                "candles": len(seg),
                "metrics": seg_summary(seg),
            }
        )

    # send ~500 points to the chart instead of every candle
    step = max(1, n // 500)
    chart = result.iloc[::step]

    return {
        "strategy": strategy,
        "params": params,
        "fee": fee,
        "holdout": holdout,
        "candles": n,
        "split_time": split_time,
        "periods": periods,
        "chart": {
            "time": [t.isoformat() for t in chart.index],
            "equity": chart["equity"].round(4).tolist(),
            "buy_hold": chart["buy_hold"].round(4).tolist(),
        },
        "disclaimer": DISCLAIMER,
    }


@app.get("/optimize")
def optimize(
    strategy: str = "sma",
    fee: float = Query(0.001, ge=0, le=0.05),
    holdout: float = Query(0.3, ge=0.1, le=0.5),
    exchange: str = "yahoo",
    symbol: str = "BTC/USD",
    timeframe: str = "1h",
):
    """Try many settings, pick the best on the TRAINING part only, then reveal the unseen test.

    This is the classic overfitting demo: the best-looking setting on past data
    often looks much worse on data it has never seen.
    """
    spec = get_spec(strategy)
    data = get_data(exchange, symbol, timeframe)
    n = len(data)
    cut = int(n * (1 - holdout))

    names = list(spec["grid"].keys())
    combos = []
    for values in itertools.product(*spec["grid"].values()):
        params = dict(zip(names, values))
        if spec["validate"](params):
            continue
        result = backtest(data, strategy, params, fee)
        combos.append(
            {
                "params": params,
                "train": seg_summary(slice_result(result, 0, cut)),
                "test": seg_summary(slice_result(result, cut, n)),
            }
        )

    if not combos:
        raise HTTPException(400, "No valid settings to test.")

    combos.sort(key=lambda c: c["train"]["sharpe"], reverse=True)
    return {
        "strategy": strategy,
        "holdout": holdout,
        "tested": len(combos),
        "best": combos[0],
        "top": combos[:5],
        "disclaimer": DISCLAIMER,
    }


@app.get("/position-size")
def position_size_endpoint(
    balance: float = Query(..., gt=0),
    risk_pct: float = Query(0.01, gt=0, le=0.2),
    entry: float = Query(..., gt=0),
    stop: float = Query(..., gt=0),
):
    return {"units": position_size(balance, risk_pct, entry, stop)}