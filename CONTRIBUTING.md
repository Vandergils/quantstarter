# Contributing to QuantStarter

Thanks for helping! This project is meant to be a friendly place to learn quant trading, so small, readable contributions are very welcome. First-time contributors too.

## Quick setup

```bash
git clone https://github.com/Vandergils/quantstarter.git
cd quantstarter
python -m venv .venv
.venv\Scripts\activate            # Windows   (macOS/Linux: source .venv/bin/activate)
python -m pip install -r requirements-dev.txt
python -m pytest
python -m pyflakes api engine collector cpp tests
```

The tests need no database and no internet. You only need MySQL and a data collector if you want to run the API and dashboard (see the README).

## Ways to contribute

- Add a strategy (the most fun one, see below)
- Improve the dashboard wording so beginners understand it better
- Add tests, fix bugs, improve the docs
- More data sources or assets
- Faster indicators in `cpp/` (always keep the pandas version in `engine/fast.py` as the reference)

## Adding a strategy

All strategies live in `engine/strategies.py`. A strategy answers one question for every candle: hold the coin (`1`) or stay in cash (`0`).

**1. Write a signal function** that returns a 0/1 pandas Series:

```python
def sig_momentum(df, lookback=72):
    """Hold while the price is higher than it was `lookback` candles ago."""
    return (df["close"] > df["close"].shift(lookback)).astype(int)
```

**2. Register it** in the `STRATEGIES` dictionary:

```python
"momentum": {
    "label": "Momentum",
    "description": "Hold while the price is above where it was N candles ago.",
    "func": sig_momentum,
    "params": [
        {"name": "lookback", "label": "Lookback (candles)", "min": 10, "max": 500,
         "step": 1, "default": 72, "hint": "How far back to compare."},
    ],
    "grid": {"lookback": [24, 48, 72, 168, 336]},   # settings tried by "Find best settings"
    "validate": lambda p: None,                      # return a message if settings are invalid
},
```

The API and the dashboard pick it up automatically. No other file needs to change. `grid` must contain every parameter, and the default settings must pass `validate`. The tests check both.

### Rules every strategy must follow

- **No look-ahead.** The shared simulation already delays the signal by one candle (`signal.shift(1)`), so use only data up to the current candle. Never use `.shift(-1)` or any future value.
- **Whole numbers by default.** Settings are read as integers. For a decimal setting, add `"type": "float"` to that parameter (see `width` in the Bollinger Bands entry).
- **Fees are applied for you.** Do not subtract fees inside a strategy.
- **Short side (optional).** To let your strategy run in long and short mode, add `short_xxx(df, **params)` returning 1 while it wants to be short, and list it as `"short_func"` in the registry entry. Use the mirror image of your long rules, and return 0 (not 1) while an indicator is still warming up, so the strategy is never short before it has any data. Without it, the dashboard disables the option for your strategy.
- **Keep it simple.** Few parameters, clear docstring. Beginners will read your code.

## Tests

```bash
python -m pytest tests
```

Please add a test for new behaviour. Tests that need the optional C++ library are skipped automatically when it is not built. To build it (needs g++): `python cpp/build.py`.

## Pull requests

1. Fork the repo and create a branch (`git checkout -b add-momentum-strategy`).
2. Keep each pull request focused on one change.
3. Make sure `python -m pytest` passes and `python -m pyflakes api engine collector cpp tests` is clean. GitHub runs both automatically on Linux and Windows. The pull request template has a short checklist.
4. Describe what you changed and why. For a new strategy, include a short note on the idea behind it.

## Please do not commit

- Passwords, API keys or `.env` files
- Compiled files (`.dll`, `.so`, `.dylib`) or the `.venv` folder
- Price data dumps

## A note on trading claims

This is an educational project. Please do not add wording that promises profit or presents a backtest result as a recommendation. Backtests are simulations on past data and do not predict the future.