from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable

from .lifecycle_profile import (
    PositionLifecycleEvent,
    PositionLifecycleJournal,
    PositionReconciliationException,
    PositionReconciliationResult,
)
from .profile import utc_now_iso
from .serialization import read_json, write_json_atomic
from .service import PortfolioRegistryService


class PositionLifecycleReconciliationService:
    def __init__(
        self,
        registry_service: PortfolioRegistryService,
        journal_file: Path,
    ) -> None:
        self.registry_service = registry_service
        self.journal_file = journal_file

    def load_journal(self) -> PositionLifecycleJournal:
        registry = self.registry_service.load_snapshot()
        payload = read_json(self.journal_file)
        if not payload:
            return PositionLifecycleJournal(portfolio_id=registry.account.portfolio_id)
        return PositionLifecycleJournal(
            portfolio_id=str(payload.get("portfolio_id", registry.account.portfolio_id)),
            events=tuple(PositionLifecycleEvent(**item) for item in payload.get("events", [])),
            exceptions=tuple(
                PositionReconciliationException(**item)
                for item in payload.get("exceptions", [])
            ),
            generated_at=str(payload.get("generated_at", utc_now_iso())),
        )

    def reconcile_lifecycle_artifact(
        self,
        artifact: Path,
        *,
        auto_repair: bool = True,
    ) -> PositionReconciliationResult:
        payload = read_json(artifact)
        order = payload.get("order") or {}
        source = payload.get("position") or {}
        position_id = str(source.get("position_id") or "")
        symbol = str(source.get("symbol") or order.get("symbol") or "").upper()
        strategy_id = str(
            source.get("strategy_id") or order.get("strategy_id") or ""
        ).upper()
        source_status = str(source.get("status") or order.get("status") or "UNKNOWN").upper()
        if not position_id or not symbol or not strategy_id:
            raise ValueError("lifecycle artifact lacks position identity")
        return self._reconcile_position_state(
            artifact=artifact,
            source_type="PAPER_TRADE_LIFECYCLE",
            position_id=position_id,
            symbol=symbol,
            strategy_id=strategy_id,
            source_status=source_status,
            current_price=self._first_float(
                source.get("current_debit"), source.get("entry_debit")
            ),
            exit_price=self._first_float(
                source.get("exit_debit"), order.get("average_fill_debit")
                if source_status == "CLOSED" else None,
            ),
            details={"order_status": order.get("status"), "source_position": source},
            auto_repair=auto_repair,
        )

    def reconcile_performance_artifact(
        self,
        artifact: Path,
        *,
        auto_repair: bool = True,
    ) -> tuple[PositionReconciliationResult, ...]:
        payload = read_json(artifact)
        results = []
        for source in payload.get("positions", []):
            position_id = str(source.get("position_id") or "")
            symbol = str(source.get("symbol") or "").upper()
            strategy_id = str(source.get("strategy_id") or "").upper()
            if not position_id or not symbol or not strategy_id:
                continue
            results.append(self._reconcile_position_state(
                artifact=artifact,
                source_type="PAPER_TRADE_PERFORMANCE",
                position_id=position_id,
                symbol=symbol,
                strategy_id=strategy_id,
                source_status=str(source.get("status", "OPEN")).upper(),
                current_price=self._first_float(source.get("current_debit")),
                exit_price=self._first_float(source.get("exit_debit")),
                details={"source_position": source},
                auto_repair=auto_repair,
            ))
        return tuple(results)

    def reconcile_dashboard_directory(
        self,
        dashboard_dir: Path,
        *,
        auto_repair: bool = True,
    ) -> tuple[PositionReconciliationResult, ...]:
        results: list[PositionReconciliationResult] = []
        lifecycle_dir = dashboard_dir / "paper_trade"
        for artifact in sorted(lifecycle_dir.glob("*_lifecycle.json")):
            results.append(self.reconcile_lifecycle_artifact(
                artifact, auto_repair=auto_repair
            ))
        performance_dir = dashboard_dir / "performance"
        for artifact in sorted(performance_dir.glob("*.json")):
            results.extend(self.reconcile_performance_artifact(
                artifact, auto_repair=auto_repair
            ))
        results.extend(self.audit_registry_identity())
        return tuple(results)

    def audit_registry_identity(self) -> tuple[PositionReconciliationResult, ...]:
        registry = self.registry_service.load_snapshot()
        results: list[PositionReconciliationResult] = []
        by_position: dict[str, list[Any]] = {}
        by_strategy: dict[tuple[str, str], list[Any]] = {}
        for position in registry.positions:
            by_position.setdefault(position.position_id, []).append(position)
            if position.status == "OPEN":
                by_strategy.setdefault((position.symbol, position.strategy_id), []).append(position)

        for position_id, records in by_position.items():
            if len(records) > 1:
                results.append(self._identity_exception(
                    records[0], "DUPLICATE_POSITION_ID",
                    f"Position id {position_id} appears {len(records)} times",
                ))
        for _, records in by_strategy.items():
            if len(records) > 1:
                results.append(self._identity_exception(
                    records[0], "DUPLICATE_OPEN_STRATEGY",
                    "Multiple open positions share symbol and strategy identity",
                ))
        return tuple(results)

    def resolve_exception(self, exception_id: str, resolution: str) -> PositionLifecycleJournal:
        journal = self.load_journal()
        found = False
        exceptions = []
        for item in journal.exceptions:
            if item.exception_id == exception_id:
                exceptions.append(replace(item, resolved=True, resolution=resolution))
                found = True
            else:
                exceptions.append(item)
        if not found:
            raise KeyError(exception_id)
        updated = PositionLifecycleJournal(
            portfolio_id=journal.portfolio_id,
            events=journal.events,
            exceptions=tuple(exceptions),
        )
        self._write(updated)
        return updated

    def _reconcile_position_state(
        self,
        *,
        artifact: Path,
        source_type: str,
        position_id: str,
        symbol: str,
        strategy_id: str,
        source_status: str,
        current_price: float | None,
        exit_price: float | None,
        details: dict[str, Any],
        auto_repair: bool,
    ) -> PositionReconciliationResult:
        fingerprint = self._fingerprint({
            "source_type": source_type,
            "position_id": position_id,
            "symbol": symbol,
            "strategy_id": strategy_id,
            "source_status": source_status,
            "current_price": current_price,
            "exit_price": exit_price,
            "details": details,
        })
        event_id = self._stable_id("EVENT", fingerprint)
        journal = self.load_journal()
        if any(item.event_id == event_id for item in journal.events):
            return PositionReconciliationResult(
                source_artifact=str(artifact), source_type=source_type,
                status="DUPLICATE_EVENT", position_id=position_id,
                symbol=symbol, strategy_id=strategy_id, duplicate=True,
            )

        registry = self.registry_service.load_snapshot()
        target = next((p for p in registry.positions if p.position_id == position_id), None)
        exception_ids: list[str] = []
        repaired = False
        action = "NO_CHANGE"
        before = "MISSING" if target is None else target.status
        after = before

        if target is None:
            exception_ids.append(self._append_exception(
                journal, position_id, symbol, strategy_id,
                "SOURCE_POSITION_NOT_IN_REGISTRY", "HIGH",
                "Source position has no matching portfolio registry record",
                artifact, details,
            ))
            journal = self.load_journal()
            action = "OPERATOR_REVIEW"
        elif target.symbol != symbol or target.strategy_id != strategy_id:
            exception_ids.append(self._append_exception(
                journal, position_id, symbol, strategy_id,
                "POSITION_IDENTITY_MISMATCH", "CRITICAL",
                "Position id matches but symbol or strategy identity conflicts",
                artifact,
                {"registry_symbol": target.symbol,
                 "registry_strategy_id": target.strategy_id, **details},
            ))
            journal = self.load_journal()
            action = "BLOCKED_IDENTITY_CONFLICT"
        elif source_status == "CLOSED" and target.status == "OPEN":
            if auto_repair and exit_price is not None and exit_price >= 0:
                self.registry_service.close_position(position_id, exit_price)
                repaired = True
                action = "CLOSED_REGISTRY_POSITION"
                after = "CLOSED"
            else:
                exception_ids.append(self._append_exception(
                    journal, position_id, symbol, strategy_id,
                    "SOURCE_CLOSED_REGISTRY_OPEN", "HIGH",
                    "Source is closed while registry remains open and no safe exit price is available",
                    artifact, details,
                ))
                journal = self.load_journal()
                action = "OPERATOR_REVIEW"
        elif source_status == "OPEN" and target.status == "CLOSED":
            exception_ids.append(self._append_exception(
                journal, position_id, symbol, strategy_id,
                "SOURCE_OPEN_REGISTRY_CLOSED", "HIGH",
                "Source reports open after portfolio registry closure",
                artifact, details,
            ))
            journal = self.load_journal()
            action = "OPERATOR_REVIEW"
        elif source_status == "OPEN" and target.status == "OPEN" and current_price is not None:
            if auto_repair and abs(target.current_price - current_price) > 1e-9:
                self.registry_service.mark_position(position_id, current_price)
                repaired = True
                action = "UPDATED_MARK"
            else:
                action = "MARK_ALREADY_CURRENT"
            after = "OPEN"
        else:
            action = "STATE_ALREADY_ALIGNED"
            after = target.status

        journal = self.load_journal()
        event = PositionLifecycleEvent(
            event_id=event_id,
            portfolio_id=journal.portfolio_id,
            position_id=position_id,
            symbol=symbol,
            strategy_id=strategy_id,
            event_type="RECONCILIATION",
            source_status=source_status,
            registry_status_before=before,
            registry_status_after=after,
            action=action,
            source_artifact=str(artifact),
            source_fingerprint=fingerprint,
            details=details,
        )
        updated = PositionLifecycleJournal(
            portfolio_id=journal.portfolio_id,
            events=journal.events + (event,),
            exceptions=journal.exceptions,
        )
        self._write(updated)
        return PositionReconciliationResult(
            source_artifact=str(artifact), source_type=source_type,
            status="RECONCILED" if not exception_ids else "EXCEPTION",
            position_id=position_id, symbol=symbol, strategy_id=strategy_id,
            action=action, repaired=repaired,
            exception_ids=tuple(exception_ids),
        )

    def _identity_exception(self, position: Any, exception_type: str, message: str) -> PositionReconciliationResult:
        journal = self.load_journal()
        exception_id = self._stable_id(
            "EXCEPTION", exception_type, position.position_id, message
        )
        if not any(item.exception_id == exception_id for item in journal.exceptions):
            exception = PositionReconciliationException(
                exception_id=exception_id,
                portfolio_id=journal.portfolio_id,
                position_id=position.position_id,
                symbol=position.symbol,
                strategy_id=position.strategy_id,
                exception_type=exception_type,
                severity="CRITICAL",
                message=message,
                source_artifact=str(self.registry_service.registry_file),
            )
            self._write(PositionLifecycleJournal(
                portfolio_id=journal.portfolio_id,
                events=journal.events,
                exceptions=journal.exceptions + (exception,),
            ))
        return PositionReconciliationResult(
            source_artifact=str(self.registry_service.registry_file),
            source_type="REGISTRY_IDENTITY_AUDIT",
            status="EXCEPTION", position_id=position.position_id,
            symbol=position.symbol, strategy_id=position.strategy_id,
            action="BLOCKED_IDENTITY_CONFLICT",
            exception_ids=(exception_id,),
        )

    def _append_exception(
        self,
        journal: PositionLifecycleJournal,
        position_id: str,
        symbol: str,
        strategy_id: str,
        exception_type: str,
        severity: str,
        message: str,
        artifact: Path,
        details: dict[str, Any],
    ) -> str:
        exception_id = self._stable_id(
            "EXCEPTION", exception_type, position_id, str(artifact),
            self._fingerprint(details),
        )
        if any(item.exception_id == exception_id for item in journal.exceptions):
            return exception_id
        exception = PositionReconciliationException(
            exception_id=exception_id,
            portfolio_id=journal.portfolio_id,
            position_id=position_id,
            symbol=symbol,
            strategy_id=strategy_id,
            exception_type=exception_type,
            severity=severity,
            message=message,
            source_artifact=str(artifact),
            details=details,
        )
        self._write(PositionLifecycleJournal(
            portfolio_id=journal.portfolio_id,
            events=journal.events,
            exceptions=journal.exceptions + (exception,),
        ))
        return exception_id

    def _write(self, journal: PositionLifecycleJournal) -> None:
        write_json_atomic(self.journal_file, journal.to_dict())

    @staticmethod
    def _first_float(*values: Any) -> float | None:
        for value in values:
            if value is not None and value != "":
                return float(value)
        return None

    @staticmethod
    def _fingerprint(payload: Any) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    @staticmethod
    def _stable_id(*parts: str) -> str:
        raw = "|".join(str(part) for part in parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24].upper()
