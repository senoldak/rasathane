# tests/test_fetch.py
from opsi import fetch


def test_chain_filters_otm_and_dte(monkeypatch):
    import datetime

    fake_exp = (datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=20)).strftime(
        "%Y-%m-%d"
    )
    calls = {"n": 0}

    def fake_chain(sym, right="P"):
        calls["n"] += 1
        return [
            {
                "symbol": sym,
                "expiry": fake_exp,
                "strike": 20.0,
                "bid": 0.5,
                "ask": 0.53,
                "volume": 100,
                "openInterest": 500,
            },
            {
                "symbol": sym,
                "expiry": "2030-01-01",
                "strike": 20.0,
                "bid": 0.5,
                "ask": 0.53,
                "volume": 100,
                "openInterest": 500,
            },
        ]

    monkeypatch.setattr(fetch, "_raw_chain", fake_chain)
    out = fetch.get_put_chain("XYZ")
    assert calls["n"] == 1
    assert len(out) == 1
    assert out[0]["expiry"] == fake_exp
