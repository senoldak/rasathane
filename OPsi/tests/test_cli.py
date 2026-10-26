# tests/test_cli.py
from opsi.cli import main


def test_cli_nightly_mocked(monkeypatch, tmp_path, capsys):
    from opsi import cli

    db = str(tmp_path / "cli.db")
    monkeypatch.setattr(cli, "run_full_scan", lambda d, **kw: 7)
    assert main(["nightly", "--db", db]) == 0
    assert "scan_id: 7" in capsys.readouterr().out


def test_cli_requires_subcommand(capsys):
    import pytest

    with pytest.raises(SystemExit):
        main([])
