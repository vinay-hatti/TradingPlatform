from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from .profile import PortfolioPositionRecord, PortfolioRegistrySnapshot, utc_now_iso
from .serialization import read_json, write_json_atomic
from .service import PortfolioRegistryService
from .snapshot_profile import (
    ExposureBucket,
    PortfolioAuditHistory,
    PortfolioAuditRecord,
    PortfolioExposureView,
    PortfolioSnapshotArtifact,
)


class PortfolioSnapshotService:
    def __init__(
        self,
        registry_service: PortfolioRegistryService,
        snapshot_directory: Path,
        exposure_file: Path,
        audit_file: Path,
    ) -> None:
        self.registry_service = registry_service
        self.snapshot_directory = snapshot_directory
        self.exposure_file = exposure_file
        self.audit_file = audit_file

    def build_exposure_view(self, snapshot: PortfolioRegistrySnapshot | None = None) -> PortfolioExposureView:
        snapshot = snapshot or self.registry_service.load_snapshot()
        open_positions = tuple(item for item in snapshot.positions if item.status == "OPEN")
        committed = float(snapshot.total_capital_committed)
        nlv = float(snapshot.net_liquidation_value)
        denominator = committed if committed > 0 else 1.0

        by_symbol = self._aggregate(open_positions, lambda p: p.symbol, denominator)
        by_sector = self._aggregate(open_positions, lambda p: p.sector or "UNKNOWN", denominator)
        by_strategy = self._aggregate(open_positions, lambda p: p.strategy_type or "UNKNOWN", denominator)
        by_direction = self._aggregate(open_positions, lambda p: p.direction or "UNKNOWN", denominator)

        warnings: list[str] = []
        largest_symbol = max((item.capital_pct for item in by_symbol), default=0.0)
        largest_sector = max((item.capital_pct for item in by_sector), default=0.0)
        if largest_symbol > 25.0:
            warnings.append("SYMBOL_CONCENTRATION_ABOVE_25_PCT")
        if largest_sector > 40.0:
            warnings.append("SECTOR_CONCENTRATION_ABOVE_40_PCT")
        if nlv <= 0:
            warnings.append("NON_POSITIVE_NET_LIQUIDATION_VALUE")

        return PortfolioExposureView(
            portfolio_id=snapshot.account.portfolio_id,
            generated_at=utc_now_iso(),
            net_liquidation_value=round(nlv, 2),
            cash_balance=round(snapshot.cash_balance, 2),
            capital_committed=round(committed, 2),
            capital_utilization_pct=round((committed / nlv * 100.0) if nlv else 0.0, 4),
            cash_pct=round((snapshot.cash_balance / nlv * 100.0) if nlv else 0.0, 4),
            open_position_count=snapshot.open_position_count,
            total_unrealized_pnl=round(snapshot.total_unrealized_pnl, 2),
            total_realized_pnl=round(snapshot.total_realized_pnl, 2),
            aggregate_delta=round(sum(p.delta for p in open_positions), 6),
            aggregate_gamma=round(sum(p.gamma for p in open_positions), 6),
            aggregate_theta=round(sum(p.theta for p in open_positions), 6),
            aggregate_vega=round(sum(p.vega for p in open_positions), 6),
            aggregate_rho=round(sum(p.rho for p in open_positions), 6),
            largest_symbol_pct=round(largest_symbol, 4),
            largest_sector_pct=round(largest_sector, 4),
            by_symbol=by_symbol,
            by_sector=by_sector,
            by_strategy=by_strategy,
            by_direction=by_direction,
            warnings=tuple(warnings),
        )

    def create_snapshot(self, event_type: str = "PORTFOLIO_SNAPSHOT") -> PortfolioSnapshotArtifact:
        registry = self.registry_service.load_snapshot()
        registry_payload = registry.to_dict()
        fingerprint = self._fingerprint(registry_payload)
        generated_at = utc_now_iso()
        snapshot_id = self._id("SNAPSHOT", registry.account.portfolio_id, fingerprint, generated_at)
        exposure = self.build_exposure_view(registry)
        artifact = PortfolioSnapshotArtifact(
            snapshot_id=snapshot_id,
            portfolio_id=registry.account.portfolio_id,
            generated_at=generated_at,
            registry_fingerprint=fingerprint,
            registry=registry_payload,
            exposure=exposure,
            warnings=exposure.warnings,
        )

        self.snapshot_directory.mkdir(parents=True, exist_ok=True)
        snapshot_file = self.snapshot_directory / f"{snapshot_id.lower()}.json"
        write_json_atomic(snapshot_file, artifact.to_dict())
        write_json_atomic(self.exposure_file, exposure.to_dict())
        self._append_audit(artifact, event_type, snapshot_file)
        return artifact

    def load_audit_history(self) -> PortfolioAuditHistory:
        payload = read_json(self.audit_file)
        if not payload:
            try:
                portfolio_id = self.registry_service.load_snapshot().account.portfolio_id
            except FileNotFoundError:
                portfolio_id = ""
            return PortfolioAuditHistory(portfolio_id=portfolio_id)
        return PortfolioAuditHistory(
            portfolio_id=str(payload.get("portfolio_id", "")),
            records=tuple(PortfolioAuditRecord(**item) for item in payload.get("records", [])),
            generated_at=str(payload.get("generated_at", utc_now_iso())),
        )

    def _append_audit(self, artifact: PortfolioSnapshotArtifact, event_type: str, snapshot_file: Path) -> None:
        history = self.load_audit_history()
        registry = artifact.registry
        duplicate = any(
            item.registry_fingerprint == artifact.registry_fingerprint
            and item.event_type == event_type.upper()
            for item in history.records
        )
        if duplicate:
            return
        record = PortfolioAuditRecord(
            audit_id=self._id("AUDIT", artifact.portfolio_id, artifact.snapshot_id, event_type.upper()),
            portfolio_id=artifact.portfolio_id,
            snapshot_id=artifact.snapshot_id,
            event_type=event_type.upper(),
            occurred_at=artifact.generated_at,
            registry_fingerprint=artifact.registry_fingerprint,
            open_position_count=int(registry.get("open_position_count", 0)),
            closed_position_count=int(registry.get("closed_position_count", 0)),
            cash_balance=float(registry.get("cash_balance", 0.0)),
            net_liquidation_value=float(registry.get("net_liquidation_value", 0.0)),
            capital_committed=float(registry.get("total_capital_committed", 0.0)),
            realized_pnl=float(registry.get("total_realized_pnl", 0.0)),
            unrealized_pnl=float(registry.get("total_unrealized_pnl", 0.0)),
            source_registry=str(self.registry_service.registry_file),
            metadata={"snapshot_file": str(snapshot_file)},
        )
        updated = PortfolioAuditHistory(
            portfolio_id=artifact.portfolio_id,
            records=tuple(history.records) + (record,),
        )
        write_json_atomic(self.audit_file, updated.to_dict())

    @staticmethod
    def _aggregate(
        positions: Iterable[PortfolioPositionRecord],
        key_fn,
        denominator: float,
    ) -> tuple[ExposureBucket, ...]:
        grouped: dict[str, list[PortfolioPositionRecord]] = defaultdict(list)
        for position in positions:
            grouped[str(key_fn(position)).upper()].append(position)
        rows = []
        for key, items in grouped.items():
            capital = sum(item.capital_committed for item in items)
            rows.append(ExposureBucket(
                key=key,
                position_count=len(items),
                capital_committed=round(capital, 2),
                capital_pct=round(capital / denominator * 100.0, 4),
                unrealized_pnl=round(sum(item.unrealized_pnl for item in items), 2),
                realized_pnl=round(sum(item.realized_pnl for item in items), 2),
                delta=round(sum(item.delta for item in items), 6),
                gamma=round(sum(item.gamma for item in items), 6),
                theta=round(sum(item.theta for item in items), 6),
                vega=round(sum(item.vega for item in items), 6),
                rho=round(sum(item.rho for item in items), 6),
            ))
        return tuple(sorted(rows, key=lambda item: (-item.capital_committed, item.key)))

    @staticmethod
    def _fingerprint(payload: dict) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _id(prefix: str, *parts: str) -> str:
        digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16].upper()
        return f"{prefix}-{digest}"
