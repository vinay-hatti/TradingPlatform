from __future__ import annotations

from math import isfinite
from typing import Any, Iterable

from .paper_trade_performance_profile import (
    PaperTradePerformanceReport,
    PerformanceSummary,
    PositionMark,
    utc_now_iso,
)


class PaperTradePerformanceService:
    def evaluate(
        self,
        lifecycle_payloads: Iterable[dict[str, Any]],
        mark_records: Iterable[dict[str, Any]],
    ) -> PaperTradePerformanceReport:
        mark_index = self._build_mark_index(mark_records)
        positions: list[PositionMark] = []
        report_warnings: list[str] = []

        for lifecycle in lifecycle_payloads:
            if not isinstance(lifecycle, dict):
                report_warnings.append(
                    "INVALID_LIFECYCLE_PAYLOAD_SKIPPED"
                )
                continue

            position = lifecycle.get("position")
            if not isinstance(position, dict):
                continue

            positions.append(
                self._evaluate_position(
                    position,
                    mark_index,
                )
            )

        positions.sort(
            key=lambda item: (
                item.status != "OPEN",
                item.symbol,
                item.position_id,
            )
        )

        summary = self._summary(positions)
        if not positions:
            report_warnings.append(
                "NO_PAPER_POSITIONS_FOUND"
            )

        return PaperTradePerformanceReport(
            generated_at=utc_now_iso(),
            summary=summary,
            positions=tuple(positions),
            warnings=tuple(dict.fromkeys(report_warnings)),
        )

    def _evaluate_position(
        self,
        position: dict[str, Any],
        mark_index: dict[str, dict[str, Any]],
    ) -> PositionMark:
        position_id = str(
            position.get("position_id", "")
        )
        symbol = str(
            position.get("symbol", "")
        ).upper()
        strategy_id = str(
            position.get("strategy_id", "")
        )
        quantity = int(
            self._number(position.get("quantity")) or 1
        )
        entry_debit = self._number(
            position.get("entry_debit")
        )
        current_status = str(
            position.get("status", "OPEN")
        ).upper()

        mark = mark_index.get(position_id)
        warnings: list[str] = []
        current_debit: float | None = None
        exit_debit: float | None = None
        realized_pnl: float | None = self._optional_number(
            position.get("realized_pnl")
        )
        unrealized_pnl: float | None = self._optional_number(
            position.get("unrealized_pnl")
        )
        closed_at = self._text(
            position.get("closed_at")
        )
        status = current_status

        if mark is None:
            warnings.append("POSITION_MARK_NOT_FOUND")
        else:
            marked_status = str(
                mark.get("status", current_status)
            ).upper()
            current_debit = self._first_number(
                mark,
                (
                    "current_debit",
                    "mark_debit",
                    "strategy_debit",
                ),
            )
            exit_debit = self._first_number(
                mark,
                ("exit_debit", "close_debit"),
            )

            if marked_status == "CLOSED":
                status = "CLOSED"
                if exit_debit is None:
                    exit_debit = current_debit
                if exit_debit is None:
                    warnings.append(
                        "EXIT_DEBIT_REQUIRED_FOR_CLOSED_POSITION"
                    )
                else:
                    realized_pnl = (
                        (exit_debit - entry_debit)
                        * quantity
                        * 100.0
                    )
                    unrealized_pnl = 0.0
                closed_at = (
                    self._first_text(
                        mark,
                        ("closed_at", "marked_at"),
                    )
                    or utc_now_iso()
                )
            else:
                status = "OPEN"
                if current_debit is None:
                    warnings.append(
                        "CURRENT_DEBIT_REQUIRED_FOR_OPEN_POSITION"
                    )
                else:
                    unrealized_pnl = (
                        (current_debit - entry_debit)
                        * quantity
                        * 100.0
                    )

        pnl_for_return = (
            realized_pnl
            if status == "CLOSED"
            else unrealized_pnl
        )
        capital_at_risk = entry_debit * quantity * 100.0
        return_pct = (
            pnl_for_return / capital_at_risk
            if (
                pnl_for_return is not None
                and capital_at_risk > 0
            )
            else None
        )

        return PositionMark(
            position_id=position_id,
            symbol=symbol,
            strategy_id=strategy_id,
            status=status,
            quantity=quantity,
            entry_debit=entry_debit,
            current_debit=current_debit,
            exit_debit=exit_debit,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=realized_pnl,
            return_pct=return_pct,
            marked_at=(
                self._first_text(
                    mark or {},
                    ("marked_at",),
                )
                or utc_now_iso()
            ),
            closed_at=closed_at,
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def _summary(
        self,
        positions: list[PositionMark],
    ) -> PerformanceSummary:
        realized = sum(
            item.realized_pnl or 0.0
            for item in positions
        )
        unrealized = sum(
            item.unrealized_pnl or 0.0
            for item in positions
        )
        returns = [
            item.return_pct
            for item in positions
            if item.return_pct is not None
        ]
        closed = [
            item
            for item in positions
            if item.status == "CLOSED"
        ]
        winning = sum(
            1
            for item in closed
            if (item.realized_pnl or 0.0) > 0
        )
        losing = sum(
            1
            for item in closed
            if (item.realized_pnl or 0.0) < 0
        )
        flat = sum(
            1
            for item in closed
            if (item.realized_pnl or 0.0) == 0
        )

        return PerformanceSummary(
            total_positions=len(positions),
            open_positions=sum(
                1
                for item in positions
                if item.status == "OPEN"
            ),
            closed_positions=len(closed),
            winning_positions=winning,
            losing_positions=losing,
            flat_positions=flat,
            total_realized_pnl=round(realized, 8),
            total_unrealized_pnl=round(
                unrealized,
                8,
            ),
            total_pnl=round(
                realized + unrealized,
                8,
            ),
            win_rate=(
                winning / len(closed)
                if closed
                else None
            ),
            average_return_pct=(
                sum(returns) / len(returns)
                if returns
                else None
            ),
            best_return_pct=(
                max(returns)
                if returns
                else None
            ),
            worst_return_pct=(
                min(returns)
                if returns
                else None
            ),
        )

    def _build_mark_index(
        self,
        records: Iterable[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        index: dict[str, dict[str, Any]] = {}
        for record in records:
            if not isinstance(record, dict):
                continue
            position_id = self._first_text(
                record,
                ("position_id",),
            )
            if position_id:
                index[position_id] = record
        return index

    def _first_text(
        self,
        payload: dict[str, Any],
        aliases: tuple[str, ...],
    ) -> str | None:
        for alias in aliases:
            value = payload.get(alias)
            if value not in (None, ""):
                return str(value).strip()
        return None

    def _first_number(
        self,
        payload: dict[str, Any],
        aliases: tuple[str, ...],
    ) -> float | None:
        for alias in aliases:
            value = self._optional_number(
                payload.get(alias)
            )
            if value is not None:
                return value
        return None

    def _text(self, value: Any) -> str | None:
        if value in (None, ""):
            return None
        return str(value).strip()

    def _optional_number(
        self,
        value: Any,
    ) -> float | None:
        if value in (None, ""):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if isfinite(number) else None

    def _number(self, value: Any) -> float:
        return self._optional_number(value) or 0.0
