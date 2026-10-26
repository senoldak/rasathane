import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from capitolseeder.db.session import get_db
from capitolseeder.engine.portfolio_simulator import simulate_shadow_portfolio_db
from capitolseeder.api.schemas import SimulationResponse

router = APIRouter(prefix="/simulate", tags=["Simulator"])

@router.get("/shadow-portfolio", response_model=SimulationResponse)
async def simulate_portfolio(
    bioguide_id: Optional[str] = Query(None),
    start_date: Optional[datetime.date] = Query(None),
    initial_capital: float = Query(100000.0, ge=1000.0),
    holding_days: int = Query(90, ge=30, le=365),
    db: AsyncSession = Depends(get_db)
):
    result = await simulate_shadow_portfolio_db(
        session=db,
        bioguide_id=bioguide_id,
        start_date=start_date,
        initial_capital=initial_capital,
        holding_days=holding_days
    )
    return result
