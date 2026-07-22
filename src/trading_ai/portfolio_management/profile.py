from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PortfolioAccount:
    portfolio_id: str
    name: str
    base_currency: str
    initial_capital: float
    created_at: str
    status: str = "ACTIVE"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PortfolioPositionRecord:
    position_id: str
    portfolio_id: str
    symbol: str
    strategy_id: str
    strategy_type: str
    direction: str
    status: str
    quantity: int
    entry_price: float
    current_price: float
    capital_committed: float
    maximum_loss: float | None
    maximum_profit: float | None
    realized_pnl: float
    unrealized_pnl: float
    opened_at: str
    updated_at: str
    closed_at: str | None = None
    sector: str = "UNKNOWN"
    industry: str = "UNKNOWN"
    correlation_group: str = ""
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    source_artifact: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PortfolioCashLedgerEntry:
    entry_id: str
    portfolio_id: str
    event_type: str
    amount: float
    balance_after: float
    occurred_at: str
    reference_id: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PortfolioRegistrySnapshot:
    account: PortfolioAccount
    cash_balance: float
    net_liquidation_value: float
    total_capital_committed: float
    total_realized_pnl: float
    total_unrealized_pnl: float
    open_position_count: int
    closed_position_count: int
    positions: tuple[PortfolioPositionRecord, ...]
    cash_ledger: tuple[PortfolioCashLedgerEntry, ...]
    generated_at: str = field(default_factory=utc_now_iso)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "account": self.account.to_dict(),
            "cash_balance": self.cash_balance,
            "net_liquidation_value": self.net_liquidation_value,
            "total_capital_committed": self.total_capital_committed,
            "total_realized_pnl": self.total_realized_pnl,
            "total_unrealized_pnl": self.total_unrealized_pnl,
            "open_position_count": self.open_position_count,
            "closed_position_count": self.closed_position_count,
            "positions": [item.to_dict() for item in self.positions],
            "cash_ledger": [item.to_dict() for item in self.cash_ledger],
            "generated_at": self.generated_at,
            "warnings": list(self.warnings),
        }
