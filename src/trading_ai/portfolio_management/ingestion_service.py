from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable

from .ingestion_profile import (
    PortfolioIngestionResult,
    PortfolioIntakeRecord,
    PortfolioIntakeSnapshot,
)
from .profile import utc_now_iso
from .serialization import read_json, write_json_atomic
from .service import PortfolioRegistryService


class PortfolioArtifactIngestionService:
    """Imports Milestone 35 decisions, executions, and marks into Milestone 36."""

    def __init__(
        self,
        registry_service: PortfolioRegistryService,
        intake_file: Path,
    ) -> None:
        self.registry_service = registry_service
        self.intake_file = intake_file

    def load_intake(self) -> PortfolioIntakeSnapshot:
        portfolio_id = self.registry_service.load_snapshot().account.portfolio_id
        if not self.intake_file.exists():
            return PortfolioIntakeSnapshot(portfolio_id=portfolio_id, records=())
        payload = read_json(self.intake_file)
        records = tuple(
            PortfolioIntakeRecord(
                intake_id=str(item["intake_id"]),
                portfolio_id=str(item.get("portfolio_id", portfolio_id)),
                symbol=str(item.get("symbol", "")).upper(),
                direction=str(item.get("direction", "")).upper(),
                strategy_id=str(item.get("strategy_id", "")).upper(),
                strategy_type=str(item.get("strategy_type", "UNKNOWN")).upper(),
                decision=str(item.get("decision", "UNKNOWN")).upper(),
                intake_status=str(item.get("intake_status", "UNKNOWN")).upper(),
                paper_trade_ready=bool(item.get("paper_trade_ready", False)),
                execution_status=str(item.get("execution_status", "UNKNOWN")).upper(),
                estimated_entry_price=self._optional_float(item.get("estimated_entry_price")),
                maximum_loss=self._optional_float(item.get("maximum_loss")),
                maximum_profit=self._optional_float(item.get("maximum_profit")),
                reward_risk_ratio=self._optional_float(item.get("reward_risk_ratio")),
                institutional_score=self._optional_float(item.get("institutional_score")),
                source_artifact=str(item.get("source_artifact", "")),
                source_fingerprint=str(item.get("source_fingerprint", "")),
                created_at=str(item.get("created_at", utc_now_iso())),
                updated_at=str(item.get("updated_at", utc_now_iso())),
                warnings=tuple(str(x) for x in item.get("warnings", [])),
                metadata=dict(item.get("metadata", {})),
            )
            for item in payload.get("records", [])
        )
        return PortfolioIntakeSnapshot(portfolio_id=portfolio_id, records=records)

    def ingest_institutional_decision(self, artifact: Path) -> PortfolioIngestionResult:
        payload = read_json(artifact)
        symbol = str(payload.get("symbol", "")).upper()
        decision = str(payload.get("decision", "")).upper()
        strategy = payload.get("selected_strategy") or {}
        paper_payload = payload.get("paper_trade_payload") or {}
        strategy_id = str(
            payload.get("selected_strategy_id")
            or strategy.get("strategy_id")
            or paper_payload.get("strategy_id")
            or ""
        ).upper()
        if not symbol or not strategy_id:
            raise ValueError("institutional decision is missing symbol or strategy_id")

        fingerprint = self._fingerprint(payload)
        snapshot = self.load_intake()
        existing = next(
            (record for record in snapshot.records if record.source_fingerprint == fingerprint),
            None,
        )
        if existing is not None:
            return PortfolioIngestionResult(
                source_type="INSTITUTIONAL_DECISION",
                source_artifact=str(artifact),
                status="DUPLICATE",
                symbol=symbol,
                strategy_id=strategy_id,
                intake_id=existing.intake_id,
                duplicate=True,
            )

        paper_ready = bool(payload.get("paper_trade_ready", False))
        execution_status = str(
            paper_payload.get("execution_status", "UNKNOWN")
        ).upper()
        if decision != "APPROVE":
            intake_status = "REJECTED"
        elif paper_ready and execution_status not in {"QUOTE_REFRESH_REQUIRED", "BLOCKED"}:
            intake_status = "READY_FOR_EXECUTION"
        elif execution_status == "QUOTE_REFRESH_REQUIRED":
            intake_status = "QUOTE_REFRESH_REQUIRED"
        else:
            intake_status = "APPROVED_PENDING_EXECUTION"

        entry = paper_payload.get("estimated_debit")
        if entry is None:
            entry = paper_payload.get("estimated_credit")
        if entry is None:
            entry = strategy.get("debit")
        if entry is None:
            entry = strategy.get("credit")

        now = utc_now_iso()
        intake_id = self._stable_id("INTAKE", symbol, strategy_id, fingerprint)
        record = PortfolioIntakeRecord(
            intake_id=intake_id,
            portfolio_id=snapshot.portfolio_id,
            symbol=symbol,
            direction=str(payload.get("direction", strategy.get("direction", ""))).upper(),
            strategy_id=strategy_id,
            strategy_type=str(
                paper_payload.get("strategy_type")
                or strategy.get("strategy_type")
                or "UNKNOWN"
            ).upper(),
            decision=decision,
            intake_status=intake_status,
            paper_trade_ready=paper_ready,
            execution_status=execution_status,
            estimated_entry_price=self._optional_float(entry),
            maximum_loss=self._optional_float(
                paper_payload.get("max_loss", strategy.get("max_loss"))
            ),
            maximum_profit=self._optional_float(
                paper_payload.get("max_profit", strategy.get("max_profit"))
            ),
            reward_risk_ratio=self._optional_float(
                paper_payload.get(
                    "reward_risk_ratio", strategy.get("reward_risk_ratio")
                )
            ),
            institutional_score=self._optional_float(strategy.get("institutional_score")),
            source_artifact=str(artifact),
            source_fingerprint=fingerprint,
            created_at=now,
            updated_at=now,
            warnings=tuple(str(x) for x in payload.get("warnings", [])),
            metadata={
                "policy": payload.get("policy", {}),
                "selected_strategy": strategy,
                "paper_trade_payload": paper_payload,
            },
        )
        updated = PortfolioIntakeSnapshot(
            portfolio_id=snapshot.portfolio_id,
            records=tuple(snapshot.records) + (record,),
        )
        self._write_intake(updated)
        return PortfolioIngestionResult(
            source_type="INSTITUTIONAL_DECISION",
            source_artifact=str(artifact),
            status=intake_status,
            symbol=symbol,
            strategy_id=strategy_id,
            intake_id=intake_id,
            imported=True,
            warnings=record.warnings,
        )

    def ingest_paper_trade_lifecycle(self, artifact: Path) -> PortfolioIngestionResult:
        payload = read_json(artifact)
        order = payload.get("order") or {}
        position = payload.get("position") or {}
        symbol = str(position.get("symbol") or order.get("symbol") or "").upper()
        strategy_id = str(
            position.get("strategy_id") or order.get("strategy_id") or ""
        ).upper()
        position_id = str(position.get("position_id") or "")
        if not symbol or not strategy_id or not position_id:
            raise ValueError("paper lifecycle is missing symbol, strategy_id, or position_id")
        if str(order.get("status", "")).upper() != "FILLED":
            return PortfolioIngestionResult(
                source_type="PAPER_TRADE_LIFECYCLE",
                source_artifact=str(artifact),
                status="SKIPPED_NOT_FILLED",
                symbol=symbol,
                strategy_id=strategy_id,
                position_id=position_id,
                warnings=("ORDER_NOT_FILLED",),
            )
        if str(position.get("status", "")).upper() != "OPEN":
            return PortfolioIngestionResult(
                source_type="PAPER_TRADE_LIFECYCLE",
                source_artifact=str(artifact),
                status="SKIPPED_NOT_OPEN",
                symbol=symbol,
                strategy_id=strategy_id,
                position_id=position_id,
                warnings=("POSITION_NOT_OPEN",),
            )

        registry = self.registry_service.load_snapshot()
        if any(item.position_id == position_id for item in registry.positions):
            self._mark_intake_executed(strategy_id, position_id)
            return PortfolioIngestionResult(
                source_type="PAPER_TRADE_LIFECYCLE",
                source_artifact=str(artifact),
                status="DUPLICATE",
                symbol=symbol,
                strategy_id=strategy_id,
                position_id=position_id,
                duplicate=True,
            )

        quantity = int(position.get("quantity") or order.get("quantity") or 1)
        entry_price = float(
            position.get("entry_debit")
            or order.get("average_fill_debit")
            or order.get("limit_debit")
            or 0.0
        )
        if entry_price <= 0:
            raise ValueError("paper lifecycle does not contain a positive fill price")
        multiplier = self.registry_service.policy.contract_multiplier
        capital_committed = round(entry_price * quantity * multiplier, 2)
        max_loss = self._scaled(position.get("max_loss"), quantity, multiplier)
        max_profit = self._scaled(position.get("max_profit"), quantity, multiplier)

        updated = self.registry_service.register_position(
            position_id=position_id,
            symbol=symbol,
            strategy_id=strategy_id,
            strategy_type=str(
                position.get("strategy_type") or order.get("strategy_type") or "UNKNOWN"
            ),
            direction=str(position.get("direction") or order.get("direction") or ""),
            quantity=quantity,
            entry_price=entry_price,
            capital_committed=capital_committed,
            maximum_loss=max_loss,
            maximum_profit=max_profit,
            source_artifact=str(artifact),
            metadata={
                "order_id": order.get("order_id"),
                "idempotency_key": order.get("idempotency_key"),
                "opened_at_source": position.get("opened_at"),
                "breakeven": position.get("breakeven"),
                "reward_risk_ratio": position.get("reward_risk_ratio"),
                "legs": position.get("legs", order.get("legs", [])),
                "source": "M35_PHASE5_PAPER_TRADE_LIFECYCLE",
            },
        )
        self._mark_intake_executed(strategy_id, position_id)
        imported = next(item for item in updated.positions if item.position_id == position_id)
        return PortfolioIngestionResult(
            source_type="PAPER_TRADE_LIFECYCLE",
            source_artifact=str(artifact),
            status="POSITION_IMPORTED",
            symbol=symbol,
            strategy_id=strategy_id,
            position_id=imported.position_id,
            imported=True,
        )

    def ingest_performance(self, artifact: Path) -> tuple[PortfolioIngestionResult, ...]:
        payload = read_json(artifact)
        results: list[PortfolioIngestionResult] = []
        for source_position in payload.get("positions", []):
            position_id = str(source_position.get("position_id") or "")
            symbol = str(source_position.get("symbol") or "").upper()
            strategy_id = str(source_position.get("strategy_id") or "").upper()
            current_price = source_position.get("current_debit")
            registry = self.registry_service.load_snapshot()
            target = next(
                (item for item in registry.positions if item.position_id == position_id),
                None,
            )
            if target is None:
                results.append(PortfolioIngestionResult(
                    source_type="PAPER_TRADE_PERFORMANCE",
                    source_artifact=str(artifact),
                    status="POSITION_NOT_FOUND",
                    symbol=symbol,
                    strategy_id=strategy_id,
                    position_id=position_id,
                    warnings=("IMPORT_LIFECYCLE_BEFORE_PERFORMANCE",),
                ))
                continue
            source_status = str(source_position.get("status", "OPEN")).upper()
            if source_status == "CLOSED" and source_position.get("exit_debit") is not None:
                if target.status == "CLOSED":
                    status = "DUPLICATE_CLOSED_MARK"
                    duplicate = True
                else:
                    self.registry_service.close_position(
                        position_id, float(source_position["exit_debit"])
                    )
                    status = "POSITION_CLOSED"
                    duplicate = False
                results.append(PortfolioIngestionResult(
                    source_type="PAPER_TRADE_PERFORMANCE",
                    source_artifact=str(artifact),
                    status=status,
                    symbol=symbol,
                    strategy_id=strategy_id,
                    position_id=position_id,
                    imported=not duplicate,
                    duplicate=duplicate,
                    marked=not duplicate,
                ))
                continue
            if current_price is None:
                results.append(PortfolioIngestionResult(
                    source_type="PAPER_TRADE_PERFORMANCE",
                    source_artifact=str(artifact),
                    status="SKIPPED_MISSING_MARK",
                    symbol=symbol,
                    strategy_id=strategy_id,
                    position_id=position_id,
                    warnings=("CURRENT_DEBIT_MISSING",),
                ))
                continue
            self.registry_service.mark_position(position_id, float(current_price))
            results.append(PortfolioIngestionResult(
                source_type="PAPER_TRADE_PERFORMANCE",
                source_artifact=str(artifact),
                status="POSITION_MARKED",
                symbol=symbol,
                strategy_id=strategy_id,
                position_id=position_id,
                marked=True,
            ))
        return tuple(results)

    def ingest_dashboard_directory(self, dashboard_dir: Path) -> tuple[PortfolioIngestionResult, ...]:
        results: list[PortfolioIngestionResult] = []
        decision_dir = dashboard_dir / "institutional_decision"
        lifecycle_dir = dashboard_dir / "paper_trade"
        performance_file = dashboard_dir / "performance" / "paper_trade_performance.json"
        for path in sorted(decision_dir.glob("*_institutional_decision.json")):
            results.append(self.ingest_institutional_decision(path))
        for path in sorted(lifecycle_dir.glob("*_lifecycle.json")):
            results.append(self.ingest_paper_trade_lifecycle(path))
        if performance_file.exists():
            results.extend(self.ingest_performance(performance_file))
        return tuple(results)

    def _mark_intake_executed(self, strategy_id: str, position_id: str) -> None:
        snapshot = self.load_intake()
        now = utc_now_iso()
        changed = False
        records = []
        for record in snapshot.records:
            if record.strategy_id != strategy_id:
                records.append(record)
                continue
            metadata = dict(record.metadata)
            metadata["portfolio_position_id"] = position_id
            records.append(replace(
                record,
                intake_status="EXECUTED",
                execution_status="FILLED",
                updated_at=now,
                metadata=metadata,
            ))
            changed = True
        if changed:
            self._write_intake(PortfolioIntakeSnapshot(
                portfolio_id=snapshot.portfolio_id,
                records=tuple(records),
            ))

    def _write_intake(self, snapshot: PortfolioIntakeSnapshot) -> None:
        write_json_atomic(self.intake_file, snapshot.to_dict())

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None or value == "":
            return None
        return float(value)

    @staticmethod
    def _scaled(value: Any, quantity: int, multiplier: float) -> float | None:
        if value is None or value == "":
            return None
        return round(float(value) * quantity * multiplier, 2)

    @staticmethod
    def _fingerprint(payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _stable_id(prefix: str, *parts: str) -> str:
        digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16].upper()
        return f"{prefix}-{digest}"
