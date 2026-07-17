from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import asdict
from pathlib import Path

from .order_profile import CanonicalOrderEvent
from .order_repository_exceptions import AuditLedgerIntegrityError
from .order_repository_policy import OrderRepositoryPolicy
from .order_repository_profile import OrderAuditEntry
from .order_storage_codec import audit_entry_from_dict, canonical_json, checksum


class OrderAuditLedger:
    """Append-only tamper-evident audit ledger with a hash chain."""

    GENESIS_HASH = "0" * 64

    def __init__(
        self,
        path: str | Path = "data/order_management/order_audit_ledger.jsonl",
        policy: OrderRepositoryPolicy | None = None,
    ) -> None:
        self.path = Path(path)
        self.policy = policy or OrderRepositoryPolicy()
        self.policy.validate()

    def _ensure_parent(self) -> None:
        if self.policy.create_parent_directories:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def entries(self) -> tuple[OrderAuditEntry, ...]:
        if not self.path.exists():
            return ()
        result: list[OrderAuditEntry] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if text:
                    result.append(audit_entry_from_dict(json.loads(text)))
        return tuple(result)

    def append(
        self,
        event: CanonicalOrderEvent,
        *,
        actor: str = "system",
        metadata: dict | None = None,
    ) -> OrderAuditEntry:
        entries = self.entries()
        previous_hash = (
            entries[-1].entry_hash if entries else self.GENESIS_HASH
        )
        sequence_number = len(entries) + 1
        payload_hash = checksum(event)
        entry_id = f"audit-{uuid.uuid4().hex}"
        hash_payload = {
            "sequence_number": sequence_number,
            "entry_id": entry_id,
            "aggregate_id": event.aggregate_id,
            "aggregate_version": event.aggregate_version,
            "event_id": event.event_id,
            "event_type": event.event_type,
            "previous_hash": previous_hash,
            "payload_hash": payload_hash,
            "actor": actor,
            "correlation_id": event.correlation_id,
            "causation_id": event.causation_id,
            "metadata": metadata or {},
        }
        entry_hash = hashlib.sha256(
            canonical_json(hash_payload).encode("utf-8")
        ).hexdigest()

        entry = OrderAuditEntry(
            sequence_number=sequence_number,
            entry_id=entry_id,
            aggregate_id=event.aggregate_id,
            aggregate_version=event.aggregate_version,
            event_id=event.event_id,
            event_type=event.event_type,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
            payload_hash=payload_hash,
            actor=actor,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            metadata=metadata or {},
        )

        self._ensure_parent()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(entry), sort_keys=True) + "\n")
            handle.flush()
            if self.policy.fsync_on_write:
                os.fsync(handle.fileno())
        return entry

    def verify(self) -> tuple[bool, tuple[str, ...]]:
        errors: list[str] = []
        previous_hash = self.GENESIS_HASH
        for expected_sequence, entry in enumerate(self.entries(), start=1):
            if entry.sequence_number != expected_sequence:
                errors.append(
                    f"SEQUENCE_MISMATCH:{entry.sequence_number}"
                )
            if entry.previous_hash != previous_hash:
                errors.append(
                    f"PREVIOUS_HASH_MISMATCH:{entry.entry_id}"
                )
            hash_payload = {
                "sequence_number": entry.sequence_number,
                "entry_id": entry.entry_id,
                "aggregate_id": entry.aggregate_id,
                "aggregate_version": entry.aggregate_version,
                "event_id": entry.event_id,
                "event_type": entry.event_type,
                "previous_hash": entry.previous_hash,
                "payload_hash": entry.payload_hash,
                "actor": entry.actor,
                "correlation_id": entry.correlation_id,
                "causation_id": entry.causation_id,
                "metadata": entry.metadata,
            }
            expected_hash = hashlib.sha256(
                canonical_json(hash_payload).encode("utf-8")
            ).hexdigest()
            if entry.entry_hash != expected_hash:
                errors.append(f"ENTRY_HASH_MISMATCH:{entry.entry_id}")
            previous_hash = entry.entry_hash
        return not errors, tuple(errors)

    def assert_integrity(self) -> None:
        valid, errors = self.verify()
        if not valid:
            raise AuditLedgerIntegrityError(
                "Audit ledger integrity failed: " + ", ".join(errors)
            )
