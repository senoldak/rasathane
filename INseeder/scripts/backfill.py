"""
Historic Form 4 Backfill Utility for INseeder

Downloads and processes Form 4 filings for a date range from SEC EDGAR daily indices,
scores them with the quantitative conviction model, and inserts trades and high-conviction
signals into the SQLite database.

Usage:
    python scripts/backfill.py --days 5
    python scripts/backfill.py --dates 20260918 20260917 20260916
"""

import asyncio
import re
import json
import logging
import argparse
from datetime import datetime, timedelta
import httpx
from typing import List, Dict, Any, Optional

from inseeder.db.database import Database
from inseeder.collectors.sec_edgar import SecEdgarCollector, parse_form4_xml
from inseeder.engine.scorer import compute_conviction_score
from inseeder.engine.rules import evaluate_rules
from inseeder.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("backfill")


def get_default_dates(days: int = 5) -> List[str]:
    """Generate a list of YYYYMMDD date strings for the past N business days."""
    dates: List[str] = []
    current = datetime.now()
    while len(dates) < days:
        current -= timedelta(days=1)
        # Skip weekends (Saturday=5, Sunday=6)
        if current.weekday() < 5:
            dates.append(current.strftime("%Y%m%d"))
    return dates


async def parse_daily_index(client: httpx.AsyncClient, date_str: str) -> List[Dict[str, str]]:
    """Download daily index from SEC EDGAR and return list of Form 4 records."""
    year = date_str[:4]
    month = int(date_str[4:6])
    quarter = f"QTR{(month - 1) // 3 + 1}"
    url = f"https://www.sec.gov/Archives/edgar/daily-index/{year}/{quarter}/form.{date_str}.idx"

    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            logger.warning(f"Failed to fetch daily index for {date_str}: HTTP {resp.status_code}")
            return []

        entries = []
        for line in resp.text.splitlines():
            # Line format: Form Type (12) | Company Name (62) | CIK (12) | Date (12) | File Name
            if line.startswith("4 ") or line.startswith("4/A "):
                parts = line.split()
                if len(parts) >= 5:
                    file_path = parts[-1]  # e.g. edgar/data/910638/0001628280-26-062712.txt
                    acc_match = re.search(r"([0-9]{10}\-[0-9]{2}\-[0-9]{6})", file_path)
                    cik_match = re.search(r"data/([0-9]+)/", file_path)
                    if acc_match and cik_match:
                        acc_no = acc_match.group(1)
                        cik = cik_match.group(1)
                        acc_no_nodash = acc_no.replace("-", "")
                        index_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_nodash}/{acc_no}-index.htm"
                        entries.append({
                            "accession_no": acc_no,
                            "index_url": index_url,
                            "date": date_str
                        })
        return entries
    except Exception as e:
        logger.error(f"Error reading daily index for {date_str}: {e}")
        return []


async def run_backfill(dates: List[str]):
    """Execute backfill pipeline for the specified list of dates."""
    logger.info(f"Initializing Form 4 backfill for dates: {', '.join(dates)}")
    db = Database(settings.DB_PATH)
    await db.init_db()
    collector = SecEdgarCollector(user_agent=settings.SEC_USER_AGENT)
    active_rules = await db.get_rules(active_only=True)

    total_inserted_trades = 0
    total_signals_created = 0

    try:
        for date_str in dates:
            logger.info(f"=== Processing Date: {date_str} ===")
            entries = await parse_daily_index(collector.client, date_str)
            logger.info(f"Found {len(entries)} Form 4 filings for {date_str}")

            for idx, entry in enumerate(entries):
                acc_no = entry["accession_no"]
                index_url = entry["index_url"]

                # Skip if already in database
                if await db.trade_exists(acc_no):
                    continue

                # Throttle requests to respect SEC Fair Access policy (max 10 req/sec)
                await asyncio.sleep(0.12)

                xml_content = await collector.fetch_form4_xml(index_url)
                if not xml_content:
                    continue

                trades = parse_form4_xml(xml_content, acc_no, index_url)
                if not trades:
                    continue

                for trade in trades:
                    trade_id = await db.insert_trade(trade)
                    if trade_id == 0:
                        continue

                    total_inserted_trades += 1
                    trade["id"] = trade_id

                    # 7-day cluster detection
                    recent_cluster = await db.get_recent_trades_for_cluster(trade["ticker"])
                    distinct_insiders = {t.get("insider_name") for t in recent_cluster if t.get("insider_name")}
                    if trade.get("insider_name"):
                        distinct_insiders.add(trade["insider_name"])
                    cluster_count = max(1, len(distinct_insiders))

                    # Conviction scoring
                    conviction = compute_conviction_score(trade, cluster_count=cluster_count)
                    score = conviction["score"]
                    matched_rules = evaluate_rules(trade, score, active_rules)

                    # Create High Conviction Signal if score >= 60 or matches an active rule
                    if score >= 60 or matched_rules:
                        matched_rule_id = matched_rules[0]["id"] if matched_rules else None
                        await db.insert_signal({
                            "trade_id": trade_id,
                            "score": score,
                            "matched_rule_id": matched_rule_id,
                            "cluster_count": cluster_count,
                            "details_json": json.dumps(conviction["breakdown"]),
                            "status": "new"
                        })
                        total_signals_created += 1
                        logger.info(
                            f"⚡ SIGNAL [{trade['ticker']}] {trade['insider_name']} "
                            f"({trade.get('insider_title')}) - Score: {score}/100 | Val: ${trade.get('value', 0):,.2f}"
                        )

                if (idx + 1) % 50 == 0:
                    logger.info(
                        f"Progress ({date_str}): {idx+1}/{len(entries)} filings | "
                        f"Trades so far: {total_inserted_trades} | Signals: {total_signals_created}"
                    )

    finally:
        await collector.close()
        await db.close()
        logger.info(
            f"Backfill Completed! Total New Trades: {total_inserted_trades} | "
            f"Total Signals: {total_signals_created}"
        )


def main():
    parser = argparse.ArgumentParser(description="INseeder Form 4 Historic Backfill Utility")
    parser.add_argument(
        "--days",
        type=int,
        default=5,
        help="Number of recent business days to backfill (default: 5)"
    )
    parser.add_argument(
        "--dates",
        nargs="+",
        help="Explicit list of YYYYMMDD dates to backfill (e.g., --dates 20260918 20260917)"
    )
    args = parser.parse_args()

    dates = args.dates if args.dates else get_default_dates(args.days)
    asyncio.run(run_backfill(dates))


if __name__ == "__main__":
    main()
