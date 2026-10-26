from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class IBrokerAdapter(ABC):
    """Abstract interface for all brokerage adapters (Paper, Alpaca, IBKR)."""

    @abstractmethod
    async def get_account_summary(self) -> Dict[str, Any]:
        """Returns account balance, cash, buying power, and portfolio value."""
        pass

    @abstractmethod
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Returns list of active open positions."""
        pass

    @abstractmethod
    async def submit_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        price: Optional[float] = None,
        order_type: str = "market",
        signal_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Submits an order (buy/sell)."""
        pass
