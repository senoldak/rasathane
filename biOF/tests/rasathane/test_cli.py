from datetime import date

import pytest

from bioseeder.rasathane import __main__ as cli


def test_arguman_ayristirma():
    a = cli.argumanlar(["sabah", "--kuru", "--tarih", "2026-10-23"])
    assert a.is_adi == "sabah" and a.kuru and a.tarih == date(2026, 10, 23)
    assert cli.argumanlar(["gun-ici"]).kuru is False


def test_bilinmeyen_is():
    with pytest.raises(SystemExit):
        cli.argumanlar(["yok"])


def test_gonderim_kapaliyken_kuru(monkeypatch, tmp_path):
    yakalanan = {}

    def sahte_calistir(is_adi, fn, b):
        yakalanan["kuru"] = b.kuru
        return 0

    monkeypatch.setattr(cli, "calistir", sahte_calistir)
    monkeypatch.delenv("RASATHANE_GONDERIM", raising=False)
    assert cli.main(["sabah"]) == 0
    assert yakalanan["kuru"] is True


def test_istanbul_tarihi():
    from datetime import datetime, timezone
    assert cli.istanbul_bugun(datetime(2026, 10, 23, 22, 30, tzinfo=timezone.utc)) == date(2026, 10, 24)
