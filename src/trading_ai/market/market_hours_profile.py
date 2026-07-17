from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MarketSessionProfile:
    exchange: str
    timezone: str
    local_timestamp: str
    trading_date: str
    session: str
    market_open: bool
    regular_session: bool
    holiday: bool
    early_close: bool
    next_open_at: str | None = None
    next_close_at: str | None = None
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
