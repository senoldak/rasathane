import logging
from typing import List, Dict, Any, Optional
import httpx
from inseeder.execution.broker_base import IBrokerAdapter

logger = logging.getLogger("inseeder.execution.alpaca_broker")

class AlpacaBroker(IBrokerAdapter):
    """
    Alpaca Markets Paper & Live Trading REST API adapter.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = "https://paper-api.alpaca.markets",
        db: Optional[Any] = None
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.broker_name = "alpaca"
        self.db = db
        self.client = httpx.AsyncClient(
            headers={
                "APCA-API-KEY-ID": self.api_key,
                "APCA-API-SECRET-KEY": self.api_secret,
                "Content-Type": "application/json"
            },
            timeout=15.0
        )

    async def get_account_summary(self) -> Dict[str, Any]:
        """Fetches cash, equity, buying power from Alpaca /v2/account."""
        try:
            resp = await self.client.get(f"{self.base_url}/v2/account")
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "broker": self.broker_name,
                    "cash": float(data.get("cash", 0.0)),
                    "portfolio_value": float(data.get("portfolio_value", 0.0)),
                    "buying_power": float(data.get("buying_power", 0.0)),
                    "status": data.get("status", "ACTIVE")
                }
            else:
                logger.error(f"Alpaca account fetch failed ({resp.status_code}): {resp.text}")
        except Exception as e:
            logger.error(f"Alpaca account fetch error: {e}")

        return {
            "broker": self.broker_name,
            "cash": 0.0,
            "portfolio_value": 0.0,
            "buying_power": 0.0,
            "status": "ERROR"
        }

    async def get_positions(self) -> List[Dict[str, Any]]:
        """Fetches active positions from Alpaca /v2/positions."""
        try:
            resp = await self.client.get(f"{self.base_url}/v2/positions")
            if resp.status_code == 200:
                data = resp.json()
                return [
                    {
                        "symbol": p.get("symbol"),
                        "qty": float(p.get("qty", 0.0)),
                        "avg_entry_price": float(p.get("avg_entry_price", 0.0)),
                        "current_price": float(p.get("current_price", 0.0)),
                        "unrealized_pnl": float(p.get("unrealized_pl", 0.0))
                    }
                    for p in data
                ]
            else:
                logger.error(f"Alpaca positions fetch failed: {resp.text}")
        except Exception as e:
            logger.error(f"Alpaca positions fetch error: {e}")

        return []

    async def submit_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        price: Optional[float] = None,
        order_type: str = "market",
        signal_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Submits an order to Alpaca /v2/orders."""
        payload = {
            "symbol": symbol.upper(),
            "qty": str(qty),
            "side": side.lower(),
            "type": order_type.lower(),
            "time_in_force": "day"
        }
        if order_type.lower() == "limit" and price:
            payload["limit_price"] = str(price)

        try:
            resp = await self.client.post(f"{self.base_url}/v2/orders", json=payload)
            if resp.status_code in (200, 201):
                data = resp.json()
                if self.db:
                    try:
                        await self.db.insert_order({
                            "signal_id": signal_id,
                            "broker": self.broker_name,
                            "symbol": symbol.upper(),
                            "side": side.lower(),
                            "qty": float(data.get("qty", qty)),
                            "fill_price": float(price or 0.0),
                            "status": data.get("status", "accepted")
                        })
                    except Exception as err:
                        logger.warning(f"Could not persist Alpaca order to DB: {err}")

                return {
                    "broker": self.broker_name,
                    "order_id": data.get("id"),
                    "symbol": data.get("symbol"),
                    "qty": float(data.get("qty", qty)),
                    "side": data.get("side"),
                    "status": data.get("status", "accepted"),
                    "signal_id": signal_id
                }
            else:
                logger.error(f"Alpaca order rejected ({resp.status_code}): {resp.text}")
                return {
                    "broker": self.broker_name,
                    "status": "rejected",
                    "reason": resp.text,
                    "symbol": symbol.upper()
                }
        except Exception as e:
            logger.error(f"Alpaca order submission error: {e}")
            return {
                "broker": self.broker_name,
                "status": "error",
                "reason": str(e),
                "symbol": symbol.upper()
            }

    async def close(self):
        await self.client.aclose()
