import asyncio
import datetime
import logging
import re
from typing import Optional, Dict, Any, List
import httpx
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from capitolseeder.config import get_settings
from capitolseeder.db.session import async_session_maker
from capitolseeder.db.models import (
    Politician,
    CommitteeMembership,
    TransactionReport,
    StockTrade,
    CapitolAlphaScore,
    FederalContractMatch
)
from capitolseeder.ingestion.ocr_engine import parse_amount_bracket, calculate_stock_act_lag
from capitolseeder.engine.scoring_engine import score_trade
from capitolseeder.engine.cluster_detector import detect_clusters_from_trades
from capitolseeder.ingestion.contract_matcher import match_federal_contracts_for_ticker

logger = logging.getLogger("capitolseeder.live_feed")

KADOA_FEED_URL = "https://raw.githubusercontent.com/kadoa-org/congress-trading-monitor/main/public/data/trades.json"

def parse_iso_date(d_val: Any) -> datetime.date:
    if isinstance(d_val, datetime.date):
        return d_val
    if isinstance(d_val, str):
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
            try:
                return datetime.datetime.strptime(d_val.strip(), fmt).date()
            except ValueError:
                continue
    return datetime.date.today()

def normalize_asset_type(asset_code: Optional[str]) -> str:
    if not asset_code:
        return "Stock"
    code = asset_code.upper().strip()
    if code in {"OP", "CALL", "CALL_OPTION"}:
        return "Call_Option"
    elif code in {"PUT", "PUT_OPTION"}:
        return "Put_Option"
    elif code in {"BD", "BOND", "GS", "NOTE"}:
        return "Bond"
    return "Stock"

