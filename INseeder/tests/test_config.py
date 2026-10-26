import os
import pytest
from inseeder.config import Settings
from inseeder.api.app import create_app

def test_settings_defaults():
    settings = Settings()
    assert settings.DB_PATH == "inseeder.db"
    assert "INseeder" in settings.SEC_USER_AGENT
    assert settings.POLL_INTERVAL_SEC == 30.0
    assert settings.DEFAULT_BROKER == "paper"

def test_create_app_with_custom_db():
    custom_db = "test_custom_config.db"
    if os.path.exists(custom_db):
        os.remove(custom_db)

    app = create_app(db_path=custom_db, start_worker=False)
    assert app.state.db.db_path == custom_db
    assert app.state.broker.broker_name == "paper"

    if os.path.exists(custom_db):
        os.remove(custom_db)
