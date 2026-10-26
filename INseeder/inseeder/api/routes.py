import json
import asyncio
import logging
import httpx
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger("inseeder.api.routes")
router = APIRouter(prefix="/api")

class RuleCreate(BaseModel):
    name: str
    is_active: int = 1
    min_score: int = Field(default=60, ge=0, le=100)
    min_value: float = Field(default=50000.0, ge=0)
    allowed_roles: List[str] = ["CEO", "CFO", "Director"]
    allowed_types: List[str] = ["P"]
    auto_execute: int = 0
    broker_target: str = "paper"
    position_size_usd: float = Field(default=5000.0, gt=0)

class OrderExecute(BaseModel):
    symbol: str
    qty: float = Field(gt=0)
    side: str = "buy"
    price: Optional[float] = None
    signal_id: Optional[int] = None
    broker: str = "paper"

@router.get("/trades")
async def get_trades(request: Request, limit: int = 50, offset: int = 0, ticker: Optional[str] = None):
    db = request.app.state.db
    return await db.get_trades(limit=limit, offset=offset, ticker=ticker)

@router.get("/signals")
async def get_signals(request: Request, limit: int = 50, offset: int = 0):
    db = request.app.state.db
    return await db.get_signals(limit=limit, offset=offset)

@router.get("/hyperliquid/markets")
async def get_hyperliquid_markets(request: Request):
    """
    Fetches real-time Hyperliquid markets (perpetuals & spot) and cross-references
    them with detected SEC Form 4 insider trading activity.
    """
    db = request.app.state.db
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post("https://api.hyperliquid.xyz/info", json={"type": "metaAndAssetCtxs"})
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail="Failed to fetch Hyperliquid data")
            data = resp.json()
            universe = data[0].get("universe", [])
            contexts = data[1] if len(data) > 1 else []
            
            # Query ALL trades grouped by ticker from the database
            conn = await db.get_conn()
            cursor = await conn.execute("""
                SELECT ticker, COUNT(*) as trade_count, 
                       SUM(CASE WHEN transaction_code = 'P' THEN 1 ELSE 0 END) as buy_count,
                       SUM(CASE WHEN transaction_code = 'S' THEN 1 ELSE 0 END) as sell_count,
                       MAX(value) as max_val,
                       MAX(trade_date) as last_trade_date
                FROM trades 
                GROUP BY ticker
            """)
            trade_stats = {row["ticker"].upper(): dict(row) for row in await cursor.fetchall()}

            # Also fetch the actual trade records for overlapping assets
            overlapping_symbols = list(trade_stats.keys())
            matched_markets = []
            
            for i, u in enumerate(universe):
                sym = u.get("name", "").upper()
                if sym in trade_stats:
                    stats = trade_stats[sym]
                    # Fetch latest 3 trades for this symbol
                    t_cursor = await conn.execute(
                        "SELECT * FROM trades WHERE UPPER(ticker) = ? ORDER BY id DESC LIMIT 5",
                        (sym,)
                    )
                    recent_trades = [dict(r) for r in await t_cursor.fetchall()]

                    ctx = contexts[i] if i < len(contexts) else {}
                    mark_px = float(ctx.get("markPx", 0.0) or 0.0)
                    oracle_px = float(ctx.get("oraclePx", 0.0) or 0.0)
                    day_vol = float(ctx.get("dayNtlVlm", 0.0) or 0.0)
                    funding = float(ctx.get("funding", 0.0) or 0.0)
                    open_interest = float(ctx.get("openInterest", 0.0) or 0.0)

                    matched_markets.append({
                        "symbol": sym,
                        "company_name": recent_trades[0].get("company_name", "") if recent_trades else "",
                        "max_leverage": u.get("maxLeverage", 50),
                        "mark_price": mark_px,
                        "oracle_price": oracle_px,
                        "volume_24h": day_vol,
                        "funding_rate": funding,
                        "open_interest": open_interest,
                        "insider_trade_count": stats["trade_count"],
                        "insider_buy_count": stats["buy_count"],
                        "insider_sell_count": stats["sell_count"],
                        "max_trade_value": stats["max_val"],
                        "last_trade_date": stats["last_trade_date"],
                        "recent_trades": recent_trades
                    })

            # Sort markets by insider trade count and trade value
            matched_markets.sort(key=lambda m: (m["insider_trade_count"], m["max_trade_value"] or 0), reverse=True)

            return {
                "count": len(matched_markets),
                "total_universe_scanned": len(universe),
                "markets": matched_markets
            }
    except Exception as e:
        logger.error(f"Error querying Hyperliquid: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/rules")
async def get_rules(request: Request, active_only: bool = False):
    db = request.app.state.db
    return await db.get_rules(active_only=active_only)

@router.post("/rules", status_code=201)
async def create_rule(request: Request, rule: RuleCreate):
    db = request.app.state.db
    rule_dict = rule.model_dump()
    rule_dict["allowed_roles"] = json.dumps(rule.allowed_roles)
    rule_dict["allowed_types"] = json.dumps(rule.allowed_types)
    rule_id = await db.insert_rule(rule_dict)
    return {"id": rule_id, **rule_dict}

@router.delete("/rules/{rule_id}")
async def delete_rule(request: Request, rule_id: int):
    db = request.app.state.db
    deleted = await db.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"success": True, "id": rule_id}

@router.get("/portfolio")
async def get_portfolio(request: Request, broker: Optional[str] = None):
    brokers = getattr(request.app.state, "brokers", {})
    active_broker = brokers.get(broker.lower()) if broker else request.app.state.broker
    if not active_broker:
        active_broker = request.app.state.broker
    summary = await active_broker.get_account_summary()
    positions = await active_broker.get_positions()
    orders = await request.app.state.db.get_orders(limit=20)
    return {
        **summary,
        "positions": positions,
        "recent_orders": orders
    }

@router.post("/orders/execute")
async def execute_order(request: Request, order: OrderExecute):
    target_broker_name = (order.broker or "paper").lower()
    brokers = getattr(request.app.state, "brokers", {})
    broker = brokers.get(target_broker_name, request.app.state.broker)
    result = await broker.submit_order(
        symbol=order.symbol,
        qty=order.qty,
        side=order.side,
        price=order.price,
        signal_id=order.signal_id
    )
    return result

@router.get("/stream")
async def sse_stream(request: Request):
    worker = request.app.state.worker
    queue = await worker.subscribe()

    async def event_generator():
        try:
            # Send initial ping
            yield "data: {\"type\": \"connected\"}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(msg)}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat ping
                    yield "data: {\"type\": \"ping\"}\n\n"
        finally:
            await worker.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
