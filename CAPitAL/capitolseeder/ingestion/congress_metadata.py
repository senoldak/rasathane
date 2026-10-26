import json
from pathlib import Path
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from capitolseeder.db.models import Politician, CommitteeMembership
from capitolseeder.config import get_settings

settings = get_settings()

async def seed_congress_metadata(session: AsyncSession) -> int:
    """Seeds politician profiles and committee jurisdiction assignments."""
    seed_dir = settings.data_dir / "seed"
    with open(seed_dir / "politicians.json", "r", encoding="utf-8") as f:
        pol_data = json.load(f)
    with open(seed_dir / "committees.json", "r", encoding="utf-8") as f:
        comm_data = json.load(f)
        
    for p in pol_data:
        existing = await session.get(Politician, p["bioguide_id"])
        if not existing:
            session.add(Politician(**p))
        else:
            for k, v in p.items():
                setattr(existing, k, v)
    await session.flush()
    
    for c in comm_data:
        existing_cm = await session.execute(
            select(CommitteeMembership).where(
                CommitteeMembership.bioguide_id == c["bioguide_id"],
                CommitteeMembership.committee_code == c["committee_code"]
            )
        )
        if not existing_cm.scalar_one_or_none():
            session.add(CommitteeMembership(**c))
    await session.commit()
    return len(pol_data)

async def get_politician_jurisdiction_keywords(bioguide_id: str, session: AsyncSession) -> List[str]:
    """Retrieves all active committee jurisdiction keywords for a given politician."""
    stmt = select(CommitteeMembership).where(CommitteeMembership.bioguide_id == bioguide_id)
    res = await session.execute(stmt)
    memberships = res.scalars().all()
    keywords = set()
    for m in memberships:
        if isinstance(m.jurisdiction_keywords, list):
            keywords.update(kw.lower() for kw in m.jurisdiction_keywords)
    return list(keywords)
