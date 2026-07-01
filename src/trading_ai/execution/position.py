from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class PaperPosition:
    order_id: str
    symbol: str
    signal: str
    strategy: str
    strike: float
    expiry: str
    quantity: int
    entry_price: float
    current_price: float
    opened_at: str
    implied_volatility: float = 0.25
    status: str = "OPEN"
    closed_at: str | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0

    def mark(self, current_price: float):
        self.current_price = float(current_price)
        self.unrealized_pnl = (
            self.current_price - self.entry_price
        ) * self.quantity * 100.0
        return self.unrealized_pnl

    def close(self, exit_price: float, reason: str):
        self.exit_price = float(exit_price)
        self.exit_reason = reason
        self.closed_at = datetime.now().isoformat()
        self.status = "CLOSED"
        self.realized_pnl = (
            self.exit_price - self.entry_price
        ) * self.quantity * 100.0
        self.unrealized_pnl = 0.0
        return self.realized_pnl

    def to_dict(self):
        return asdict(self)
