# Changelog

## 0.5.2 - 2026-10-16

Maintenance: fixes from an audit of v0.5.1, covering data collection, metrics, the C++ indicators, the asset comparison, and the README.

### Fixed

- **Collectors no longer store a candle that is still forming.** An unfinished candle used to be saved once and then kept forever with partial values. Candles already stored are now refreshed when you run a collector again, so re-running it repairs old data
- **Sortino ratio** now uses the standard downside deviation (losses over all candles). Earlier values could be far too high, so Sortino numbers will change
- **Win rate** now includes the fee on exit (and splits the cost of a long-to-short flip between the two trades), so trades that only looked profitable before fees on exit are no longer counted as wins
- **Docker:** MySQL is pinned to 8.4 and its port is only open to your own computer; `db/schema.sql` ends with a semicolon
- **C++ indicators** now treat a missing price like pandas does (a window with a gap gives NaN). Before, one missing price made the C++ moving average NaN for the rest of the series
- **Position size calculator** shows what the position is worth and the leverage it implies, and warns when a tight stop would need more than your balance
- **Asset comparison** now cuts every coin to the dates they all share, so the unseen part covers the same period for each, and reports the average correlation between the coins (`common_window=false` restores the old behaviour)
- **Dashboard** escapes ticker and exchange names before showing them
- **CI** reports whether the C++ indicators were loaded, runs the tests a second time on the pandas indicators, and uses read-only permissions
- Docs: the getting-started guide now lives in `docs/` where the README links to it; the pull request template is in `.github/`; the README explains where a trade is assumed to fill and lists the timeframes the collector provides. New known limits: constant-share leverage, free setting switches between walk-forward folds, and the simple-average RSI
- Docs: the README no longer says zero funding flatters shorts (funding can help or hurt), explains that the unseen period stops being unseen if you keep tuning against it, notes the limits of the Yahoo data, warns against exposing the API without authentication, and the Contributing ideas list no longer mentions strategies that already exist

## 0.5.1 - 2026-10-15

Maintenance: a safer install, more tests, and friendlier contributing.

### Added

- **API tests** (`tests/test_api.py`) that run without a database. They cover every endpoint, the new settings, and the error messages
- `requirements-dev.txt` (test and lint tools) and `pytest.ini`
- **Lint check** (`pyflakes`) in CI, which now installs the requirements exactly as a new user does and also runs on Python 3.14
- Issue templates (bug report with a place for the exported JSON, feature or strategy idea) and a pull request checklist
- `QUANTSTARTER_CORS_ORIGINS` to restrict which browser origins may call the API (everything is still allowed by default)

### Changed

- `requirements.txt` now has version ranges, so a fresh install does not jump to an untested major version
- Python 3.12 or newer is the documented requirement
- `/optimize` now reports the mode, size and fee it ran with, like the other endpoints

## 0.5.0 - 2026-10-14

See how size changes risk: fractions of the account, leverage, and what it costs.

### Added

- **Position size and leverage:** a size setting (0.1x to 5x) and a yearly borrowing cost for the part above 1x, on every view and endpoint (`size` and `borrow_cost` in the API, `--size` and `--borrow` in the terminal tools). Fees scale with the amount traded, and the account is wiped out when a move inside one candle equals the whole account. Results show an "account wiped out" row and warning, and exports carry the new settings

### Changed

- Short funding now scales with the position size
- Results at the default size of 1x are unchanged

## 0.4.0 - 2026-10-14

Keep your results, learn the tool faster, and two more strategies to test.

### Added

- **Two new strategies,** each with a long and a short side: **Momentum** (hold while the price is above where it was N candles ago) and **Trend, calm markets only** (a trend rule that stands aside when volatility is far above normal, with a decimal volatility-limit setting)
- **Export:** CSV and JSON download buttons on every result panel (backtest, optimizer, walk-forward, settings map, asset comparison, cost stress test). Files carry the settings that produced them, are created in the browser, and need no server changes
- **Beginner walkthrough** in `docs/GETTING_STARTED.md`, linked from the README

## 0.3.0 - 2026-10-13

Longer history and shorting: daily and 4-hour candles, and strategies that can profit from falling prices.

### Added

- **Long and short mode:** every strategy has a short side, selectable with a Direction setting (`mode=long_short` in the API) and a yearly short funding cost. A flip from long to short counts as two trades, and one candle cannot lose more than the whole account
- **Hourly, 4-hour and daily candles** (15m, 30m and 2h are also supported by the metrics). `collect_yahoo.py` takes `--timeframe 1h|4h|1d`, the dashboard Data menu lists every timeframe in the database, and `engine/backtest.py` and `engine/report.py` take `--symbol` and `--timeframe`

### Changed

- Win rate counts short trades, and "time in market" counts time long or short (a new "time short" figure is shown in long and short mode)
- Long-only results are unchanged
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

On hourly BTC-USD data from November 2024 to October 2026, none of the first three example strategies (moving average, RSI, breakout) showed convincing out-of-sample profit. See the README for details.