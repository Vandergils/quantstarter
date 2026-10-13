# Getting started

A step-by-step walkthrough from an empty computer to your first result. It is written for **Windows with Laragon**, because that is the lightest way to get MySQL running. On macOS or Linux the steps are the same, apart from how you install MySQL and activate the virtual environment (see the notes).

Plan on 30 to 40 minutes the first time.

> **Educational use only.** Nothing here is financial advice, and a backtest does not predict the future.

## What you will have at the end

A dashboard in your browser where you pick a coin and a strategy, run it on past prices, and see how it did on data it was **not** set up on, next to simply buying and holding.

## 1. Install the tools

| Tool | Why | Notes |
|---|---|---|
| [Python 3.11 or newer](https://www.python.org/downloads/) | Runs everything | On the first installer screen, tick **Add python.exe to PATH**, then choose **Install Now** |
| [Git](https://git-scm.com/) | Downloads the code | |
| [Laragon](https://laragon.org) | Gives you MySQL with one click | Docker also works (see the README) |
| [VSCode](https://code.visualstudio.com/) | Optional editor | |

Close and reopen any terminal after installing, so it picks up the new settings. Check Python:

```powershell
python --version
python -m pip --version
```

Both should print a version number. If they do not, see the troubleshooting table below.

## 2. Get the code

```powershell
git clone https://github.com/Vandergils/quantstarter.git
cd quantstarter
```

Tip: if you put the folder inside Laragon's `www` directory (for example `C:\laragon\www\quantstarter`), you can later open the dashboard at `http://localhost/quantstarter/dashboard/`.

## 3. Start MySQL and create the table

1. Open Laragon and click **Start All**.
2. Open phpMyAdmin at `http://localhost/phpmyadmin`.
3. Go to the **SQL** tab, paste the contents of `db/schema.sql`, and click **Go**.

You should now see a database called `quantstarter` with a table called `candles`.

## 4. Tell the project how to reach the database

```powershell
copy collector\.env.example collector\.env
```

Laragon's defaults are already in the file (user `root`, empty password), so you do not need to edit it. The `.env` file is ignored by git, so a password you add later is never uploaded.

## 5. Create a virtual environment and install the packages

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Your prompt should start with `(.venv)`. Keep using this same terminal for the next steps. If you open a new one, activate the environment again.

## 6. Download some prices

Daily candles go back many years, so start there:

```powershell
python collector/collect_yahoo.py BTC-USD --timeframe 1d
```

You should see a line like `BTC-USD: downloaded 4000 candles, 4000 new, stored as BTC/USD (1d)`. Running it again later only adds new candles.

Optional extras:

```powershell
python collector/collect_yahoo.py ETH-USD SOL-USD --timeframe 1d   # more coins, for the cross-coin comparison
python collector/collect_yahoo.py BTC-USD                          # hourly candles (about the last two years)
```

## 7. A first look in the terminal

```powershell
python engine/backtest.py --timeframe 1d
python engine/report.py --timeframe 1d
```

The first prints every strategy with default settings next to buy and hold. The second splits the data into a training part and an unseen test part, which is the comparison that matters.

## 8. Start the API and open the dashboard

```powershell
python -m uvicorn api.main:app --reload
```

Leave that terminal running. Then open `dashboard/index.html` in your browser (or the Laragon address from step 2). Interactive API docs are at `http://127.0.0.1:8000/docs`.

## 9. Your first experiment

1. In the **Data** menu, choose `BTC/USD 1d`.
2. Pick a strategy and press **Run backtest**.
3. Read the **Unseen test** column first, then compare it with **Buy and hold**.
4. Press **Find best settings** and see whether the winner on the training data holds up on the unseen data.
5. Press **Run walk-forward test**, **Draw settings map**, **Compare across assets** and **Cost stress test**, one after another.
6. Switch **Direction** to **Long and short**, set a funding cost, and run it again.
7. Use **Download these results** (CSV or JSON) under any result to keep a run. The settings are saved in the file.

The **Learn** tab explains every term in plain language.

## 10. How to read what you see

- **Start with the unseen part.** Training results are the ones the settings were chosen on, so they flatter the strategy.
- **Compare with buy and hold.** If a strategy cannot beat holding, ask whether it at least fell much less.
- **Count the trades.** Every trade pays a cost. Hundreds of trades usually means costs dominate, and a handful means luck can explain it.
- **Check more than one view.** An idea worth a second look holds up on unseen data, across walk-forward windows, in a broad region of the settings map, at higher costs, and on other coins.
- **A good result is a reason to keep testing, never proof.**

## Troubleshooting

| What you see | What it means | Fix |
|---|---|---|
| `pip is not recognized` or `Python was not found` | Python is not installed, or not on PATH | Reinstall Python and tick **Add python.exe to PATH**. Then close and reopen the terminal. The `py` launcher (`py -m pip ...`) often works even when `python` does not |
| `python` opens the Microsoft Store | Windows has a placeholder for Python | Settings, Apps, Advanced app settings, App execution aliases, then turn off `python.exe` and `python3.exe` |
| `No module named ...` (for example `ccxt` or `pandas`) | The packages went into a different Python than the one running your script | Activate the virtual environment, and install with `python -m pip install -r requirements.txt`. In VSCode, press `Ctrl+Shift+P`, choose **Python: Select Interpreter**, and pick the one inside `.venv` |
| `running scripts is disabled` when activating | PowerShell blocks the activation script | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then activate again |
| `NetworkError` or `actively refused` from `collect.py` | Your network blocks that exchange | Use the Yahoo collector instead (step 6). `python collector/test_exchanges.py` shows which exchanges you can reach |
| `Can't connect to MySQL server` | MySQL is not running, or `.env` does not match | Click **Start All** in Laragon and check `collector/.env` |
| `Unknown database 'quantstarter'` | The schema has not been loaded | Run `db/schema.sql` again (step 3) |
| Dashboard says it **can't reach the API** | The API is not running | Start it with the `uvicorn` command in step 8 |
| The **Data** menu says "No data yet" | Nothing is in the database, or the API was started before you collected | Run the collector, restart the API, and refresh with `Ctrl+F5` |
| `Not enough candles in the database` | That series is too short for the chosen tool | Collect more, or pick a longer series (daily data is the longest) |
| `git push` is rejected (`fetch first`) | The remote has commits you do not have | Run `git pull --rebase`, then push again |

### Optional: faster indicators with C++

You do not need this. If you want it, `pacman` only exists inside the **MSYS2 UCRT64** terminal (not PowerShell). Open it and run `pacman -S mingw-w64-ucrt-x86_64-gcc`, then in your normal terminal run `python cpp/build.py`. Results are identical with or without it.

## macOS and Linux notes

- Install MySQL or MariaDB with your package manager (or use Docker, see the README), then load `db/schema.sql`.
- Copy the settings with `cp collector/.env.example collector/.env`.
- Activate the environment with `source .venv/bin/activate`.
- Everything else is the same.

## Where to go next

- The **Learn** tab in the dashboard, for the ideas behind each tool.
- [README.md](../README.md) for the full feature list and known limits.
- [CONTRIBUTING.md](../CONTRIBUTING.md) if you want to add a strategy of your own.