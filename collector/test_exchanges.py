import ccxt

for name in ["bybit", "okx", "kucoin", "kraken", "gateio"]:
    try:
        ex = getattr(ccxt, name)({"enableRateLimit": True, "timeout": 10000})
        c = ex.fetch_ohlcv("BTC/USDT", "1h", limit=5)
        print(f"{name}: OK ({len(c)} candles)")
    except Exception as e:
        print(f"{name}: FAILED - {type(e).__name__}")