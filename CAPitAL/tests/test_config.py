import pytest
from capitolseeder.config import Settings, get_settings

def test_settings_defaults():
    settings = get_settings()
    assert settings.app_name == "CAPitAL"
    assert "sqlite" in settings.database_url
    assert settings.stock_act_grace_days == 45
    assert settings.weight_conflict == 0.35
    assert settings.weight_cluster == 0.25
    assert settings.weight_winrate == 0.15
    assert settings.weight_size == 0.15
    assert settings.weight_asset == 0.10
