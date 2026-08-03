from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class IbkrPaperOrderRequest:
    aggregate_id: str
    client_order_id: str
    portfolio_id: str
    broker_account_id: str
    symbol: str
    security_type: str
    side: str
    quantity: float
    order_type: str = "MKT"
    time_in_force: str = "DAY"
    limit_price: float | None = None
    stop_price: float | None = None
    currency: str = "USD"
    exchange: str = "SMART"
    primary_exchange: str = ""
    contract_id: int = 0
    local_symbol: str = ""
    expiry: str = ""
    strike: float | None = None
    right: str = ""
    multiplier: str = ""
    outside_regular_hours: bool = False
    transmit: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.aggregate_id or not self.client_order_id:
            raise ValueError("aggregate_id and client_order_id are required")
        if not self.broker_account_id.upper().startswith("DU"):
            raise ValueError("IBKR paper account must begin with DU")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.side.upper() not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        typ = self.order_type.upper()
        if typ not in {"MKT", "LMT", "STP", "STP LMT"}:
            raise ValueError("unsupported order type")
        if typ in {"LMT", "STP LMT"} and self.limit_price is None:
            raise ValueError("limit_price is required")
        if typ in {"STP", "STP LMT"} and self.stop_price is None:
            raise ValueError("stop_price is required")


@dataclass(frozen=True)
class IbkrPaperComboLegRequest:
    contract_id: int
    ratio: int
    action: str
    exchange: str = "SMART"
    symbol: str = ""
    local_symbol: str = ""
    expiry: str = ""
    strike: float | None = None
    right: str = ""
    multiplier: str = "100"

    def validate(self) -> None:
        if self.contract_id <= 0:
            raise ValueError("combo leg contract_id must be positive")
        if self.ratio <= 0:
            raise ValueError("combo leg ratio must be positive")
        if self.action.upper() not in {"BUY", "SELL"}:
            raise ValueError("combo leg action must be BUY or SELL")
        if not self.exchange:
            raise ValueError("combo leg exchange is required")


@dataclass(frozen=True)
class IbkrPaperComboOrderRequest:
    aggregate_id: str
    client_order_id: str
    portfolio_id: str
    broker_account_id: str
    symbol: str
    quantity: float
    combo_legs: tuple[IbkrPaperComboLegRequest, ...]
    order_type: str = "LMT"
    time_in_force: str = "DAY"
    limit_price: float | None = None
    currency: str = "USD"
    exchange: str = "SMART"
    outside_regular_hours: bool = False
    transmit: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def security_type(self) -> str:
        return "BAG"

    @property
    def side(self) -> str:
        # Combo leg actions define the strategy direction. A BUY parent with a
        # signed net limit price is the canonical IBKR representation used here.
        return "BUY"

    def validate(self) -> None:
        if not self.aggregate_id or not self.client_order_id:
            raise ValueError("aggregate_id and client_order_id are required")
        if not self.broker_account_id.upper().startswith("DU"):
            raise ValueError("IBKR paper account must begin with DU")
        if self.quantity <= 0:
            raise ValueError("combo quantity must be positive")
        if not 2 <= len(self.combo_legs) <= 4:
            raise ValueError("IBKR combo orders require between two and four legs")
        if self.order_type.upper() != "LMT":
            raise ValueError("combo orders currently require LMT order type")
        if self.limit_price is None:
            raise ValueError("combo limit_price is required")
        for leg in self.combo_legs:
            leg.validate()
        if len({leg.contract_id for leg in self.combo_legs}) != len(self.combo_legs):
            raise ValueError("combo leg contract IDs must be unique")
        actions = {leg.action.upper() for leg in self.combo_legs}
        if actions != {"BUY", "SELL"}:
            raise ValueError("combo order must contain at least one BUY and one SELL leg")


@dataclass(frozen=True)
class IbkrPaperOrderStatus:
    broker_order_id: int
    permanent_id: int
    client_id: int
    status: str
    filled_quantity: float
    remaining_quantity: float
    average_fill_price: float
    last_fill_price: float = 0.0
    why_held: str = ""
    updated_at: str = field(default_factory=utc_now_iso)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IbkrPaperExecution:
    execution_id: str
    broker_order_id: int
    permanent_id: int
    client_id: int
    broker_account_id: str
    contract_id: int
    symbol: str
    security_type: str
    side: str
    quantity: float
    price: float
    commission: float
    currency: str
    executed_at: str
    exchange: str = ""
    liquidation: int = 0
    raw: dict[str, Any] = field(default_factory=dict)
