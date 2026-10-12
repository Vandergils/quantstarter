# Changelog

## Unreleased

### Added

- **Hourly, 4-hour and daily candles** (15m, 30m and 2h are also supported by the metrics). `collect_yahoo.py` takes `--timeframe 1h|4h|1d`, the dashboard Data menu lists every timeframe in the database, and `engine/backtest.py` and `engine/report.py` take `--symbol` and `--timeframe`

### Changed

- Sharpe and Sortino are annualised with the right number of candles per year for the chosen timeframe (`periods_per_year`), instead of assuming hourly candles
- Minimum data rules for the walk-forward test, settings map, cost test and asset comparison are lower for slower timeframes (for example daily data needs 60-candle test windows, not 300)

## 0.2.0 - 2026-10-12

More ways to doubt a result: other coins, realistic costs, and a map of neighbouring settings.

### Added

- **Several coins:** `collect_yahoo.py` accepts several tickers, the dashboard has a **Data** menu, and **Compare across assets** runs one strategy, with the same settings, on every coin in the database (new `/datasets` and `/compare` endpoints)
- **Realistic costs:** a slippage setting added to the fee on every view, and a **Cost stress test** (new `/cost-test` endpoint) that reruns a strategy at rising costs and finds the cost where the profit disappears
- **Settings map:** a grid of neighbouring settings scored on training and unseen data, with buy and hold shown for each period, a plain-language verdict and a warning when results swing with the market (new `/sensitivity` endpoint and dashboard panel)

### Changed

- Verdicts say "lost less than holding" when both the strategy and holding lost money, and the cross-asset verdict separates protection from profit
- Costs are now a fee plus slippage on every view (slippage defaults to 0, so earlier numbers still reproduce)

## 0.1.0 - 2026-10-11

First public release.

### Added

- **Data collection:** candles from exchanges via `ccxt`, or from Yahoo Finance as a fallback, saved to MySQL
- **Strategies:** moving average crossover, RSI mean reversion, breakout and Bollinger Bands, in a registry that makes adding a new one a single function plus one list entry. Settings are whole numbers by default, or decimals with `"type": "float"`
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

<<<<<<< HEAD
On hourly BTC-USD data from November 2024 to October 2026, none of the first three example strategies (moving average, RSI, breakout) showed convincing out-of-sample profit. See the README for details.
=======
On hourly BTC-USD data from November 2024 to October 2026, none of the first three example strategies (moving average, RSI, breakout) showed convincing out-of-sample profit. See the README for details.
>>>>>>> 745ae04 (Add timeframe-aware metrics and daily/4-hour data support)
