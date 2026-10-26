"""Kanal Telegram gönderimi: requests.post taklit edilir."""

from dataclasses import dataclass, field
from typing import Any

import pytest
from rasathane_ortak.tek_gonderim import Giden, GonderimHatasi, GonderimKaydi

from opsi.kanal import telegram
from opsi.kanal.telegram import gonder, requests_istek, sahibe_yaz


@dataclass
class Cagri:
    url: str
    data: dict[str, Any]
    files: dict[str, Any] = field(default_factory=dict)


class _Yanit:
    def __init__(self, govde: dict[str, Any], durum: int = 200) -> None:
        self._g, self.status_code = govde, durum

    def json(self) -> dict[str, Any]:
        return self._g


class Kayitlar(list[Cagri]):
    """Yapılan çağrılar; yanitlar sırayla dönecek Telegram gövdeleri."""

    def __init__(self) -> None:
        super().__init__()
        self.yanitlar: list[dict[str, Any]] = []


@pytest.fixture
def cagri(monkeypatch: pytest.MonkeyPatch) -> Kayitlar:
    kayit = Kayitlar()
    yanitlar = kayit.yanitlar

    def post(url: str, data: Any = None, files: Any = None, timeout: Any = None) -> _Yanit:
        kayit.append(Cagri(url, dict(data or {}), dict(files or {})))
        return _Yanit(yanitlar.pop(0) if yanitlar else {"ok": True, "result": {"message_id": 3}})

    monkeypatch.setattr(telegram.requests, "post", post)
    return kayit


def _gidenler(n: int) -> list[Giden]:
    return [Giden(f"k{i}", 1, b"P%d" % i, f"OPsi · Kart {i} · 23.10.2026") for i in range(n)]


def test_her_kart_ayri_sendphoto(
    cagri: Kayitlar, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(telegram, "_ARA", 0)
    ids = gonder(
        "T", "@rasathane:12", "2026-10-23", _gidenler(3), GonderimKaydi(tmp_path / "k.csv")
    )
    assert ids == [3, 3, 3]
    assert [c.url.rsplit("/", 1)[1] for c in cagri] == ["sendPhoto"] * 3
    assert cagri[0].data == {
        "chat_id": "@rasathane",
        "message_thread_id": "12",
        "caption": "OPsi · Kart 0 · 23.10.2026",
    }


def test_ok_false_hata(cagri: Kayitlar, tmp_path: Any) -> None:
    cagri.yanitlar.append({"ok": False, "description": "Bad Request: TOPIC_CLOSED"})
    with pytest.raises(GonderimHatasi):
        gonder("T", "@x:1", "g", _gidenler(1), GonderimKaydi(tmp_path / "k.csv"))
    assert len(cagri) == 1


def test_okuma_zaman_asiminda_yeniden_gondermez(monkeypatch: pytest.MonkeyPatch) -> None:
    sayac: list[int] = []

    def yavas(*a: Any, **k: Any) -> Any:
        sayac.append(1)
        raise telegram.requests.ReadTimeout("yavaş")

    monkeypatch.setattr(telegram.requests, "post", yavas)
    with pytest.raises(telegram.requests.ReadTimeout):
        requests_istek("https://x/sendPhoto", {}, {})
    assert len(sayac) == 1


def test_baglanti_hatasinda_yeniden_dener(monkeypatch: pytest.MonkeyPatch) -> None:
    sayac: list[int] = []

    def kopuk(*a: Any, **k: Any) -> Any:
        sayac.append(1)
        if len(sayac) == 1:
            raise telegram.requests.ConnectionError("bağlantı yok")
        return _Yanit({"ok": True, "result": {"message_id": 1}})

    monkeypatch.setattr(telegram.requests, "post", kopuk)
    assert requests_istek("https://x/sendPhoto", {}, {}) == (
        200,
        {"ok": True, "result": {"message_id": 1}},
    )
    assert len(sayac) == 2


def test_sahibe_yaz_hatayi_yutar(monkeypatch: pytest.MonkeyPatch) -> None:
    def patla(*a: Any, **k: Any) -> Any:
        raise OSError("ağ yok")

    monkeypatch.setattr(telegram.requests, "post", patla)
    sahibe_yaz("T", "123", "hata")  # istisna fırlatmamalı
