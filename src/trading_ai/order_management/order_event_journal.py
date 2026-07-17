from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from .order_profile import CanonicalOrderEvent
from .order_repository_exceptions import DuplicateOrderEventError
from .order_repository_policy import OrderRepositoryPolicy
from .order_storage_codec import event_from_dict


class OrderEventJournal:
    """Append-only JSONL event journal."""

    def __init__(
        self,
        path: str | Path = "data/order_management/order_events.jsonl",
        policy: OrderRepositoryPolicy | None = None,
    ) -> None:
        self.path = Path(path)
        self.policy = policy or OrderRepositoryPolicy()
        self.policy.validate()
        self._event_ids: set[str] = set()
        self._versions: dict[str, int] = {}
        if self.path.exists():
            self._load_index()

    def _ensure_parent(self) -> None:
        if self.policy.create_parent_directories:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> None:
        self._event_ids.clear()
        self._versions.clear()
        for event in self.all_events():
            self._event_ids.add(event.event_id)
            self._versions[event.aggregate_id] = max(
                self._versions.get(event.aggregate_id, 0),
                event.aggregate_version,
            )

    def append(self, event: CanonicalOrderEvent) -> Path:
        if (
            self.policy.reject_duplicate_event_id
            and event.event_id in self._event_ids
        ):
            raise DuplicateOrderEventError(
                f"Duplicate order event id: {event.event_id}"
            )

        previous_version = self._versions.get(event.aggregate_id, 0)
        if (
            self.policy.require_contiguous_event_versions
            and event.aggregate_version != previous_version + 1
        ):
            raise ValueError(
                f"Non-contiguous event version for {event.aggregate_id}: "
                f"expected {previous_version + 1}, got {event.aggregate_version}"
            )

        if previous_version >= self.policy.maximum_events_per_aggregate:
            raise ValueError(
                f"Maximum event count reached for {event.aggregate_id}"
            )

        self._ensure_parent()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), sort_keys=True) + "\n")
            handle.flush()
            if self.policy.fsync_on_write:
                os.fsync(handle.fileno())

        self._event_ids.add(event.event_id)
        self._versions[event.aggregate_id] = event.aggregate_version
        return self.path

    def all_events(self) -> tuple[CanonicalOrderEvent, ...]:
        if not self.path.exists():
            return ()
        events: list[CanonicalOrderEvent] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if text:
                    events.append(event_from_dict(json.loads(text)))
        return tuple(events)

    def events_for(
        self,
        aggregate_id: str,
    ) -> tuple[CanonicalOrderEvent, ...]:
        return tuple(
            event
            for event in self.all_events()
            if event.aggregate_id == aggregate_id
        )

    def latest_version(self, aggregate_id: str) -> int:
        return self._versions.get(aggregate_id, 0)

    def contains(self, event_id: str) -> bool:
        return event_id in self._event_ids
