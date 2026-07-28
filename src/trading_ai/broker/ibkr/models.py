from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class IbkrPaperConnectionConfig:
    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 50
    environment: str = "PAPER"
    expected_account_id: str = ""
    timeout_seconds: float = 15.0
    read_only: bool = True

    def validate(self) -> None:
        if self.environment.upper() != "PAPER":
            raise ValueError("IBKR environment must be PAPER")
        if self.port <= 0 or self.port > 65535:
            raise ValueError("IBKR port must be between 1 and 65535")
        if self.client_id < 0:
            raise ValueError("IBKR client_id must be non-negative")
        if self.expected_account_id and not self.expected_account_id.upper().startswith("DU"):
            raise ValueError("Expected IBKR paper account must begin with DU")


@dataclass(frozen=True)
class IbkrAccountSummary:
    broker_account_id: str
    base_currency: str
    net_liquidation: float
    total_cash_value: float
    available_funds: float
    buying_power: float
    excess_liquidity: float = 0.0
    captured_at: str = field(default_factory=utc_now_iso)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IbkrPositionSnapshot:
    broker_account_id: str
    contract_id: int
    symbol: str
    security_type: str
    currency: str
    exchange: str
    quantity: float
    average_cost: float
    local_symbol: str = ""
    expiry: str = ""
    strike: float | None = None
    right: str = ""
    multiplier: float = 1.0
    captured_at: str = field(default_factory=utc_now_iso)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IbkrConnectionStatus:
    connected: bool
    environment: str
    account_ids: tuple[str, ...]
    server_version: int | None = None
    message: str = ""
