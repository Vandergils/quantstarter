from backtest import load_candles, sma_crossover
from metrics import summary

data = load_candles()
rows = []
for fast, slow in [(10, 30), (20, 50), (50, 100), (50, 200), (100, 300)]:
    result, n = sma_crossover(data, fast=fast, slow=slow)
    s = summary(result)
    rows.append((fast, slow, n, s["total_return"], s["max_drawdown"], s["sharpe"]))

print(f"{'fast':>5} {'slow':>5} {'trades':>7} {'return':>9} {'maxDD':>9} {'sharpe':>7}")
for r in rows:
    print(f"{r[0]:>5} {r[1]:>5} {r[2]:>7} {r[3]:>9.2%} {r[4]:>9.2%} {r[5]:>7.2f}")