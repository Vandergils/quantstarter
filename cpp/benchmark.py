import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine"))

import fast  # noqa: E402

N = 1_000_000
REPEAT = 5


def best_time(fn):
    best = float("inf")
    for _ in range(REPEAT):
        start = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - start)
    return best


def main():
    if not fast.using_cpp():
        print("C++ library not found. Build it first:  python cpp/build.py")
        return 1

    rng = np.random.default_rng(1)
    s = pd.Series(100 + np.cumsum(rng.normal(0, 1, N)))
    print(f"{N:,} prices, best of {REPEAT} runs\n")
    print(f"{'indicator':<22}{'pandas':>10}{'C++':>10}{'speed-up':>10}")

    cases = [
        ("SMA(50)", lambda: fast.py_sma(s, 50), lambda: fast.sma(s, 50)),
        ("RSI(14)", lambda: fast.py_rsi(s, 14), lambda: fast.rsi(s, 14)),
        ("Rolling max(100)", lambda: fast.py_rolling_max(s, 100), lambda: fast.rolling_max(s, 100)),
    ]
    for name, py_fn, cpp_fn in cases:
        t_py, t_cpp = best_time(py_fn), best_time(cpp_fn)
        print(f"{name:<22}{t_py * 1000:>8.1f}ms{t_cpp * 1000:>8.1f}ms{t_py / t_cpp:>9.1f}x")

    print("\nFor ~17,000 candles (your hourly data) both versions finish in a few milliseconds,")
    print("so the C++ version matters mostly for very large datasets or big parameter searches.")
    return 0


if __name__ == "__main__":
    sys.exit(main())