# src/opsi/fetch.py
"""Yahoo (yfinance) data fetch: throttled, fault-tolerant, DTE-filtered."""

import datetime
import math
import threading
import time
from typing import Any

import pandas as pd
import yfinance as yf

from . import config
from .types import RawContract

_lock = threading.Lock()
_last: list[float] = [0.0]


def _to_float(v: object) -> float:
    """Coerces NaN/None/bad numbers to 0.0."""
    if not isinstance(v, (int, float, str)) or isinstance(v, bool):
        return 0.0
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if math.isnan(f) else f


def _to_int(v: object) -> int:
    return int(_to_float(v))


def _throttle() -> None:
    with _lock:
        now = time.time()
        wait = config.MIN_REQUEST_GAP_SEC - (now - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()


def get_sp500_symbols() -> list[str]:
    """Reads S&P 500 symbol list from CSV."""
    _throttle()
    df = pd.read_csv(config.SP500_URL)
    col = "Symbol" if "Symbol" in df.columns else df.columns[0]
    return sorted(set(df[col].astype(str).str.strip()))


def is_etf(symbol: str) -> bool:
    """Checks whether a symbol is a major ETF."""
    return symbol.upper() in set(config.MAJOR_ETFS)


def get_symbols(universe: str = "all") -> list[str]:
    """Returns symbols to scan for the requested universe ('all', 'stocks', 'etfs')."""
    u = (universe or "all").lower()
    if u == "etfs":
        return sorted(config.MAJOR_ETFS)
    if u in config.UNIVERSES:
        return get_universe_symbols(u)
    stocks = get_sp500_symbols()
    if u == "stocks":
        return stocks
    return sorted(set(stocks + config.MAJOR_ETFS))


def _universe_cache_dir(cache_dir: str | None = None) -> object:
    import pathlib

    d = pathlib.Path(cache_dir or config.UNIVERSE_CACHE_DIR)
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return d


def _read_json(path: object) -> dict[str, Any] | None:
    import json

    try:
        with open(str(path), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _write_json(path: object, payload: dict[str, Any]) -> None:
    import json

    try:
        with open(str(path), "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except OSError:
        pass  # scan proceeds even if cache write fails


def _cache_fresh(fetched_at: str | None, ttl_days: int) -> bool:
    if not fetched_at:
        return False
    try:
        ts = datetime.datetime.fromisoformat(fetched_at)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=datetime.UTC)
        age = datetime.datetime.now(datetime.UTC) - ts
        return age <= datetime.timedelta(days=ttl_days)
    except ValueError:
        return False


def get_universe_symbols(uid: str, cache_dir: str | None = None) -> list[str]:
    """Returns cached symbols of a preset index universe (cache-friendly, rate-limit aware).

    Order: fresh cache -> live source -> stale cache -> embedded fallback.
    Never fabricates symbols on network errors; worst case returns the embedded
    real list or an empty list. Unknown universe raises KeyError.
    """
    key = (uid or "").lower()
    if key not in config.UNIVERSES:
        raise KeyError(f"bilinmeyen evren: {uid}")
    meta = config.UNIVERSES[key]
    d = _universe_cache_dir(cache_dir)
    import pathlib

    cache_file = pathlib.Path(str(d)) / f"{key}.json"
    cached = _read_json(cache_file)
    cached_syms = [s for s in (cached or {}).get("symbols", []) if isinstance(s, str) and s.strip()]

    def _remember(syms: list[str]) -> list[str]:
        clean = sorted({s.strip().upper() for s in syms if s.strip()})
        _write_json(
            cache_file,
            {"symbols": clean, "fetched_at": datetime.datetime.now(datetime.UTC).isoformat()},
        )
        return clean

    if meta.get("kind") == "static":
        syms = list(meta.get("symbols", []))
        return _remember(syms) if syms else cached_syms

    # kind == "url" (e.g. sp500): fresh cache first — no CSV fetch on every scan
    if cached and _cache_fresh(cached.get("fetched_at"), config.UNIVERSE_TTL_DAYS) and cached_syms:
        return sorted({s.strip().upper() for s in cached_syms if s.strip()})
    live: list[str] = []
    try:
        _throttle()
        url = getattr(config, meta.get("url_key", ""), "")
        df = pd.read_csv(url)
        col = "Symbol" if "Symbol" in df.columns else df.columns[0]
        live = sorted(set(df[col].astype(str).str.strip()))
    except Exception:
        live = []  # fall back to cache/fallback when live source is unavailable
    if live:
        return _remember(live)
    if cached_syms:
        return sorted({s.strip().upper() for s in cached_syms if s.strip()})
    return sorted({s.strip().upper() for s in meta.get("fallback", []) if s.strip()})


def universe_info(uid: str, cache_dir: str | None = None) -> dict[str, Any]:
    """Returns universe card info without network access (count from cache/fallback)."""
    key = (uid or "").lower()
    meta = config.UNIVERSES[key]
    import pathlib

    d = _universe_cache_dir(cache_dir)
    data = _read_json(pathlib.Path(str(d)) / f"{key}.json") or {}
    syms = [s for s in data.get("symbols", []) if isinstance(s, str) and s.strip()]
    if syms:
        count: int | None = len({s.strip().upper() for s in syms})
        cached_at = data.get("fetched_at")
    elif meta.get("kind") == "static":
        count = len({s.strip().upper() for s in meta.get("symbols", [])})
        cached_at = None
    else:
        count = None
        cached_at = None
    return {
        "id": key,
        "title": meta.get("title", key),
        "desc": meta.get("desc", ""),
        "currency": meta.get("currency", "USD"),
        "count": count,
        "cached_at": cached_at,
    }


_FX_MEM: dict[str, tuple[str, float]] = {}


def get_fx_to_usd(ccy: str, cache_dir: str | None = None) -> float | None:
    """1 USD = ? ccy (e.g. TRY). Daily cached; None on error (no fake rates)."""
    ccy = (ccy or "USD").upper()
    if ccy == "USD":
        return 1.0
    pair = config.FX_PAIRS.get(ccy)
    if not pair:
        return None
    import pathlib

    d = _universe_cache_dir(cache_dir)
    fx_file = pathlib.Path(str(d)) / f"fx_{ccy}.json"
    mem = _FX_MEM.get(f"{d}|{ccy}")
    if mem and _cache_fresh(mem[0], config.FX_TTL_DAYS):
        return mem[1]
    data = _read_json(fx_file) or {}
    if _cache_fresh(data.get("fetched_at"), config.FX_TTL_DAYS) and isinstance(
        data.get("rate"), (int, float)
    ):
        _FX_MEM[f"{d}|{ccy}"] = (data["fetched_at"], float(data["rate"]))
        return float(data["rate"])
    try:
        _throttle()
        h = yf.Ticker(pair).history(period="1d")
        if h.empty:
            return None
        rate = float(h["Close"].iloc[-1])
        if rate <= 0:
            return None
        stamp = datetime.datetime.now(datetime.UTC).isoformat()
        _write_json(fx_file, {"rate": rate, "fetched_at": stamp})
        _FX_MEM[f"{d}|{ccy}"] = (stamp, rate)
        return rate
    except Exception:
        return None


def price_in_usd(symbol: str, price: float | None, cache_dir: str | None = None) -> float | None:
    """Converts price to USD for threshold checks (.IS via TRY rate)."""
    if price is None:
        return None
    sym = (symbol or "").upper()
    if sym.endswith(".IS"):
        rate = get_fx_to_usd("TRY", cache_dir=cache_dir)
        if rate:
            return price / rate
    return price


def get_price(symbol: str) -> float | None:
    """Returns latest close price; None when unavailable."""
    _throttle()
    try:
        t = yf.Ticker(symbol)
        h = t.history(period="1d")
        if h.empty:
            return None
        return float(h["Close"].iloc[-1])
    except Exception:
        return None


def _raw_chain(symbol: str, right: str = "P") -> list[RawContract]:
    """Fetches raw contracts across the first 12 expiries (right=P put, C call)."""
    _throttle()
    t = yf.Ticker(symbol)
    out: list[RawContract] = []
    for exp in (t.options or [])[:12]:
        try:
            chain = t.option_chain(exp)
            legs = chain.calls if right == "C" else chain.puts
            for _, r in legs.iterrows():
                lp = _to_float(r.get("lastPrice", 0))
                out.append(
                    {
                        "symbol": symbol,
                        "expiry": exp,
                        "strike": float(r["strike"]),
                        "bid": _to_float(r.get("bid", 0)),
                        "ask": _to_float(r.get("ask", 0)),
                        "lastPrice": lp,
                        "volume": _to_int(r.get("volume", 0)),
                        "openInterest": _to_int(r.get("openInterest", 0)),
                    }
                )
        except Exception:
            continue
    return out


def get_chain(
    symbol: str, right: str = "P", max_dte_min: int = 14, max_dte_max: int = 45
) -> list[RawContract]:
    """Returns contracts in the DTE range; skips malformed expiries."""
    today = datetime.datetime.now(datetime.UTC).date()
    res: list[RawContract] = []
    for c in _raw_chain(symbol, right):
        try:
            exp = datetime.date.fromisoformat(c["expiry"])
        except ValueError:
            continue
        dte = (exp - today).days
        if max_dte_min <= dte <= max_dte_max:
            res.append(c)
    return res


def get_put_chain(symbol: str, max_dte_min: int = 14, max_dte_max: int = 45) -> list[RawContract]:
    """Backward compat: put chain."""
    return get_chain(symbol, "P", max_dte_min, max_dte_max)


def get_history(symbol: str, period: str = "1y") -> list[tuple[str, float]]:
    """Daily close series [(date_iso, close)]; empty list when unavailable."""
    _throttle()
    try:
        t = yf.Ticker(symbol)
        h = t.history(period=period, auto_adjust=True)
        if h.empty:
            return []
        return [(idx.date().isoformat(), float(row["Close"])) for idx, row in h.iterrows()]
    except Exception:
        return []


def get_earnings_days(symbol: str) -> int | None:
    """Days to next earnings; None when no calendar."""
    import datetime

    _throttle()
    try:
        cal = yf.Ticker(symbol).calendar
        if isinstance(cal, dict):  # yfinance 1.x
            liste = list(cal.get("Earnings Date") or [])
            if not liste:
                return None
            first = pd.Timestamp(liste[0]).date()
        else:
            if cal is None or getattr(cal, "empty", True):
                return None
            dates = cal["Earnings Date"] if "Earnings Date" in cal.columns else None
            if dates is None or len(dates) == 0:
                return None
            first = pd.Timestamp(dates.iloc[0]).date()
        return int((first - datetime.datetime.now(datetime.UTC).date()).days)
    except Exception:
        return None


def atm_put_sample(price: float, chains: list[RawContract]) -> dict[str, float]:
    """Liquidity pulse from nearest-expiry ATM put (pure function, no I/O)."""
    if not chains:
        return {"iv": 0.0, "volume": 0.0, "oi": 0.0, "spread": 0.0, "stale": 1.0}
    nearest = min(chains, key=lambda c: c["expiry"])
    same_exp = [c for c in chains if c["expiry"] == nearest["expiry"]]
    atm = min(same_exp, key=lambda c: abs(c["strike"] - price))
    bid, ask = float(atm["bid"]), float(atm["ask"])
    mid = 0.5 * (bid + ask)
    spread = ((ask - bid) / mid) if mid > 0 else 0.0
    stale = 1.0 if (bid <= 0 and ask <= 0) else 0.0
    return {
        "iv": 0.0,
        "volume": float(atm["volume"]),
        "oi": float(atm["openInterest"]),
        "spread": spread,
        "stale": stale,
    }


def get_atm_put_sample(symbol: str, price: float) -> dict[str, float]:
    """Liquidity pulse from nearest-expiry ATM put; zeros when no chain."""
    chains = get_chain(symbol, "P", max_dte_min=1, max_dte_max=400)
    return atm_put_sample(price, chains)
