# src/opsi/params.py
"""Scan math: tunable parameter set (filters/weights/academic/general).

All numbers are validated and clamped server-side; corrupt records fall back to defaults.
Weights are normalized at use time when they do not sum to 1 (0-100 scale preserved).
"""

import math
from typing import Any

DEFAULT_PARAMS: dict[str, dict[str, Any]] = {
    "filters": {
        "dte_min": 14,
        "dte_max": 45,
        "put_lo": -0.30,
        "put_hi": -0.10,
        "call_lo": 0.10,
        "call_hi": 0.30,
        "spread_max": 0.10,
        "vol_min": 10,
        "oi_min": 100,
        "capital_max": 2000.0,
        "csp_price_max": 25.0,
        "cc_capital_max": 5000.0,
        "width_max": 5.0,
        "pairs_max": 5,
        "earnings_days": 7,
        "spread_penalty": 10.0,
    },
    "weights": {
        "ret": 0.35,
        "otm": 0.25,
        "liq": 0.20,
        "iv": 0.10,
        "trend": 0.10,
        "ret_norm_hi": 0.6,
    },
    "academic": {
        "skew_hi": 0.6,
        "skew_lo": 0.4,
        "m_skew_hi": 0.94,
        "m_skew_lo": 1.05,
        "term_dte": 18,
        "m_term": 0.97,
        "jump_days": 14,
        "m_jump": 0.93,
        "clamp_lo": 0.8,
        "clamp_hi": 1.2,
    },
    "general": {
        "risk_free": 0.045,
        "stock_w": 0.4,
        "contract_w": 0.6,
    },
    "flags": {
        "skew": True,
        "term": True,
        "jump": True,
    },
}

# field -> (type, min, max)
_SPEC: dict[str, dict[str, tuple[str, float, float]]] = {
    "filters": {
        "dte_min": ("int", 0, 365),
        "dte_max": ("int", 0, 365),
        "put_lo": ("float", -1.0, 1.0),
        "put_hi": ("float", -1.0, 1.0),
        "call_lo": ("float", -1.0, 1.0),
        "call_hi": ("float", -1.0, 1.0),
        "spread_max": ("float", 0.01, 0.50),
        "vol_min": ("int", 0, 100000),
        "oi_min": ("int", 0, 1000000),
        "capital_max": ("float", 100.0, 100000.0),
        "csp_price_max": ("float", 1.0, 1000.0),
        "cc_capital_max": ("float", 100.0, 100000.0),
        "width_max": ("float", 0.5, 50.0),
        "pairs_max": ("int", 1, 50),
        "earnings_days": ("int", 0, 60),
        "spread_penalty": ("float", 0.0, 50.0),
    },
    "weights": {
        "ret": ("float", 0.0, 1.0),
        "otm": ("float", 0.0, 1.0),
        "liq": ("float", 0.0, 1.0),
        "iv": ("float", 0.0, 1.0),
        "trend": ("float", 0.0, 1.0),
        "ret_norm_hi": ("float", 0.05, 5.0),
    },
    "academic": {
        "skew_hi": ("float", 0.0, 5.0),
        "skew_lo": ("float", 0.0, 5.0),
        "m_skew_hi": ("float", 0.5, 1.5),
        "m_skew_lo": ("float", 0.5, 1.5),
        "term_dte": ("int", 0, 120),
        "m_term": ("float", 0.5, 1.5),
        "jump_days": ("int", 0, 60),
        "m_jump": ("float", 0.5, 1.5),
        "clamp_lo": ("float", 0.1, 1.0),
        "clamp_hi": ("float", 1.0, 2.0),
    },
    "general": {
        "risk_free": ("float", 0.0, 0.20),
        "stock_w": ("float", 0.0, 1.0),
        "contract_w": ("float", 0.0, 1.0),
    },
    "flags": {
        "skew": ("bool", 0, 1),
        "term": ("bool", 0, 1),
        "jump": ("bool", 0, 1),
    },
}

_PARAMS_KEY = "scan_params"


def _clean_value(kind: str, lo: float, hi: float, v: Any, fallback: Any) -> Any:
    try:
        if kind == "bool":
            if isinstance(v, bool):
                return v
            if isinstance(v, str):
                return v.strip().lower() in ("1", "true", "evet", "on")
            return bool(v)
        f = float(v)
        if math.isnan(f):  # NaN
            return fallback
        f = max(lo, min(hi, f))
        return round(f) if kind == "int" else f
    except (TypeError, ValueError):
        return fallback


def normalize_params(payload: Any) -> dict[str, dict[str, Any]]:
    """Merges user input with defaults and validates (drops unknown fields)."""
    out: dict[str, dict[str, Any]] = {s: dict(vals) for s, vals in DEFAULT_PARAMS.items()}
    if not isinstance(payload, dict):
        return out
    for section, spec in _SPEC.items():
        raw = payload.get(section)
        if not isinstance(raw, dict):
            continue
        for key, (kind, lo, hi) in spec.items():
            if key in raw:
                out[section][key] = _clean_value(kind, lo, hi, raw[key], out[section][key])
    f = out["filters"]
    if f["dte_min"] > f["dte_max"]:
        f["dte_min"], f["dte_max"] = f["dte_max"], f["dte_min"]
    if f["put_lo"] > f["put_hi"]:
        f["put_lo"], f["put_hi"] = f["put_hi"], f["put_lo"]
    if f["call_lo"] > f["call_hi"]:
        f["call_lo"], f["call_hi"] = f["call_hi"], f["call_lo"]
    a = out["academic"]
    if a["skew_lo"] > a["skew_hi"]:
        a["skew_lo"], a["skew_hi"] = a["skew_hi"], a["skew_lo"]
    if a["clamp_lo"] > a["clamp_hi"]:
        a["clamp_lo"], a["clamp_hi"] = a["clamp_hi"], a["clamp_lo"]
    return out


def norm_weights(params: dict[str, Any] | None) -> dict[str, float]:
    """Normalizes weights to sum to 1 (defaults when zero)."""
    w = (params or {}).get("weights", DEFAULT_PARAMS["weights"])
    vals = {
        k: max(0.0, float(w.get(k, DEFAULT_PARAMS["weights"][k])))
        for k in ("ret", "otm", "liq", "iv", "trend")
    }
    total = sum(vals.values())
    if total <= 0:
        return {k: DEFAULT_PARAMS["weights"][k] for k in vals}
    return {k: v / total for k, v in vals.items()}


def get_params(db: str) -> dict[str, dict[str, Any]]:
    """Active parameter set (defaults when missing/corrupt)."""
    import json
    import sqlite3

    try:
        con = sqlite3.connect(db)
        try:
            row = con.execute(
                "SELECT value FROM app_settings WHERE key=?", (_PARAMS_KEY,)
            ).fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        return normalize_params(None)
    if not row or not row[0]:
        return normalize_params(None)
    try:
        return normalize_params(json.loads(row[0]))
    except (ValueError, TypeError):
        return normalize_params(None)


def save_params(db: str, payload: Any) -> dict[str, dict[str, Any]]:
    """Saves the validated set and returns it."""
    import json
    import sqlite3

    clean = normalize_params(payload)
    con = sqlite3.connect(db)
    try:
        con.execute(
            "INSERT INTO app_settings(key, value) VALUES(?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (_PARAMS_KEY, json.dumps(clean)),
        )
        con.commit()
    finally:
        con.close()
    return clean
