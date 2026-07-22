from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class SecurityProfile:
    symbol: str
    name: str = ""
    exchange: str = ""
    asset_type: str = "EQUITY"
    active: bool = True
    tradable: bool = True
    options_eligible: bool = False
    sector: str = ""
    industry: str = ""
    market_cap: float | None = None
    average_daily_volume: float | None = None
    source: str = "UNKNOWN"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UniverseProfile:
    universe_id: str
    name: str
    generated_at: datetime
    securities: tuple[SecurityProfile, ...]
    source_names: tuple[str, ...]
    governance_status: str
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UniverseBuildResult:
    universe: UniverseProfile
    received_count: int
    accepted_count: int
    rejected_count: int
    duplicate_count: int
    rejection_reasons: dict[str, int]
