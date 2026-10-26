import httpx
import pytest

from bioseeder.rasathane.http import Istemci, KaynakHatasi


UA = "biOF Rasathane iletisim@ornek.com"


class SahteSaat:
    def __init__(self):
        self.t = 0.0
        self.uykular = []

    def saat(self):
        return self.t

    def uyku(self, s):
        self.uykular.append(s)
        self.t += s


def _istemci(yanitlar, **kw):
    istekler = []
    sira = list(yanitlar)

    def isle(req):
        istekler.append(req)
        return sira.pop(0) if len(sira) > 1 else sira[0]

    saat = SahteSaat()
    kw.setdefault("sec_ua", UA)
    ist = Istemci(transport=httpx.MockTransport(isle), uyku=saat.uyku, saat=saat.saat, **kw)
    return ist, istekler, saat


def test_basari_ve_baslik():
    ist, istekler, _ = _istemci([httpx.Response(200, text="ok")])
    assert ist.metin("https://www.sec.gov/x", sec=True) == "ok"
    assert istekler[0].headers["User-Agent"] == UA


def test_429_sonra_basari():
    ist, istekler, saat = _istemci([httpx.Response(429), httpx.Response(200, json={"a": 1})])
    assert ist.json("https://ornek/x") == {"a": 1}
    assert len(istekler) == 2
    assert any(u >= 1 for u in saat.uykular)


def test_404_hemen_hata():
    ist, istekler, _ = _istemci([httpx.Response(404)])
    with pytest.raises(KaynakHatasi) as e:
        ist.metin("https://ornek/yok")
    assert e.value.durum == 404
    assert len(istekler) == 1


def test_surekli_503_hata():
    ist, istekler, _ = _istemci([httpx.Response(503)], deneme=4)
    with pytest.raises(KaynakHatasi):
        ist.metin("https://ornek/x")
    assert len(istekler) == 5


def test_sec_esik_403_uzun_bekler():
    ist, _, saat = _istemci([httpx.Response(403, text="<title>SEC.gov | Request Rate Threshold Exceeded</title>"),
                             httpx.Response(200, text="ok")])
    assert ist.metin("https://www.sec.gov/x", sec=True) == "ok"
    assert max(saat.uykular) >= 60


def test_hiz_siniri():
    ist, _, saat = _istemci([httpx.Response(200, text="ok")], hz=5.0)
    for _ in range(3):
        ist.metin("https://ornek/x")
    assert sum(saat.uykular) >= 0.4 - 1e-9


def test_sec_iletisim_yoksa_hata():
    ist, istekler, _ = _istemci([httpx.Response(200, text="ok")], sec_ua=None)
    with pytest.raises(KaynakHatasi, match="SEC_ILETISIM"):
        ist.metin("https://www.sec.gov/x", sec=True)
    assert istekler == []
    assert ist.metin("https://clinicaltrials.gov/x") == "ok"
