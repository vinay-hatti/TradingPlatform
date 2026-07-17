from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OrderRepositoryPolicy:
    require_optimistic_concurrency: bool = True
    reject_duplicate_aggregate_id: bool = True
    reject_duplicate_event_id: bool = True
    require_contiguous_event_versions: bool = True
    require_event_aggregate_match: bool = True
    require_event_version_match: bool = True
    require_audit_hash_chain: bool = True
    fsync_on_write: bool = False
    create_parent_directories: bool = True
    maximum_events_per_aggregate: int = 100000
    fail_closed: bool = True

    def validate(self) -> None:
        if self.maximum_events_per_aggregate <= 0:
            raise ValueError("maximum_events_per_aggregate must be positive")
