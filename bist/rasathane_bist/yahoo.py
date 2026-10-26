"""Yahoo Finance kapanışları. yfinance tembel içe aktarılır; temel paket ona bağlı değildir."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date, timedelta
from typing import Any

GERI_GUN = 5


def _varsayilan_indir() -> Callable[..., Any]:
    import yfinance  # type: ignore[import-untyped]

    return yfinance.download  # type: ignore[no-any-return]


def _kapanis_tablosu(
    semboller: list[str], bas: date, bit: date, indir: Callable[..., Any] | None
) -> dict[str, list[tuple[date, float]]]:
    """Her sembol için (gün, kapanış) listesi, bit dahil. `indir` yfinance.download ile aynı
    çağrı biçimindedir: indir(semboller, start=, end=, auto_adjust=True, progress=False) ->
    "Close" sütunu olan DataFrame (tek sembolde düz, çoklu sembolde MultiIndex sütunlar)."""
    indirici = indir if indir is not None else _varsayilan_indir()
    df: Any = indirici(
        semboller,
        start=bas.isoformat(),
        end=(bit + timedelta(days=1)).isoformat(),  # yfinance'te bitiş hariçtir
        auto_adjust=True,
        progress=False,
    )
    sonuc: dict[str, list[tuple[date, float]]] = {}
    if df is None or len(df) == 0:
        return sonuc
    kapanis: Any = df["Close"]
    for sembol in semboller:
        if hasattr(kapanis, "columns"):
            if sembol not in kapanis.columns:
                continue
            seri: Any = kapanis[sembol]
        else:  # tek sembol, düz sütun
            seri = kapanis
        seri = seri.dropna()
        satirlar = [
            (idx.date(), float(deger)) for idx, deger in seri.items() if bas <= idx.date() <= bit
        ]
        if satirlar:
            sonuc[sembol] = sorted(satirlar)
    return sonuc


def kapanislar(
    semboller: Sequence[str], gun: date, indir: Callable[..., Any] | None = None
) -> dict[str, float]:
    """Her sembolün `gun` ya da öncesindeki son kapanışı (en çok 5 gün geri).
    Bulunamayan sembol sözlükte yer almaz."""
    liste = list(semboller)
    if not liste:
        return {}
    tablo = _kapanis_tablosu(liste, gun - timedelta(days=GERI_GUN), gun, indir)
    return {s: satirlar[-1][1] for s, satirlar in tablo.items()}


def kapanis_serisi(
    sembol: str, bitis: date, gun_sayisi: int = 92, indir: Callable[..., Any] | None = None
) -> list[tuple[date, float]]:
    """`bitis`e kadar, yaklaşık `gun_sayisi` takvim günü geriye (gün, kapanış) çiftleri."""
    tablo = _kapanis_tablosu([sembol], bitis - timedelta(days=gun_sayisi), bitis, indir)
    return tablo.get(sembol, [])
