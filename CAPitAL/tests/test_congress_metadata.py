import pytest
from sqlalchemy import select
from capitolseeder.db.session import init_db, async_session_maker
from capitolseeder.db.models import Politician, CommitteeMembership
from capitolseeder.ingestion.congress_metadata import seed_congress_metadata, get_politician_jurisdiction_keywords

@pytest.mark.asyncio
async def test_seed_congress_metadata():
    await init_db()
    async with async_session_maker() as session:
        count = await seed_congress_metadata(session)
        assert count >= 5
        
        keywords = await get_politician_jurisdiction_keywords("P000197", session)
        assert len(keywords) > 0
        assert "semiconductors" in keywords or "technology" in keywords
