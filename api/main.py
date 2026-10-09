import os
import sys

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# let the API import from ../engine
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "engine"))

from backtest import load_candles, sma_crossover  # noqa: E402
from metrics import summary, position_size  # noqa: E402

app = FastAPI(title="QuantStarter API")

# allow the dashboard (different port) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # fine for local dev; restrict this if you deploy
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/backtest")
def backtest(
    exchange: str = "yahoo",
    symbol: str = "BTC/USD",
    timeframe: str = "1h",
    fast: int = Query(20, ge=2, le=500),
    slow: int = Query(50, ge=3, le=1000),
    fee: float = Query(0.001, ge=0, le=0.05),
):
    if fast >= slow:
        raise HTTPException(400, "fast must be smaller than slow")

    data = load_candles(exchange, symbol, timeframe)
    if len(data) <= slow:
        raise HTTPException(404, "Not enough candles in the database for this setting")

    result, n_trades = sma_crossover(data, fast=fast, slow=slow, fee=fee)

    # send ~500 points to the chart instead of all 16k
    step = max(1, len(result) // 500)
    chart = result.iloc[::step]

    return {
        "params": {"fast": fast, "slow": slow, "fee": fee},
        "candles": len(result),
        "trades": n_trades,
        "metrics": summary(result),
        "chart": {
            "time": [t.isoformat() for t in chart.index],
            "equity": chart["equity"].round(4).tolist(),
            "buy_hold": chart["buy_hold"].round(4).tolist(),
        },
        "disclaimer": "Historical simulation only. Not financial advice.",
    }


@app.get("/position-size")
def position_size_endpoint(
    balance: float = Query(..., gt=0),
    risk_pct: float = Query(0.01, gt=0, le=0.2),
    entry: float = Query(..., gt=0),
    stop: float = Query(..., gt=0),
):
    return {"units": position_size(balance, risk_pct, entry, stop)}