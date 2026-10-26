import asyncio
import json
import datetime
import sys
from pathlib import Path
from typing import Optional, Any
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
import uvicorn

from capitolseeder.config import get_settings
from capitolseeder.db.session import init_db, async_session_maker
from capitolseeder.db.models import (
    Politician,
    CommitteeMembership,
    TransactionReport,
    StockTrade,
    FederalContractMatch,
    CapitolAlphaScore
)
from capitolseeder.ingestion.congress_metadata import seed_congress_metadata
from capitolseeder.ingestion.ocr_engine import parse_amount_bracket, calculate_stock_act_lag
from capitolseeder.engine.scoring_engine import score_trade
from capitolseeder.engine.cluster_detector import detect_clusters_from_trades

settings = get_settings()

def parse_date(val: Any) -> datetime.date:
    if isinstance(val, datetime.date):
        return val
    if isinstance(val, str):
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
            try:
                return datetime.datetime.strptime(val.strip(), fmt).date()
            except ValueError:
                continue
    return datetime.date.today()

async def run_seed() -> int:
    """
    Initializes database schema and ingests complete seed dataset with scores and contracts.
    """
    await init_db()
    
    async with async_session_maker() as session:
        # 1. Seed politicians & committees
        await seed_congress_metadata(session)

        # 2. Ingest trades
        seed_dir = settings.data_dir / "seed"
        with open(seed_dir / "trades.json", "r", encoding="utf-8") as f:
            trades_raw = json.load(f)

        trades_count = 0
        for tr in trades_raw:
            filing_id = tr["filing_id"]
            bioguide_id = tr["bioguide_id"]
            tx_date = parse_date(tr["transaction_date"])
            disc_date = parse_date(tr["disclosure_date"])

            # Ensure filing exists
            existing_filing = await session.get(TransactionReport, filing_id)
            if not existing_filing:
                filing = TransactionReport(
                    filing_id=filing_id,
                    bioguide_id=bioguide_id,
                    chamber=tr.get("chamber", "House"),
                    filing_type="PTR",
                    filing_date=parse_date(tr.get("filing_date", disc_date)),
                    doc_url=tr.get("doc_url", ""),
                    is_amendment=tr.get("is_amendment", False),
                    ocr_processed=True
                )
                session.add(filing)
                await session.flush()

            # Ensure trade exists
            stmt = select(StockTrade).where(
                StockTrade.filing_id == filing_id,
                StockTrade.ticker == tr["ticker"],
                StockTrade.transaction_date == tx_date
            )
            res = await session.execute(stmt)
            existing_trade = res.scalar_one_or_none()

            amount_min, amount_max, amount_mid = parse_amount_bracket(tr.get("amount_range_str", "$1,001 - $15,000"))
            lag_days, is_viol, sev = calculate_stock_act_lag(tx_date, disc_date)

            if not existing_trade:
                trade = StockTrade(
                    filing_id=filing_id,
                    bioguide_id=bioguide_id,
                    ticker=tr["ticker"].upper(),
                    company_name=tr.get("company_name", f"{tr['ticker']} Corp"),
                    asset_type=tr.get("asset_type", "Stock"),
                    transaction_type=tr.get("transaction_type", "Purchase"),
                    transaction_date=tx_date,
                    disclosure_date=disc_date,
                    amount_range_str=tr.get("amount_range_str", "$1,001 - $15,000"),
                    amount_min=amount_min,
                    amount_max=amount_max,
                    amount_midpoint=amount_mid,
                    owner_type=tr.get("owner_type", "Self"),
                    option_strike=tr.get("option_strike"),
                    option_expiration=parse_date(tr["option_expiration"]) if tr.get("option_expiration") else None,
                    filing_lag_days=lag_days,
                    is_stock_act_violation=is_viol,
                    violation_severity=sev,
                    price_at_transaction=tr.get("price_at_transaction"),
                    price_at_disclosure=tr.get("price_at_disclosure"),
                    return_30d=tr.get("return_30d"),
                    return_90d=tr.get("return_90d"),
                    benchmark_return_90d=tr.get("benchmark_return_90d")
                )
                session.add(trade)
                await session.flush()
            else:
                trade = existing_trade

            # Add contracts
            for c_data in tr.get("contracts", []):
                award_d = parse_date(c_data["award_date"])
                c_stmt = select(FederalContractMatch).where(
                    FederalContractMatch.trade_id == trade.id,
                    FederalContractMatch.contract_id == c_data["contract_id"]
                )
                c_res = await session.execute(c_stmt)
                if not c_res.scalar_one_or_none():
                    cm = FederalContractMatch(
                        trade_id=trade.id,
                        agency_name=c_data["agency_name"],
                        contract_id=c_data["contract_id"],
                        award_date=award_d,
                        award_amount=c_data["award_amount"],
                        days_between_trade_and_contract=c_data.get("days_between_trade_and_contract", (tx_date - award_d).days),
                        match_confidence_score=c_data.get("match_confidence_score", 1.0)
                    )
                    session.add(cm)

            trades_count += 1

        await session.commit()

        # Fetch politicians and trades
        pol_res = await session.execute(
            select(Politician).options(selectinload(Politician.committees))
        )
        politicians = {p.bioguide_id: p for p in pol_res.scalars().all()}

        all_trades_res = await session.execute(select(StockTrade))
        all_trades = all_trades_res.scalars().all()

        # 3. Detect clusters across all trades
        trades_for_clusters = []
        for t in all_trades:
            pol = politicians.get(t.bioguide_id)
            trades_for_clusters.append({
                "id": t.id,
                "ticker": t.ticker,
                "bioguide_id": t.bioguide_id,
                "party": pol.party if pol else "Unknown",
                "transaction_date": t.transaction_date,
                "transaction_type": t.transaction_type,
                "amount_range_str": t.amount_range_str
            })

        detected_clusters = detect_clusters_from_trades(trades_for_clusters, window_days=14)
        cluster_score_map = {}
        for c in detected_clusters:
            for ct in c.get("trades", []):
                cluster_score_map[ct["id"]] = max(cluster_score_map.get(ct["id"], 0.0), c["cluster_score"])

        # 4. Calculate Capitol-Alpha Scores for all trades
        for t in all_trades:
            pol = politicians.get(t.bioguide_id)
            if pol:
                c_score = cluster_score_map.get(t.id, 0.0)
                score_stmt = select(CapitolAlphaScore).where(CapitolAlphaScore.trade_id == t.id)
                s_res = await session.execute(score_stmt)
                existing_score = s_res.scalar_one_or_none()
                if not existing_score:
                    alpha_record = score_trade(t, pol, cluster_score=c_score)
                    session.add(alpha_record)
                else:
                    updated = score_trade(t, pol, cluster_score=c_score)
                    existing_score.conflict_score = updated.conflict_score
                    existing_score.cluster_score = updated.cluster_score
                    existing_score.winrate_score = updated.winrate_score
                    existing_score.size_score = updated.size_score
                    existing_score.asset_score = updated.asset_score
                    existing_score.decay_penalty = updated.decay_penalty
                    existing_score.composite_alpha_score = updated.composite_alpha_score
                    existing_score.rationale = updated.rationale

        await session.commit()

        # 4. Update Politician aggregate scores
        for bioguide_id, p in politicians.items():
            t_stmt = select(StockTrade).where(StockTrade.bioguide_id == bioguide_id)
            t_res = await session.execute(t_stmt)
            p_trades = t_res.scalars().all()

            if p_trades:
                total_vol = sum(t.amount_midpoint for t in p_trades)
                p.total_volume = total_vol
                # Update alpha average
                sc_stmt = (
                    select(func.avg(CapitolAlphaScore.composite_alpha_score))
                    .join(StockTrade, CapitolAlphaScore.trade_id == StockTrade.id)
                    .where(StockTrade.bioguide_id == bioguide_id)
                )
                sc_res = await session.execute(sc_stmt)
                avg_alpha = sc_res.scalar()
                if avg_alpha:
                    p.alpha_score = round(avg_alpha, 1)

        await session.commit()
        return trades_count

def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    if len(sys.argv) > 1 and sys.argv[1] == "seed":
        count = asyncio.run(run_seed())
        print(f"[OK] Successfully seeded {count} congressional transactions.")
    elif len(sys.argv) > 1 and sys.argv[1] == "serve":
        port = 8000
        if "--port" in sys.argv:
            idx = sys.argv.index("--port")
            if idx + 1 < len(sys.argv):
                port = int(sys.argv[idx + 1])
        print(f"[INFO] Launching CAPitAL Terminal on http://localhost:{port}...")
        uvicorn.run("capitolseeder.api.main:app", host="0.0.0.0", port=port, reload=True)
    else:
        print("Usage: python -m capitolseeder.cli [seed|serve]")

if __name__ == "__main__":
    main()
