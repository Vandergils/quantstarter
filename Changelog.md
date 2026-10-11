# Changelog

## 0.2.0 - 2026-10-12

More ways to doubt a result: other coins, realistic costs, and a map of neighbouring settings.

### Added

- **Bollinger Bands** strategy (buy below the lower band, sell at the middle band)
- Strategy settings can now be decimals (`"type": "float"` in the registry)
- **Several coins:** `collect_yahoo.py` accepts several tickers, the dashboard has a **Data** menu, and **Compare across assets** runs one strategy, with the same settings, on every coin in the database (new `/datasets` and `/compare` endpoints)
- **Realistic costs:** a slippage setting added to the fee on every view, and a **Cost stress test** (new `/cost-test` endpoint) that reruns a strategy at rising costs and finds the cost where the profit disappears
- **Settings map:** a grid of neighbouring settings scored on training and unseen data, with buy and hold shown for each period, a plain-language verdict and a warning when results swing with the market (new `/sensitivity` endpoint and dashboard panel)

### Changed

- Verdicts quote real counts and separate "lost money" from "lost less than holding" (protection, not profit)
- Strategy settings are read as whole numbers unless a setting declares `"type": "float"`
- Costs are now a fee plus slippage on every view (slippage defaults to 0, so earlier numbers still reproduce)

## 0.1.0 - 2026-10-11

First public release.

### Added

- **Data collection:** candles from exchanges via `ccxt`, or from Yahoo Finance as a fallback, saved to MySQL
- **Strategies:** moving average crossover, RSI mean reversion and breakout, in a registry that makes adding a new one a single function plus one list entry
- **Backtester** with trading fees and a one-candle delay on every trade, so a strategy never uses information it could not have had yet
- **Metrics:** total return, max drawdown, Sharpe, Sortino, win rate, number of trades, time in market, and a position size calculator
- **Unseen test period:** the newest part of the data is held back, with training and test results shown side by side
- **"Find best settings" optimizer:** picks the best setting on training data only, then reveals how it does on unseen data (an overfitting demo)
- **Walk-forward test:** repeats the train/test routine over several sliding windows and stitches the unseen windows into one result
- **FastAPI backend** with `/strategies`, `/backtest`, `/optimize`, `/walkforward` and `/position-size`
- **Web dashboard** with strategy controls, equity chart against buy and hold, plain-language verdicts, and a **Learn** tab with two small calculators
- **Optional C++ indicators** (`cpp/`) with an automatic pandas fallback
- **Terminal tools:** `engine/backtest.py` and `engine/report.py`
- **Tests** and a GitHub Actions workflow on Linux and Windows
- Contributing guide and MIT license

### Known limits

- Long-only, one asset, hourly candles assumed for Sharpe and Sortino
- Costs are a fee plus a flat slippage per trade (no order-size effects or delays)
- The API allows requests from any origin, which is fine for local use only
- The Docker setup has not been tested by the author

### Findings from the example data

On hourly BTC-USD data from November 2024 to October 2026, none of the three example strategies showed convincing out-of-sample profit. See the README for details.