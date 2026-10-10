# QuantStarter

A small, beginner-friendly toolkit for testing crypto trading ideas on historical prices before risking real money.

You pick a strategy and its settings in a web dashboard, and QuantStarter shows how it would have performed compared with simply holding the coin, including trading fees and risk measures.

![Dashboard screenshot](docs/screenshot.png)

> **Educational use only.** Backtests are simulations on historical data. Past results do not predict future results. Nothing here is financial advice.

## What's inside

| Part | Language | What it does |
|---|---|---|
| `collector/` | Python | Downloads price candles (OHLCV) from exchanges via `ccxt`, or from Yahoo Finance as a fallback, and saves them to MySQL |
| `engine/` | Python | Backtester, strategies, and metrics (return, max drawdown, Sharpe, Sortino, win rate, position sizing) |
| `api/` | Python (FastAPI) | Serves backtest results as JSON |
| `dashboard/` | JavaScript | A single-page web UI with sliders, an equity chart, and plain-language metric cards |
| `db/` | SQL | MySQL schema |

How data flows:

```
Exchange / Yahoo -> collector -> MySQL (candles) -> engine -> API -> dashboard
```

## Requirements

- Python 3.11 or newer
- MySQL 8 (or MariaDB). Easiest options: [Laragon](https://laragon.org) on Windows, or Docker on any system
- A modern web browser

## Setup

### 1. Get the code

```bash
git clone https://github.com/Vandergils/quantstarter.git
cd quantstarter
```

### 2. Start MySQL

**Option A: Laragon (Windows, light on RAM).** Open Laragon, click **Start All**, then open phpMyAdmin (`http://localhost/phpmyadmin`) and run the contents of `db/schema.sql` in the SQL tab.

**Option B: Docker.**

```bash
docker compose up -d
```

The database and table are created automatically from `db/schema.sql`. Change the password in `docker-compose.yml` before using it for anything beyond local testing.

### 3. Configure the database connection

Copy the example settings and edit them to match your MySQL:

```bash
cp collector/.env.example collector/.env        # macOS / Linux
copy collector\.env.example collector\.env      # Windows (cmd)
```

Laragon's default is user `root` with an empty password. If you use the Docker option, set `DB_PASSWORD` to the password from `docker-compose.yml`.

### 4. Install Python packages

Using a virtual environment keeps things tidy:

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
python -m pip install -r requirements.txt
```

### 5. Download price data

Pick one:

```bash
python collector/collect.py          # from an exchange (ccxt), default Bybit/Binance settings in the file
python collector/collect_yahoo.py    # from Yahoo Finance, no API key needed
```

Some networks or regions block exchange APIs. If `collect.py` fails with a network error, `collector/test_exchanges.py` shows which exchanges your connection can reach, and `collect_yahoo.py` is the fallback. Hourly Yahoo data covers roughly the last two years.

The collector and the backtester must use the same source name. The defaults in `engine/backtest.py` and `api/main.py` are `yahoo` and `BTC/USD`. If you collect from an exchange, change those defaults to match (for example `bybit` and `BTC/USDT`).

### 6. Run a backtest in the terminal

```bash
python engine/backtest.py
```

### 7. Start the API and the dashboard

```bash
python -m uvicorn api.main:app --reload
```

Then open `dashboard/index.html` in your browser (or serve the folder with any static server). Interactive API docs are at `http://127.0.0.1:8000/docs`.

## How to read the results

| Metric | What it tells you |
|---|---|
| Total return vs buy and hold | Did the strategy beat doing nothing? |
| Max drawdown | The worst fall from a peak. Could you sit through it? |
| Sharpe ratio | Return per unit of risk. Roughly: above 1 is decent, below 0 lost money |
| Sortino ratio | Like Sharpe, but only counts downside swings |
| Win rate | Share of trades that made money. Low is fine if winners are much bigger than losers |
| Trades | More trades means more fees, and very few trades means the result may be luck |

A result looks promising only if it holds up when you raise the fee, change the settings slightly, and test a different time period. Be careful of **overfitting**: if you try many settings and keep the best one, you mostly found what fit past noise. Tune on one part of the data and check on a part you did not touch.

## Add your own strategy

A strategy only has to decide, for each candle, whether to hold (`1`) or stay in cash (`0`). In `engine/backtest.py`, `sma_crossover` is the example. The key lines are:

```python
signal = (df["fast"] > df["slow"]).astype(int)
df["position"] = signal.shift(1).fillna(0)   # trade on the NEXT candle
```

The `shift(1)` matters: it makes the strategy act on the following candle, so it never trades on information it could not have had yet (look-ahead bias). Keep it in any strategy you write. The metrics, API, and dashboard work with any strategy that returns a table with the columns `position`, `strategy_ret`, `equity`, and `buy_hold`.

## Project layout

```
quantstarter/
├── README.md
├── LICENSE
├── requirements.txt
├── docker-compose.yml
├── db/schema.sql
├── collector/
│   ├── collect.py
│   ├── collect_yahoo.py
│   ├── test_exchanges.py
│   └── .env.example
├── engine/
│   ├── backtest.py
│   ├── metrics.py
│   └── sweep.py
├── api/main.py
├── dashboard/index.html
└── tests/test_metrics.py
```

## Tests

```bash
python -m pip install pytest
python -m pytest tests
```

## Ideas for contributions

- More strategies (RSI, Bollinger Bands, breakout, momentum)
- A strategy dropdown in the dashboard and API
- Train/test split to show overfitting
- Optional C++ module (via `pybind11`) for faster indicators
- More assets and timeframes

Issues and pull requests are welcome.

## License

MIT. See [LICENSE](LICENSE).
![tests](https://github.com/Vandergils/quantstarter/actions/workflows/tests.yml/badge.svg)