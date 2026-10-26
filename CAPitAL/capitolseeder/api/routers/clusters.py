from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from capitolseeder.db.session import get_db
from capitolseeder.db.models import StockTrade, Politician
from capitolseeder.engine.cluster_detector import detect_clusters_from_trades
from capitolseeder.api.schemas import BipartisanClusterResponse

router = APIRouter(prefix="/bipartisan-clusters", tags=["Clusters"])

@router.get("", response_model=List[BipartisanClusterResponse])
async def get_bipartisan_clusters(
    window_days: int = Query(14, ge=1, le=60),
    min_parties: int = Query(2, ge=1, le=3),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(StockTrade)
        .where(StockTrade.transaction_type == "Purchase")
        .join(StockTrade.politician)
        .options(selectinload(StockTrade.politician))
    )
    res = await db.execute(stmt)
    trades = res.scalars().all()

    trades_list = []
    for t in trades:
        trades_list.append({
            "id": t.id,
            "ticker": t.ticker,
            "bioguide_id": t.bioguide_id,
            "party": t.politician.party if t.politician else "Unknown",
            "politician_name": f"{t.politician.first_name} {t.politician.last_name}" if t.politician else "",
            "transaction_date": t.transaction_date,
            "amount_range_str": t.amount_range_str,
            "owner_type": t.owner_type,
            "transaction_type": t.transaction_type
        })

    detected = detect_clusters_from_trades(trades_list, window_days=window_days)
    
    # Filter by min_parties
    filtered = []
    for c in detected:
        parties_count = (1 if c["democrat_count"] > 0 else 0) + (1 if c["republican_count"] > 0 else 0)
        if parties_count >= min_parties:
            filtered.append(c)

    return filtered
