import pytest
import sqlite3
from sqlalchemy import text
from bioseeder.config import get_settings
from bioseeder.database import set_sqlite_pragma
from tests.conftest import test_engine, TestingSessionLocal

@pytest.mark.asyncio
async def test_database_connection():
    settings = get_settings()
    assert settings.DATABASE_URL is not None
    async with test_engine.begin() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1

@pytest.mark.asyncio
async def test_session_generator():
    async with TestingSessionLocal() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1

def test_sqlite_pragma_configuration():
    conn = sqlite3.connect(":memory:")
    try:
        set_sqlite_pragma(conn, None)
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys")
        assert cur.fetchone()[0] == 1
    finally:
        conn.close()

