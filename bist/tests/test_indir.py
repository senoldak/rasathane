from __future__ import annotations

from datetime import date

import pytest

from rasathane_bist.indir import BistErisimHatasi, dosya_al, pay_bulteni_url


def test_pay_bulteni_url() -> None:
    assert (
        pay_bulteni_url(date(2026, 10, 23))
        == "https://borsaistanbul.com/data/thb/2026/10/thb202610231.zip"
    )


def test_dosya_al_404_none() -> None:
    assert dosya_al(lambda u: (404, b""), "u", uyku=lambda s: None) is None


def test_dosya_al_200() -> None:
    assert dosya_al(lambda u: (200, b"x"), "u", uyku=lambda s: None) == b"x"


def test_dosya_al_kalici_hata() -> None:
    cagri: list[str] = []
    uykular: list[float] = []

    def ind(u: str) -> tuple[int, bytes]:
        cagri.append(u)
        return (503, b"")

    with pytest.raises(BistErisimHatasi, match="503"):
        dosya_al(ind, "u", deneme=3, uyku=uykular.append)
    assert len(cagri) == 3
    assert uykular == [5, 5]


def test_dosya_al_istisna_sonra_basari() -> None:
    yanitlar: list[Exception | tuple[int, bytes]] = [ConnectionError("kopma"), (200, b"ok")]
    it = iter(yanitlar)

    def ind(u: str) -> tuple[int, bytes]:
        y = next(it)
        if isinstance(y, Exception):
            raise y
        return y

    assert dosya_al(ind, "u", uyku=lambda s: None) == b"ok"
