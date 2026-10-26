import asyncio
import json
import logging
from typing import Optional, Set, Dict, Any
from inseeder.db.database import Database
from inseeder.collectors.sec_edgar import SecEdgarCollector, parse_form4_xml
from inseeder.engine.scorer import compute_conviction_score
from inseeder.engine.rules import evaluate_rules
from inseeder.execution.broker_base import IBrokerAdapter
from inseeder.execution.paper_broker import PaperBroker
from inseeder.execution.notifier import Notifier

logger = logging.getLogger("inseeder.worker")

class IngestionWorker:
    """
    Background worker orchestrating the end-to-end pipeline:
    Feed Ingestion -> XML Parsing -> Conviction Scoring -> Rule Evaluation ->
    Alert Dispatch -> Copy-Trade Execution -> SSE Broadcasting.
    """

    def __init__(
        self,
        db: Database,
        broker: Optional[IBrokerAdapter] = None,
        notifier: Optional[Notifier] = None,
        collector: Optional[SecEdgarCollector] = None,
        brokers: Optional[Dict[str, IBrokerAdapter]] = None
    ):
        self.db = db
        self.broker = broker or PaperBroker(db=db)
        self.brokers = brokers or {"paper": self.broker}
        if "paper" not in self.brokers and isinstance(self.broker, PaperBroker):
            self.brokers["paper"] = self.broker
        self.notifier = notifier or Notifier()
        self.collector = collector or SecEdgarCollector()
        self.subscribers: Set[asyncio.Queue] = set()
        self._running = False

    async def subscribe(self) -> asyncio.Queue:
        """Register a new SSE client subscriber queue."""
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.subscribers.add(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue):
        """Unregister an SSE client queue."""
        if q in self.subscribers:
            self.subscribers.remove(q)

    async def broadcast(self, event_type: str, data: Dict[str, Any]):
        """Push real-time event to all active SSE subscribers."""
        msg = {"type": event_type, "data": data}
        for q in list(self.subscribers):
            try:
                q.put_nowait(msg)
            except Exception as e:
                logger.debug(f"Subscriber queue error: {e}")

    async def run_once(self) -> int:
        """
        Executes a single polling and processing cycle.
        Returns the number of new trades processed.
        """
        entries = await self.collector.fetch_feed()
        processed_count = 0
        active_rules = await self.db.get_rules(active_only=True)

        for entry in entries:
            acc_no = entry.get("accession_no", "")
            index_url = entry.get("index_url", "")
            if not acc_no or not index_url:
                continue

            # Check if this filing was already processed before downloading files
            if await self.db.trade_exists(acc_no):
                continue

            # Fetch XML
            xml_content = await self.collector.fetch_form4_xml(index_url)
            if not xml_content:
                continue

            trades = parse_form4_xml(xml_content, acc_no, index_url)
            if not trades:
                continue

            for trade in trades:
                trade_id = await self.db.insert_trade(trade)
                if trade_id == 0:
                    # Already exists or insert ignored
                    continue

                processed_count += 1
                trade["id"] = trade_id

                # Broadcast trade to live stream
                await self.broadcast("trade", trade)

                # Cluster detection: check recent trades for the same ticker (last 7 days)
                # Count distinct insiders who bought within the window
                recent_cluster_trades = await self.db.get_recent_trades_for_cluster(trade["ticker"])
                distinct_insiders = {t.get("insider_name") for t in recent_cluster_trades if t.get("insider_name")}
                if trade.get("insider_name"):
                    distinct_insiders.add(trade["insider_name"])
                cluster_count = max(1, len(distinct_insiders))

                # Conviction Scoring
                conviction = compute_conviction_score(trade, cluster_count=cluster_count)
                score = conviction["score"]

                # Rule Matching
                matched_rules = evaluate_rules(trade, score, active_rules)

                # Create signal if score is significant (>=60) or matched rules
                if score >= 60 or matched_rules:
                    matched_rule_id = matched_rules[0]["id"] if matched_rules else None
                    signal_id = await self.db.insert_signal({
                        "trade_id": trade_id,
                        "score": score,
                        "matched_rule_id": matched_rule_id,
                        "cluster_count": cluster_count,
                        "details_json": json.dumps(conviction["breakdown"]),
                        "status": "new"
                    })

                    signal_payload = {
                        "id": signal_id,
                        "trade_id": trade_id,
                        "ticker": trade["ticker"],
                        "company_name": trade.get("company_name", ""),
                        "insider_name": trade.get("insider_name", ""),
                        "insider_title": trade.get("insider_title", ""),
                        "score": score,
                        "value": trade.get("value", 0.0),
                        "shares": trade.get("shares", 0.0),
                        "price": trade.get("price", 0.0),
                        "cluster_count": cluster_count,
                        "breakdown": conviction["breakdown"],
                        "sec_url": trade.get("sec_url", "")
                    }

                    # Broadcast signal event
                    await self.broadcast("signal", signal_payload)

                    # Send Alert (Telegram & Discord)
                    await self.notifier.send_signal_alert(signal_payload, trade)

                    # Check for auto-execution
                    for rule in matched_rules:
                        if rule.get("auto_execute", 0):
                            target_usd = float(rule.get("position_size_usd", 5000.0) or 5000.0)
                            price = float(trade.get("price", 0.0) or 0.0)
                            if price > 0:
                                qty = max(1.0, round(target_usd / price, 2))
                                target_broker_name = (rule.get("broker_target") or "paper").lower()
                                target_broker = self.brokers.get(target_broker_name, self.broker)
                                await target_broker.submit_order(
                                    symbol=trade["ticker"],
                                    qty=qty,
                                    side="buy",
                                    price=price,
                                    signal_id=signal_id
                                )
                                logger.info(f"Auto-executed order: {qty} shares of {trade['ticker']} via {target_broker.broker_name}")
                                break # Execute on first matched rule

        return processed_count

    async def start_loop(self, interval_sec: float = 30.0):
        """Runs the continuous ingestion loop."""
        self._running = True
        logger.info(f"Ingestion worker started (interval: {interval_sec}s)")
        while self._running:
            try:
                await self.run_once()
            except Exception as e:
                logger.error(f"Error in ingestion cycle: {e}")
            await asyncio.sleep(interval_sec)

    def stop(self):
        self._running = False
