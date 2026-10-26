import aiosqlite
import os
import json
from typing import List, Dict, Any, Optional

class Database:
    def __init__(self, db_path: str = "inseeder.db"):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def get_conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            self._conn = await aiosqlite.connect(self.db_path)
            self._conn.row_factory = aiosqlite.Row
        return self._conn

    async def init_db(self):
        conn = await self.get_conn()
        await conn.execute("PRAGMA journal_mode=WAL;")
        await conn.execute("PRAGMA busy_timeout=5000;")
        await conn.execute("PRAGMA synchronous=NORMAL;")
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        with open(schema_path, "r", encoding="utf-8") as f:
            await conn.executescript(f.read())
        await conn.commit()

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def trade_exists(self, accession_no: str) -> bool:
        """Check if an accession number (or filing with this accession) is already stored."""
        conn = await self.get_conn()
        cursor = await conn.execute(
            "SELECT 1 FROM trades WHERE accession_no = ? OR accession_no LIKE ? || '_%' LIMIT 1",
            (accession_no, accession_no)
        )
        row = await cursor.fetchone()
        return row is not None

    async def insert_trade(self, trade: Dict[str, Any]) -> int:
        conn = await self.get_conn()
        trade_params = {
            "accession_no": trade.get("accession_no"),
            "filing_date": trade.get("filing_date"),
            "trade_date": trade.get("trade_date"),
            "ticker": trade.get("ticker"),
            "company_name": trade.get("company_name"),
            "insider_name": trade.get("insider_name"),
            "insider_title": trade.get("insider_title"),
            "is_director": int(bool(trade.get("is_director", 0))),
            "is_officer": int(bool(trade.get("is_officer", 0))),
            "is_ten_percent": int(bool(trade.get("is_ten_percent", 0))),
            "transaction_code": trade.get("transaction_code", "P"),
            "shares": float(trade.get("shares", 0.0) or 0.0),
            "price": float(trade.get("price", 0.0) or 0.0),
            "value": float(trade.get("value", 0.0) or 0.0),
            "shares_owned_after": float(trade.get("shares_owned_after", 0.0) or 0.0),
            "is_10b5_1": int(bool(trade.get("is_10b5_1", 0))),
            "sec_url": trade.get("sec_url") or "",
        }
        query = """
        INSERT OR IGNORE INTO trades (
            accession_no, filing_date, trade_date, ticker, company_name,
            insider_name, insider_title, is_director, is_officer, is_ten_percent,
            transaction_code, shares, price, value, shares_owned_after,
            is_10b5_1, sec_url
        ) VALUES (
            :accession_no, :filing_date, :trade_date, :ticker, :company_name,
            :insider_name, :insider_title, :is_director, :is_officer, :is_ten_percent,
            :transaction_code, :shares, :price, :value, :shares_owned_after,
            :is_10b5_1, :sec_url
        )
        """
        cursor = await conn.execute(query, trade_params)
        await conn.commit()
        if cursor.rowcount == 0:
            return 0
        return cursor.lastrowid or 0

    async def get_account_cash(self, broker: str) -> Optional[float]:
        """Fetch persisted virtual cash balance for a broker adapter."""
        conn = await self.get_conn()
        cursor = await conn.execute("SELECT cash FROM accounts WHERE broker = ?", (broker,))
        row = await cursor.fetchone()
        return float(row["cash"]) if row is not None else None

    async def update_account_cash(self, broker: str, cash: float):
        """Update or insert persisted virtual cash balance for a broker adapter."""
        conn = await self.get_conn()
        query = """
        INSERT INTO accounts (broker, cash, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(broker) DO UPDATE SET
            cash = excluded.cash,
            updated_at = CURRENT_TIMESTAMP
        """
        await conn.execute(query, (broker, cash))
        await conn.commit()

    async def get_trades(self, limit: int = 50, offset: int = 0, ticker: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = await self.get_conn()
        if ticker:
            cursor = await conn.execute(
                "SELECT * FROM trades WHERE ticker = ? ORDER BY filing_date DESC LIMIT ? OFFSET ?",
                (ticker.upper(), limit, offset)
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM trades ORDER BY filing_date DESC LIMIT ? OFFSET ?",
                (limit, offset)
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_recent_trades_for_cluster(self, ticker: str, days: int = 7) -> List[Dict[str, Any]]:
        conn = await self.get_conn()
        query = """
        SELECT * FROM trades 
        WHERE ticker = ? AND transaction_code = 'P' 
        AND datetime(filing_date) >= datetime('now', ?)
        ORDER BY filing_date DESC
        """
        cursor = await conn.execute(query, (ticker.upper(), f"-{days} days"))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def insert_signal(self, signal: Dict[str, Any]) -> int:
        conn = await self.get_conn()
        query = """
        INSERT INTO signals (
            trade_id, score, matched_rule_id, cluster_count, details_json, status
        ) VALUES (
            :trade_id, :score, :matched_rule_id, :cluster_count, :details_json, :status
        )
        """
        cursor = await conn.execute(query, signal)
        await conn.commit()
        return cursor.lastrowid or 0

    async def get_signals(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        conn = await self.get_conn()
        query = """
        SELECT s.*, t.ticker, t.company_name, t.insider_name, t.insider_title,
               t.transaction_code, t.shares, t.price, t.value, t.filing_date, t.sec_url
        FROM signals s
        JOIN trades t ON s.trade_id = t.id
        ORDER BY s.created_at DESC LIMIT ? OFFSET ?
        """
        cursor = await conn.execute(query, (limit, offset))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def insert_rule(self, rule: Dict[str, Any]) -> int:
        conn = await self.get_conn()
        query = """
        INSERT INTO rules (
            name, is_active, min_score, min_value, allowed_roles, allowed_types,
            auto_execute, broker_target, position_size_usd
        ) VALUES (
            :name, :is_active, :min_score, :min_value, :allowed_roles, :allowed_types,
            :auto_execute, :broker_target, :position_size_usd
        )
        """
        cursor = await conn.execute(query, rule)
        await conn.commit()
        return cursor.lastrowid or 0

    async def get_rules(self, active_only: bool = False) -> List[Dict[str, Any]]:
        conn = await self.get_conn()
        if active_only:
            cursor = await conn.execute("SELECT * FROM rules WHERE is_active = 1 ORDER BY id ASC")
        else:
            cursor = await conn.execute("SELECT * FROM rules ORDER BY id ASC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def delete_rule(self, rule_id: int) -> bool:
        conn = await self.get_conn()
        cursor = await conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
        await conn.commit()
        return cursor.rowcount > 0

    async def insert_order(self, order: Dict[str, Any]) -> int:
        conn = await self.get_conn()
        query = """
        INSERT INTO orders (
            signal_id, broker, symbol, side, qty, fill_price, status
        ) VALUES (
            :signal_id, :broker, :symbol, :side, :qty, :fill_price, :status
        )
        """
        cursor = await conn.execute(query, order)
        await conn.commit()
        return cursor.lastrowid or 0

    async def get_orders(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = await self.get_conn()
        cursor = await conn.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def upsert_position(self, position: Dict[str, Any]):
        conn = await self.get_conn()
        query = """
        INSERT INTO positions (broker, symbol, qty, avg_entry_price, current_price, unrealized_pnl, updated_at)
        VALUES (:broker, :symbol, :qty, :avg_entry_price, :current_price, :unrealized_pnl, CURRENT_TIMESTAMP)
        ON CONFLICT(broker, symbol) DO UPDATE SET
            qty = :qty,
            avg_entry_price = :avg_entry_price,
            current_price = :current_price,
            unrealized_pnl = :unrealized_pnl,
            updated_at = CURRENT_TIMESTAMP
        """
        await conn.execute(query, position)
        await conn.commit()

    async def get_positions(self, broker: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = await self.get_conn()
        if broker:
            cursor = await conn.execute("SELECT * FROM positions WHERE broker = ? AND qty > 0", (broker,))
        else:
            cursor = await conn.execute("SELECT * FROM positions WHERE qty > 0")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
