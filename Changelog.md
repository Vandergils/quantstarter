# Changelog

## Unreleased

### Added

- **Bollinger Bands** strategy (buy below the lower band, sell at the middle band)
- Strategy settings can now be decimals (`"type": "float"` in the registry)
- **Settings map:** a grid of neighbouring settings scored on training and unseen data, with a plain-language verdict (new `/sensitivity` endpoint and dashboard panel)

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
- Only the trading fee is modelled (no slippage)
- The API allows requests from any origin, which is fine for local use only
- The Docker setup has not been tested by the author

### Findings from the example data

On hourly BTC-USD data from November 2024 to October 2026, none of the three example strategies showed convincing out-of-sample profit. See the README for details.