from pathlib import Path

KOK = Path(__file__).resolve().parents[2]
# İş akışları depo kökünde (rasathane/.github/workflows).
IS_AKISI = KOK.parent / ".github" / "workflows" / "inseeder.yml"


def test_workflow_contents():
    yml = IS_AKISI.read_text(encoding="utf-8")
    for parca in ('"0 4 * * 2-6"', "workflow_dispatch", "python -m inseeder.kanal",
                  "contents: write", "vars.INSEEDER_TELEGRAM_HEDEF", "secrets.SEC_USER_AGENT",
                  "secrets.TELEGRAM_BOT_TOKEN", "secrets.TELEGRAM_SAHIP_ID",
                  "actions/upload-artifact@v5", "kanal_veri", "timeout-minutes: 360",
                  "ref: ${{ github.event.repository.default_branch }}",
                  "working-directory: INseeder", "group: inseeder"):
        assert parca in yml, parca


def test_records_step_runs_even_on_failure():
    yml = IS_AKISI.read_text(encoding="utf-8")
    adim = yml.split("- name: Kayıtları depoya yaz", 1)[1].split("run:", 1)[0]
    assert "always()" in adim
    assert "inputs.kuru" in adim


def test_readme_turkish_setup():
    readme = (KOK / "README.md").read_text(encoding="utf-8")
    assert "## Rasathane Telegram kanalı" in readme
    assert "TELEGRAM_HEDEF=@rasathane:" in readme
    assert "Read and write" in readme
    assert "Yatırım tavsiyesi değildir" in readme


def test_env_example_has_channel_vars():
    env = (KOK / ".env.example").read_text(encoding="utf-8")
    assert "TELEGRAM_HEDEF=" in env
    assert "TELEGRAM_SAHIP_ID=" in env
