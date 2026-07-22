from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PositionMark:
    position_id: str
    symbol: str
    strategy_id: str
    status: str
    quantity: int
    entry_debit: float
    current_debit: float | None
    exit_debit: float | None
    unrealized_pnl: float | None
    realized_pnl: float | None
    return_pct: float | None
    marked_at: str
    closed_at: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class PerformanceSummary:
    total_positions: int
    open_positions: int
    closed_positions: int
    winning_positions: int
    losing_positions: int
    flat_positions: int
    total_realized_pnl: float
    total_unrealized_pnl: float
    total_pnl: float
    win_rate: float | None
    average_return_pct: float | None
    best_return_pct: float | None
    worst_return_pct: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PaperTradePerformanceReport:
    generated_at: str
    summary: PerformanceSummary
    positions: tuple[PositionMark, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "summary": self.summary.to_dict(),
            "positions": [
                position.to_dict()
                for position in self.positions
            ],
            "warnings": list(self.warnings),
        }
