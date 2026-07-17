from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .order_profile import CanonicalOrderAggregate, CanonicalOrderEvent
from .order_repository_exceptions import (
    DuplicateOrderError,
    OptimisticConcurrencyError,
    OrderNotFoundError,
)
from .order_repository_policy import OrderRepositoryPolicy
from .order_repository_profile import (
    OrderPersistenceResult,
    OrderRepositoryRecord,
)
from .order_storage_codec import checksum, record_from_dict


class JsonOrderRepository:
    """JSON repository with explicit optimistic concurrency checks."""

    def __init__(
        self,
        path: str | Path = "data/order_management/orders.json",
        policy: OrderRepositoryPolicy | None = None,
    ) -> None:
        self.path = Path(path)
        self.policy = policy or OrderRepositoryPolicy()
        self.policy.validate()

    def _ensure_parent(self) -> None:
        if self.policy.create_parent_directories:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, OrderRepositoryRecord]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return {
            aggregate_id: record_from_dict(raw)
            for aggregate_id, raw in payload.get("orders", {}).items()
        }

    def _save(self, records: dict[str, OrderRepositoryRecord]) -> None:
        self._ensure_parent()
        payload = {
            "orders": {
                aggregate_id: asdict(record)
                for aggregate_id, record in records.items()
            }
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            if self.policy.fsync_on_write:
                os.fsync(handle.fileno())
        temporary.replace(self.path)

    def get(self, aggregate_id: str) -> CanonicalOrderAggregate | None:
        record = self._load().get(aggregate_id)
        return record.aggregate if record is not None else None

    def require(self, aggregate_id: str) -> CanonicalOrderAggregate:
        aggregate = self.get(aggregate_id)
        if aggregate is None:
            raise OrderNotFoundError(f"Order aggregate not found: {aggregate_id}")
        return aggregate

    def all(self) -> tuple[CanonicalOrderAggregate, ...]:
        return tuple(
            sorted(
                (record.aggregate for record in self._load().values()),
                key=lambda aggregate: aggregate.created_at,
            )
        )

    def create(
        self,
        aggregate: CanonicalOrderAggregate,
    ) -> OrderPersistenceResult:
        records = self._load()
        existing = records.get(aggregate.aggregate_id)
        if existing is not None and self.policy.reject_duplicate_aggregate_id:
            raise DuplicateOrderError(
                f"Order aggregate already exists: {aggregate.aggregate_id}"
            )

        now = datetime.now(timezone.utc).isoformat()
        record = OrderRepositoryRecord(
            aggregate=aggregate,
            persisted_version=aggregate.version,
            created_at=now,
            updated_at=now,
            checksum=checksum(aggregate),
        )
        records[aggregate.aggregate_id] = record
        self._save(records)

        return OrderPersistenceResult(
            valid=True,
            allowed=True,
            action="CREATE",
            aggregate_id=aggregate.aggregate_id,
            expected_version=None,
            actual_version=None,
            persisted_version=aggregate.version,
            aggregate=aggregate,
            recommendation="PERSISTED",
        )

    def save(
        self,
        aggregate: CanonicalOrderAggregate,
        *,
        expected_version: int,
    ) -> OrderPersistenceResult:
        records = self._load()
        current = records.get(aggregate.aggregate_id)
        if current is None:
            raise OrderNotFoundError(
                f"Order aggregate not found: {aggregate.aggregate_id}"
            )

        actual_version = current.persisted_version
        if (
            self.policy.require_optimistic_concurrency
            and expected_version != actual_version
        ):
            raise OptimisticConcurrencyError(
                aggregate.aggregate_id,
                expected_version,
                actual_version,
            )

        if aggregate.version != actual_version + 1:
            raise OptimisticConcurrencyError(
                aggregate.aggregate_id,
                actual_version + 1,
                aggregate.version,
            )

        now = datetime.now(timezone.utc).isoformat()
        records[aggregate.aggregate_id] = OrderRepositoryRecord(
            aggregate=aggregate,
            persisted_version=aggregate.version,
            created_at=current.created_at,
            updated_at=now,
            checksum=checksum(aggregate),
            metadata=current.metadata,
        )
        self._save(records)

        return OrderPersistenceResult(
            valid=True,
            allowed=True,
            action="UPDATE",
            aggregate_id=aggregate.aggregate_id,
            expected_version=expected_version,
            actual_version=actual_version,
            persisted_version=aggregate.version,
            aggregate=aggregate,
            recommendation="PERSISTED",
        )

    def delete(
        self,
        aggregate_id: str,
        *,
        expected_version: int,
    ) -> OrderPersistenceResult:
        records = self._load()
        current = records.get(aggregate_id)
        if current is None:
            raise OrderNotFoundError(
                f"Order aggregate not found: {aggregate_id}"
            )
        if (
            self.policy.require_optimistic_concurrency
            and expected_version != current.persisted_version
        ):
            raise OptimisticConcurrencyError(
                aggregate_id,
                expected_version,
                current.persisted_version,
            )
        del records[aggregate_id]
        self._save(records)
        return OrderPersistenceResult(
            valid=True,
            allowed=True,
            action="DELETE",
            aggregate_id=aggregate_id,
            expected_version=expected_version,
            actual_version=current.persisted_version,
            persisted_version=None,
            aggregate=current.aggregate,
            recommendation="DELETED",
        )
