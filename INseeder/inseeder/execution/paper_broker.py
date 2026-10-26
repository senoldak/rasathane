import math
import logging
from typing import List, Dict, Any, Optional
from inseeder.execution.broker_base import IBrokerAdapter
from inseeder.db.database import Database

logger = logging.getLogger("inseeder.execution.paper_broker")

class PaperBroker(IBrokerAdapter):
    """
    Zero-risk simulation broker managing a virtual cash balance,
    order execution at current market price, and position tracking.
    Persists cash balance in the database across restarts.
    """

    def __init__(self, db: Database, initial_cash: float = 100000.0):
        self.db = db
        self.initial_cash = initial_cash
        self._cash: Optional[float] = None
        self.broker_name = "paper"

    async def _get_cash(self) -> float:
        """Fetch cash from database or initialize with initial_cash."""
        if self._cash is None:
            persisted = await self.db.get_account_cash(self.broker_name)
            if persisted is not None and math.isfinite(persisted):
                self._cash = persisted
            else:
                self._cash = self.initial_cash
                await self.db.update_account_cash(self.broker_name, self._cash)
        return self._cash

    async def _set_cash(self, val: float):
        """Update in-memory and database cash balance."""
        if not math.isfinite(val):
            raise ValueError(f"Cannot set non-finite cash balance: {val}")
        self._cash = val
        await self.db.update_account_cash(self.broker_name, val)

    @property
    def cash(self) -> float:
        """Synchronous property for backward compatibility."""
        return self._cash if self._cash is not None else self.initial_cash

    @cash.setter
    def cash(self, val: float):
        self._cash = val

    async def get_account_summary(self) -> Dict[str, Any]:
        """Calculates total portfolio value, cash, and unrealized PnL."""
        current_cash = await self._get_cash()
        positions = await self.get_positions()
        positions_value = sum(p["qty"] * p["current_price"] for p in positions)
        total_value = current_cash + positions_value
        unrealized_pnl = sum(p["unrealized_pnl"] for p in positions)

        return {
            "broker": self.broker_name,
            "cash": round(current_cash, 2),
            "positions_value": round(positions_value, 2),
            "portfolio_value": round(total_value, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "open_positions_count": len(positions)
        }

    async def get_positions(self) -> List[Dict[str, Any]]:
        """Retrieves active positions from the database for paper broker."""
        return await self.db.get_positions(broker=self.broker_name)

    async def submit_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        price: Optional[float] = None,
        order_type: str = "market",
        signal_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Executes a paper order immediately at given price with strict validation.
        """
        symbol_upper = (symbol or "").upper().strip()
        side_lower = (side or "").lower().strip()

        # 1. Validate quantity
        if not isinstance(qty, (int, float)) or not math.isfinite(qty) or qty <= 0:
            return {
                "status": "rejected",
                "reason": f"Invalid order quantity: {qty}. Quantity must be a positive finite number.",
                "symbol": symbol_upper,
                "qty": qty,
                "side": side_lower
            }

        # 2. Validate price
        fill_price = price if price is not None and price > 0 and math.isfinite(price) else 100.0

        current_cash = await self._get_cash()

        if side_lower == "buy":
            cost = qty * fill_price
            if current_cash < cost:
                return {
                    "status": "rejected",
                    "reason": f"Insufficient funds. Required ${cost:.2f}, available ${current_cash:.2f}",
                    "symbol": symbol_upper,
                    "qty": qty,
                    "side": side_lower
                }

            await self._set_cash(current_cash - cost)

            # Check existing position
            positions = await self.get_positions()
            existing = next((p for p in positions if p["symbol"] == symbol_upper), None)

            if existing:
                old_qty = existing["qty"]
                old_avg = existing["avg_entry_price"]
                new_qty = old_qty + qty
                new_avg = ((old_qty * old_avg) + (qty * fill_price)) / new_qty
            else:
                new_qty = qty
                new_avg = fill_price

            unrealized = (fill_price - new_avg) * new_qty
            await self.db.upsert_position({
                "broker": self.broker_name,
                "symbol": symbol_upper,
                "qty": new_qty,
                "avg_entry_price": round(new_avg, 4),
                "current_price": round(fill_price, 4),
                "unrealized_pnl": round(unrealized, 2)
            })

            order_id = await self.db.insert_order({
                "signal_id": signal_id,
                "broker": self.broker_name,
                "symbol": symbol_upper,
                "side": "buy",
                "qty": qty,
                "fill_price": fill_price,
                "status": "filled"
            })

            return {
                "order_id": order_id,
                "status": "filled",
                "symbol": symbol_upper,
                "qty": qty,
                "side": "buy",
                "fill_price": fill_price
            }

        elif side_lower == "sell":
            positions = await self.get_positions()
            existing = next((p for p in positions if p["symbol"] == symbol_upper), None)

            if not existing or existing["qty"] < qty:
                available = existing["qty"] if existing else 0
                return {
                    "status": "rejected",
                    "reason": f"Insufficient shares to sell. Required {qty}, available {available}",
                    "symbol": symbol_upper,
                    "qty": qty,
                    "side": side_lower
                }

            revenue = qty * fill_price
            await self._set_cash(current_cash + revenue)

            new_qty = existing["qty"] - qty
            new_avg = existing["avg_entry_price"] if new_qty > 0 else 0.0
            unrealized = (fill_price - new_avg) * new_qty if new_qty > 0 else 0.0

            await self.db.upsert_position({
                "broker": self.broker_name,
                "symbol": symbol_upper,
                "qty": new_qty,
                "avg_entry_price": round(new_avg, 4),
                "current_price": round(fill_price, 4),
                "unrealized_pnl": round(unrealized, 2)
            })

            order_id = await self.db.insert_order({
                "signal_id": signal_id,
                "broker": self.broker_name,
                "symbol": symbol_upper,
                "side": "sell",
                "qty": qty,
                "fill_price": fill_price,
                "status": "filled"
            })

            return {
                "order_id": order_id,
                "status": "filled",
                "symbol": symbol_upper,
                "qty": qty,
                "side": "sell",
                "fill_price": fill_price
            }

        return {"status": "rejected", "reason": f"Unsupported order side: {side}"}
