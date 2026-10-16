import itertools
import math
import os
import sys
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

# let the API import from ../engine
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "engine"))

from backtest import list_datasets, load_candles  # noqa: E402
from compare import compare_assets  # noqa: E402
from costs import cost_stress  # noqa: E402
from metrics import (  # noqa: E402
    HOURS_PER_YEAR, account_wiped, periods_per_year, position_size, summary, time_in_market, time_short,
)
from strategies import MODES, STRATEGIES, backtest, slice_result  # noqa: E402
from sensitivity import run_sensitivity  # noqa: E402
from walkforward import run_walk_forward  # noqa: E402

app = FastAPI(title="QuantStarter API", version="0.5.2")

def cors_origins(value: Optional[str]) -> list:
    """Browser origins allowed to call the API.

    Everything by default, which is fine for local use. To restrict it, set the environment variable
    QUANTSTARTER_CORS_ORIGINS to a comma-separated list. A dashboard opened straight from a file
    has the origin "null", so include that if you still open it that way.
    """
    origins = [o.strip() for o in (value or "").split(",") if o.strip()]
    return origins or ["*"]


# allow the dashboard (a different origin) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(os.getenv("QUANTSTARTER_CORS_ORIGINS")),
    allow_methods=["*"],
    allow_headers=["*"],
)

DISCLAIMER = "Historical simulation only. Not financial advice."
MIN_CANDLES = 300  # hourly or faster; slower timeframes need 150


# ---------- helpers ----------

def total_cost(fee: float, slippage: float) -> float:
    """Cost of one trade: the exchange fee plus slippage (the price you lose by not trading at the quote)."""
    return round(fee + slippage, 6)


def get_spec(strategy: str) -> dict:
    if strategy not in STRATEGIES:
        raise HTTPException(404, f"Unknown strategy '{strategy}'. Options: {', '.join(STRATEGIES)}")
    return STRATEGIES[strategy]


def parse_params(spec: dict, query, validate: bool = True) -> dict:
    """Read the strategy settings from the URL, check ranges, fall back to defaults."""
    params = {}
    for p in spec["params"]:
        raw = query.get(p["name"], p["default"])
        try:
            value = round(float(raw), 2) if p.get("type") == "float" else int(float(raw))
        except (TypeError, ValueError):
            raise HTTPException(400, f"{p['label']} must be a number.")
        if not p["min"] <= value <= p["max"]:
            raise HTTPException(400, f"{p['label']} must be between {p['min']} and {p['max']}.")
        params[p["name"]] = value
    if validate:
        error = spec["validate"](params)
        if error:
            raise HTTPException(400, error)
    return params


def get_ppy(timeframe: str) -> int:
    """Candles per year for a timeframe, or a clear 400 error if it is not supported."""
    try:
        return periods_per_year(timeframe)
    except ValueError as error:
        raise HTTPException(400, str(error))


def check_mode(mode: str) -> None:
    if mode not in MODES:
        raise HTTPException(400, f"Unknown mode '{mode}'. Use one of: {', '.join(MODES)}.")


def per_candle_funding(short_cost_per_year: float, timeframe: str) -> float:
    """Turn a yearly funding or borrow cost for shorts into the cost of one candle."""
    return short_cost_per_year / get_ppy(timeframe)


def seg_summary(seg, ppy: int = HOURS_PER_YEAR) -> dict:
    s = summary(seg, ppy)
    s["trades"] = int(seg["trade"].sum())
    s["exposure"] = time_in_market(seg)
    s["short_time"] = time_short(seg)
    s["account_wiped"] = account_wiped(seg)
    return {k: (v if math.isfinite(v) else 0.0) for k, v in s.items()}


def get_data(exchange: str, symbol: str, timeframe: str):
    minimum = MIN_CANDLES if get_ppy(timeframe) >= HOURS_PER_YEAR else 150
    data = load_candles(exchange, symbol, timeframe)
    if len(data) < minimum:
        raise HTTPException(404, "Not enough candles in the database. Run a collector first.")
    return data


# ---------- endpoints ----------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/datasets")
def datasets():
    """Every price series stored in the database, so the dashboard can offer a choice."""
    return list_datasets()


@app.get("/strategies")
def list_strategies():
    """Everything the dashboard needs to build its controls."""
    return {
        key: {"label": s["label"], "description": s["description"], "params": s["params"],
              "supports_short": "short_func" in s}
        for key, s in STRATEGIES.items()
    }