async def fetch_remote_feed(limit: int = 150) -> List[Dict[str, Any]]:
    """
    Fetches real-time congressional trade disclosures from public live stream.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(KADOA_FEED_URL)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return data[:limit]
    except Exception as e:
        logger.error(f"Failed to fetch remote congressional feed: {e}")
    return []

async def sync_live_congress_trades(limit: int = 150) -> int:
    """
    Synchronizes fresh disclosures from live congressional streams into CAPitAL:
    - Creates or links Politician records
    - Ingests Transaction Reports and Trades
    - Computes Federal Contract matches
    - Runs Capitol-Alpha scoring and cluster detection
    - Recalculates member volume and alpha averages
    """
    items = await fetch_remote_feed(limit=limit)
    if not items:
        return 0

    inserted_trades = 0
    new_trade_objs: List[Dict[str, Any]] = []

    async with async_session_maker() as session:

        # Pre-cache politicians
        p_res = await session.execute(select(Politician).options(selectinload(Politician.committees)))
        politicians = {p.bioguide_id: p for p in p_res.scalars().all()}
        name_to_pol = {f"{p.first_name} {p.last_name}".lower(): p for p in politicians.values()}

        for item in items:
            raw_id = item.get("id")
            ticker = (item.get("ticker") or "").upper().strip()
            if not ticker or ticker == "--":
                continue

            filer_name = item.get("filer_name", "").strip()
            if not filer_name:
                continue

            chamber = "House" if (item.get("chamber") or "").lower() == "house" else "Senate"
            party_code = (item.get("party") or "I").upper()
            party = "Democrat" if party_code == "D" else ("Republican" if party_code == "R" else "Independent")
            state = (item.get("state") or "US").upper()

            # Identify or create politician
            filer_key = filer_name.lower()
            pol = name_to_pol.get(filer_key)

            if not pol:
                # Generate deterministic bio id
                clean_name = re.sub(r'[^a-zA-Z0-9]', '', filer_name)[:8].upper()
                gen_bioguide = f"G{clean_name}"
                
                parts = filer_name.split()
                first_name = parts[0] if parts else "Member"
                last_name = " ".join(parts[1:]) if len(parts) > 1 else parts[0]

                pol = await session.get(Politician, gen_bioguide)
                if not pol:
                    pol = Politician(
                        bioguide_id=gen_bioguide,
                        first_name=first_name,
                        last_name=last_name,
                        chamber=chamber,
                        party=party,
                        state=state,
                        active=True,
                        win_rate=55.0,
                        total_volume=0.0,
                        alpha_score=50.0
                    )
                    session.add(pol)
                    await session.flush()
                    politicians[gen_bioguide] = pol
                    name_to_pol[filer_key] = pol

            bioguide_id = pol.bioguide_id
            tx_date = parse_iso_date(item.get("transaction_date"))
            disc_date = parse_iso_date(item.get("filing_date") or item.get("disclosure_date"))
            doc_url = item.get("doc_url") or ""
            filing_id = str(item.get("source_id") or raw_id or f"DOC_{int(disc_date.strftime('%Y%m%d'))}_{ticker}")

            # Ensure Filing
            filing = await session.get(TransactionReport, filing_id)
            if not filing:
                filing = TransactionReport(
                    filing_id=filing_id,
                    bioguide_id=bioguide_id,
                    chamber=chamber,
                    filing_type="PTR",
                    filing_date=disc_date,
                    doc_url=doc_url,
                    is_amendment=False,
                    ocr_processed=True
                )
                session.add(filing)
                await session.flush()

            # Ensure Trade
            t_stmt = select(StockTrade).where(
                StockTrade.filing_id == filing_id,
                StockTrade.ticker == ticker,
                StockTrade.transaction_date == tx_date
            )
            t_res = await session.execute(t_stmt)
            existing_trade = t_res.scalar_one_or_none()

            amount_str = item.get("amount_range_label") or "$1,001 - $15,000"
            amount_min, amount_max, amount_mid = parse_amount_bracket(amount_str)
            lag_days, is_viol, sev = calculate_stock_act_lag(tx_date, disc_date)
            asset_type = normalize_asset_type(item.get("asset_type"))
            company_name = item.get("asset_name") or f"{ticker} Corporation"

            raw_owner = (item.get("owner") or "Self").capitalize()
            owner_norm = "Spouse" if "Spouse" in raw_owner else ("Joint" if "Joint" in raw_owner else "Self")

            if not existing_trade:
                trade = StockTrade(
                    filing_id=filing_id,
                    bioguide_id=bioguide_id,
                    ticker=ticker,
                    company_name=company_name,
                    asset_type=asset_type,
                    transaction_type=item.get("transaction_type") or "Purchase",
                    transaction_date=tx_date,
                    disclosure_date=disc_date,
                    amount_range_str=amount_str,
                    amount_min=amount_min,
                    amount_max=amount_max,
                    amount_midpoint=amount_mid,
                    owner_type=owner_norm,
                    filing_lag_days=lag_days,
                    is_stock_act_violation=is_viol,
                    violation_severity=sev,
                    price_at_transaction=item.get("price_at_transaction"),
                    price_at_disclosure=item.get("price_at_disclosure"),
                    return_30d=item.get("ret_30d"),
                    return_90d=item.get("ret_since") if item.get("ret_since") is not None else None,
                    benchmark_return_90d=item.get("excess_since")
                )
                session.add(trade)
                await session.flush()
                inserted_trades += 1

                # Match Contracts
                contracts = match_federal_contracts_for_ticker(ticker, tx_date)
                for c in contracts:
                    fcm = FederalContractMatch(
                        trade_id=trade.id,
                        agency_name=c["agency_name"],
                        contract_id=c["contract_id"],
                        award_date=c["award_date"],
                        award_amount=c["award_amount"],
                        days_between_trade_and_contract=c["days_between_trade_and_contract"],
                        match_confidence_score=c["match_confidence_score"]
                    )
                    session.add(fcm)
                new_trade_objs.append({
                    "id": trade.id,
                    "filing_id": trade.filing_id,
                    "bioguide_id": trade.bioguide_id,
                    "politician_name": f"{pol.first_name} {pol.last_name}",
                    "party": pol.party,
                    "state": pol.state,
                    "chamber": pol.chamber,
                    "ticker": trade.ticker,
                    "company_name": trade.company_name,
                    "asset_type": trade.asset_type,
                    "transaction_type": trade.transaction_type,
                    "transaction_date": str(trade.transaction_date),
                    "disclosure_date": str(trade.disclosure_date),
                    "amount_range_str": trade.amount_range_str,
                    "amount_midpoint": trade.amount_midpoint,
                    "owner_type": trade.owner_type,
                    "filing_lag_days": trade.filing_lag_days,
                    "is_stock_act_violation": trade.is_stock_act_violation,
                    "violation_severity": trade.violation_severity,
                    "alpha_score": {"composite_alpha_score": 65.0}
                })

        await session.commit()

        # Score all trades without a score
        all_trades_res = await session.execute(
            select(StockTrade).options(
                selectinload(StockTrade.politician).selectinload(Politician.committees),
                selectinload(StockTrade.alpha_score)
            )
        )
        all_trades = all_trades_res.scalars().all()
        clusters = detect_clusters_from_trades(all_trades, window_days=14)
        cluster_map: Dict[int, float] = {}
        for c in clusters:
            for ct in c.get("trades", []):
                cluster_map[ct["id"]] = max(cluster_map.get(ct["id"], 0.0), c["cluster_score"])

        for t in all_trades:
            if t.politician:
                existing_sc = await session.get(CapitolAlphaScore, t.id)
                if not existing_sc and not t.alpha_score:
                    c_score = cluster_map.get(t.id, 0.0)
                    sc = score_trade(t, t.politician, cluster_score=c_score)
                    session.add(sc)

        await session.commit()


        # Update Politician aggregate stats
        for pol in politicians.values():
            vol_stmt = select(func.sum(StockTrade.amount_midpoint)).where(StockTrade.bioguide_id == pol.bioguide_id)
            vol_res = await session.execute(vol_stmt)
            vol = vol_res.scalar()
            if vol:
                pol.total_volume = float(vol)

            avg_stmt = (
                select(func.avg(CapitolAlphaScore.composite_alpha_score))
                .join(StockTrade, CapitolAlphaScore.trade_id == StockTrade.id)
                .where(StockTrade.bioguide_id == pol.bioguide_id)
            )
            avg_res = await session.execute(avg_stmt)
            avg_sc = avg_res.scalar()
            if avg_sc:
                pol.alpha_score = round(float(avg_sc), 1)

        await session.commit()

    if new_trade_objs:
        try:
            from capitolseeder.api.routers.websocket import manager
            await manager.broadcast({
                "type": "NEW_TRADES",
                "count": len(new_trade_objs),
                "trades": new_trade_objs
            })
            logger.info(f"Broadcasted {len(new_trade_objs)} new trade(s) to connected WebSocket clients.")
        except Exception as e:
            logger.warning(f"Could not broadcast new trades to WebSocket: {e}")

    return inserted_trades

