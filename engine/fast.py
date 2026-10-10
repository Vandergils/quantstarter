import ctypes
import os
import sys

import numpy as np
import pandas as pd
from numpy.ctypeslib import ndpointer

_CPP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cpp")
_LIB_NAME = {"win32": "indicators.dll", "darwin": "libindicators.dylib"}.get(sys.platform, "libindicators.so")


def _load():
    if os.environ.get("QUANTSTARTER_NO_CPP") == "1":  # force the pandas versions
        return None
    path = os.path.abspath(os.path.join(_CPP_DIR, _LIB_NAME))
    if not os.path.exists(path):
        return None
    try:
        lib = ctypes.CDLL(path)
        arg_in = ndpointer(np.float64, flags="C_CONTIGUOUS")
        arg_out = ndpointer(np.float64, flags="C_CONTIGUOUS,WRITEABLE")
        for name in ("sma", "rsi", "rolling_max", "rolling_min"):
            fn = getattr(lib, name)
            fn.argtypes = [arg_in, ctypes.c_int, ctypes.c_int, arg_out]
            fn.restype = None
        return lib
    except (OSError, AttributeError):
        return None


_LIB = _load()


def using_cpp() -> bool:
    return _LIB is not None


# ---------- pandas versions (also used as the reference in tests) ----------

def py_sma(s: pd.Series, window: int) -> pd.Series:
    return s.rolling(window).mean()


def py_rsi(s: pd.Series, period: int) -> pd.Series:
    delta = s.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    return 100 - 100 / (1 + gain / loss)


def py_rolling_max(s: pd.Series, window: int) -> pd.Series:
    return s.rolling(window).max()


def py_rolling_min(s: pd.Series, window: int) -> pd.Series:
    return s.rolling(window).min()


# ---------- public functions ----------

def _call(name: str, s: pd.Series, param: int) -> pd.Series:
    x = np.ascontiguousarray(s.to_numpy(dtype=np.float64))
    out = np.empty_like(x)
    getattr(_LIB, name)(x, len(x), int(param), out)
    return pd.Series(out, index=s.index)


def sma(s: pd.Series, window: int) -> pd.Series:
    return _call("sma", s, window) if _LIB else py_sma(s, window)


def rsi(s: pd.Series, period: int) -> pd.Series:
    return _call("rsi", s, period) if _LIB else py_rsi(s, period)


def rolling_max(s: pd.Series, window: int) -> pd.Series:
    return _call("rolling_max", s, window) if _LIB else py_rolling_max(s, window)


def rolling_min(s: pd.Series, window: int) -> pd.Series:
    return _call("rolling_min", s, window) if _LIB else py_rolling_min(s, window)