@app.get("/backtest")
def run_backtest(
    request: Request,
    strategy: str = "sma",
    fee: float = Query(0.001, ge=0, le=0.05),
    slippage: float = Query(0.0, ge=0, le=0.05, description="Extra cost per trade on top of the fee."),
    mode: str = Query("long", description="long = hold or cash. long_short = also profit from falling prices."),
    short_cost: float = Query(0.0, ge=0, le=1.0, description="Yearly cost of holding a short (funding or borrow) as a fraction: 0.05 = 5% a year."),
    size: float = Query(1.0, ge=0.1, le=5.0, description="How much of the account is exposed: 1 = all of it, 0.5 = half, 2 = twice the account (leverage)."),
    borrow_cost: float = Query(0.0, ge=0, le=1.0, description="Yearly cost of borrowing the part above 1x, as a fraction: 0.08 = 8% a year."),
    holdout: float = Query(0.3, ge=0, le=0.5, description="Share of the newest data kept as an unseen test. 0 = off."),
    exchange: str = "yahoo",
    symbol: str = "BTC/USD",
    timeframe: str = "1h",
):
    fee = total_cost(fee, slippage)
    check_mode(mode)
    funding = per_candle_funding(short_cost, timeframe)
    borrow = per_candle_funding(borrow_cost, timeframe)
    if 0 < holdout < 0.1:
        raise HTTPException(400, "Holdout must be 0 (off) or at least 0.1.")

    spec = get_spec(strategy)
    params = parse_params(spec, request.query_params)
    data = get_data(exchange, symbol, timeframe)
    ppy = get_ppy(timeframe)

    result = backtest(data, strategy, params, fee, mode, funding, size, borrow)
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
                "metrics": seg_summary(seg, ppy),
            }
        )

    # send ~500 points to the chart instead of every candle
    step = max(1, n // 500)
    chart = result.iloc[::step]

    return {
        "strategy": strategy,
        "mode": mode,
        "short_cost": short_cost,
        "size": size,
        "borrow_cost": borrow_cost,
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
    slippage: float = Query(0.0, ge=0, le=0.05, description="Extra cost per trade on top of the fee."),
    mode: str = Query("long", description="long = hold or cash. long_short = also profit from falling prices."),
    short_cost: float = Query(0.0, ge=0, le=1.0, description="Yearly cost of holding a short (funding or borrow) as a fraction: 0.05 = 5% a year."),
    size: float = Query(1.0, ge=0.1, le=5.0, description="How much of the account is exposed: 1 = all of it, 0.5 = half, 2 = twice the account (leverage)."),
    borrow_cost: float = Query(0.0, ge=0, le=1.0, description="Yearly cost of borrowing the part above 1x, as a fraction: 0.08 = 8% a year."),
    holdout: float = Query(0.3, ge=0.1, le=0.5),
    exchange: str = "yahoo",
    symbol: str = "BTC/USD",
    timeframe: str = "1h",
):
    """Try many settings, pick the best on the TRAINING part only, then reveal the unseen test.

    This is the classic overfitting demo: the best-looking setting on past data
    often looks much worse on data it has never seen.
    """
    fee = total_cost(fee, slippage)
    check_mode(mode)
    funding = per_candle_funding(short_cost, timeframe)
    borrow = per_candle_funding(borrow_cost, timeframe)
    spec = get_spec(strategy)
    data = get_data(exchange, symbol, timeframe)
    ppy = get_ppy(timeframe)
    n = len(data)
    cut = int(n * (1 - holdout))

    names = list(spec["grid"].keys())
    combos = []
    for values in itertools.product(*spec["grid"].values()):
        params = dict(zip(names, values))
        if spec["validate"](params):
            continue
        result = backtest(data, strategy, params, fee, mode, funding, size, borrow)
        combos.append(
            {
                "params": params,
                "train": seg_summary(slice_result(result, 0, cut), ppy),
                "test": seg_summary(slice_result(result, cut, n), ppy),
            }
        )

    if not combos:
        raise HTTPException(400, "No valid settings to test.")

    combos.sort(key=lambda c: c["train"]["sharpe"], reverse=True)
    return {
        "strategy": strategy,
        "mode": mode,
        "size": size,
        "fee": fee,
        "holdout": holdout,
        "tested": len(combos),
        "best": combos[0],
        "top": combos[:5],
        "disclaimer": DISCLAIMER,
    }


@app.get("/walkforward")
def walkforward(
    strategy: str = "sma",
    fee: float = Query(0.001, ge=0, le=0.05),
    slippage: float = Query(0.0, ge=0, le=0.05, description="Extra cost per trade on top of the fee."),
    mode: str = Query("long", description="long = hold or cash. long_short = also profit from falling prices."),
    short_cost: float = Query(0.0, ge=0, le=1.0, description="Yearly cost of holding a short (funding or borrow) as a fraction: 0.05 = 5% a year."),
    size: float = Query(1.0, ge=0.1, le=5.0, description="How much of the account is exposed: 1 = all of it, 0.5 = half, 2 = twice the account (leverage)."),
    borrow_cost: float = Query(0.0, ge=0, le=1.0, description="Yearly cost of borrowing the part above 1x, as a fraction: 0.08 = 8% a year."),
    folds: int = Query(5, ge=3, le=8, description="How many train/test windows to slide through the data."),
    exchange: str = "yahoo",
    symbol: str = "BTC/USD",
    timeframe: str = "1h",
):
    """Repeat 'pick the best setting on training data, then test it on unseen data' over several windows."""
    fee = total_cost(fee, slippage)
    check_mode(mode)
    funding = per_candle_funding(short_cost, timeframe)
    borrow = per_candle_funding(borrow_cost, timeframe)
    get_spec(strategy)
    data = get_data(exchange, symbol, timeframe)
    try:
        result = run_walk_forward(data, strategy, fee, folds, timeframe, mode, funding, size, borrow)
    except ValueError as error:
        raise HTTPException(400, str(error))
    return {**result, "disclaimer": DISCLAIMER}


@app.get("/sensitivity")
def sensitivity(
    request: Request,
    strategy: str = "sma",
    x: Optional[str] = None,
    y: Optional[str] = None,
    fee: float = Query(0.001, ge=0, le=0.05),
    slippage: float = Query(0.0, ge=0, le=0.05, description="Extra cost per trade on top of the fee."),
    mode: str = Query("long", description="long = hold or cash. long_short = also profit from falling prices."),
    short_cost: float = Query(0.0, ge=0, le=1.0, description="Yearly cost of holding a short (funding or borrow) as a fraction: 0.05 = 5% a year."),
    size: float = Query(1.0, ge=0.1, le=5.0, description="How much of the account is exposed: 1 = all of it, 0.5 = half, 2 = twice the account (leverage)."),
    borrow_cost: float = Query(0.0, ge=0, le=1.0, description="Yearly cost of borrowing the part above 1x, as a fraction: 0.08 = 8% a year."),
    holdout: float = Query(0.3, ge=0.1, le=0.5),
    count: int = Query(9, ge=4, le=12, description="How many values to try along each axis."),
    exchange: str = "yahoo",
    symbol: str = "BTC/USD",
    timeframe: str = "1h",
):
    """Test a grid of neighbouring settings, scored on training and on unseen data."""
    fee = total_cost(fee, slippage)
    check_mode(mode)
    funding = per_candle_funding(short_cost, timeframe)
    borrow = per_candle_funding(borrow_cost, timeframe)
    spec = get_spec(strategy)
    names = [p["name"] for p in spec["params"]]
    x = x or names[0]
    if y is None and len(names) > 1:
        y = next(n for n in names if n != x)
    # the settings that are not on an axis stay at their current value
    fixed = parse_params(spec, request.query_params, validate=False)
    data = get_data(exchange, symbol, timeframe)
    try:
        result = run_sensitivity(data, strategy, x, y, fixed, fee, holdout, count, timeframe, mode, funding, size, borrow)
    except ValueError as error:
        raise HTTPException(400, str(error))
    return {**result, "disclaimer": DISCLAIMER}


MAX_COMPARE_ASSETS = 8


@app.get("/compare")
def compare(
    request: Request,
    strategy: str = "sma",
    fee: float = Query(0.001, ge=0, le=0.05),
    slippage: float = Query(0.0, ge=0, le=0.05, description="Extra cost per trade on top of the fee."),
    mode: str = Query("long", description="long = hold or cash. long_short = also profit from falling prices."),
    short_cost: float = Query(0.0, ge=0, le=1.0, description="Yearly cost of holding a short (funding or borrow) as a fraction: 0.05 = 5% a year."),
    size: float = Query(1.0, ge=0.1, le=5.0, description="How much of the account is exposed: 1 = all of it, 0.5 = half, 2 = twice the account (leverage)."),
    borrow_cost: float = Query(0.0, ge=0, le=1.0, description="Yearly cost of borrowing the part above 1x, as a fraction: 0.08 = 8% a year."),
    holdout: float = Query(0.3, ge=0.1, le=0.5),
    common_window: bool = Query(True, description="Compare every asset over the dates they all have, so the unseen part covers the same period for each."),
    timeframe: str = "1h",
):
    """Run one strategy, with the same settings, on every asset in the database."""
    fee = total_cost(fee, slippage)
    check_mode(mode)
    funding = per_candle_funding(short_cost, timeframe)
    borrow = per_candle_funding(borrow_cost, timeframe)
    spec = get_spec(strategy)
    params = parse_params(spec, request.query_params)

    # one series per symbol: if two exchanges have the same symbol, keep the longer one
    best = {}
    for d in list_datasets():
        if d["timeframe"] != timeframe:
            continue
        if d["symbol"] not in best or d["candles"] > best[d["symbol"]]["candles"]:
            best[d["symbol"]] = d
    chosen = list(best.values())[:MAX_COMPARE_ASSETS]
    if not chosen:
        raise HTTPException(404, "No data in the database yet. Run a collector first.")

    data = {d["symbol"]: load_candles(d["exchange"], d["symbol"], d["timeframe"]) for d in chosen}
    try:
        result = compare_assets(data, strategy, params, fee, holdout, timeframe, mode, funding, size, borrow, common_window)
    except ValueError as error:
        raise HTTPException(400, str(error))
    for row in result["assets"]:
        row["source"] = best[row["asset"]]["exchange"]
    return {**result, "disclaimer": DISCLAIMER}


@app.get("/cost-test")
def cost_test(
    request: Request,
    strategy: str = "sma",
    fee: float = Query(0.001, ge=0, le=0.05),
    slippage: float = Query(0.0, ge=0, le=0.05),
    mode: str = Query("long", description="long = hold or cash. long_short = also profit from falling prices."),
    short_cost: float = Query(0.0, ge=0, le=1.0, description="Yearly cost of holding a short (funding or borrow) as a fraction: 0.05 = 5% a year."),
    size: float = Query(1.0, ge=0.1, le=5.0, description="How much of the account is exposed: 1 = all of it, 0.5 = half, 2 = twice the account (leverage)."),
    borrow_cost: float = Query(0.0, ge=0, le=1.0, description="Yearly cost of borrowing the part above 1x, as a fraction: 0.08 = 8% a year."),
    holdout: float = Query(0.3, ge=0.1, le=0.5),
    exchange: str = "yahoo",
    symbol: str = "BTC/USD",
    timeframe: str = "1h",
):
    """Run the same strategy at rising trading costs and find the cost where the profit disappears."""
    spec = get_spec(strategy)
    params = parse_params(spec, request.query_params)
    data = get_data(exchange, symbol, timeframe)
    check_mode(mode)
    funding = per_candle_funding(short_cost, timeframe)
    borrow = per_candle_funding(borrow_cost, timeframe)
    try:
        result = cost_stress(data, strategy, params, holdout, timeframe=timeframe, mode=mode, short_cost=funding,
                             size=size, borrow_cost=borrow)
    except ValueError as error:
        raise HTTPException(400, str(error))
    return {**result, "current_cost": total_cost(fee, slippage), "disclaimer": DISCLAIMER}


@app.get("/position-size")
def position_size_endpoint(
    balance: float = Query(..., gt=0),
    risk_pct: float = Query(0.01, gt=0, le=0.2),
    entry: float = Query(..., gt=0),
    stop: float = Query(..., gt=0),
):
    units = position_size(balance, risk_pct, entry, stop)
    notional = units * entry
    leverage = notional / balance
    # with a tight stop the position can be worth more than the whole balance, which needs borrowed money
    return {"units": units, "notional": notional, "leverage": leverage, "needs_leverage": leverage > 1.0}