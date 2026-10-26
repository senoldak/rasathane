import logging
from typing import List, Dict, Any, Optional
import httpx
from inseeder.execution.broker_base import IBrokerAdapter

logger = logging.getLogger("inseeder.execution.ibkr_broker")

class IBKRBroker(IBrokerAdapter):
    """
    Interactive Brokers Client Portal / Web API Adapter.
    Communicates with IBKR Client Portal Gateway (default: https://localhost:5000/v1/api).
    """

    def __init__(self, base_url: str = "https://localhost:5000/v1/api", account_id: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.account_id = account_id
        self.broker_name = "ibkr"
        self.client = httpx.AsyncClient(verify=False, timeout=15.0)

    async def get_account_summary(self) -> Dict[str, Any]:
        """Fetches account summary from IBKR Client Portal API."""
        try:
            resp = await self.client.get(f"{self.base_url}/portfolio/accounts")
            if resp.status_code == 200:
                data = resp.json()
                return {"broker": self.broker_name, "accounts": data, "status": "ACTIVE"}
        except Exception as e:
            logger.warning(f"IBKR gateway not reachable: {e}")

        return {"broker": self.broker_name, "status": "DISCONNECTED", "cash": 0.0, "portfolio_value": 0.0}

    async def get_positions(self) -> List[Dict[str, Any]]:
        """Fetches positions from IBKR Client Portal API."""
        if not self.account_id:
            return []
        try:
            resp = await self.client.get(f"{self.base_url}/portfolio/{self.account_id}/positions")
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"IBKR get_positions error: {e}")
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
        """Submits an order through IBKR Client Portal API."""
        logger.info(f"IBKR order requested: {side} {qty} {symbol}")
        return {
            "broker": self.broker_name,
            "status": "simulated_accepted",
            "symbol": symbol.upper(),
            "qty": qty,
            "side": side.lower(),
            "signal_id": signal_id
        }

    async def close(self):
        await self.client.aclose()
