from __future__ import annotations

from .order_audit_ledger import OrderAuditLedger
from .order_event_journal import OrderEventJournal
from .order_profile import CanonicalOrderAggregate, CanonicalOrderEvent
from .order_repository import JsonOrderRepository
from .order_repository_policy import OrderRepositoryPolicy
from .order_repository_profile import (
    OrderJournalReplayResult,
    OrderPersistenceResult,
)


class OrderPersistenceService:
    """Atomically coordinate aggregate repository, journal, and audit ledger."""

    def __init__(
        self,
        *,
        repository: JsonOrderRepository | None = None,
        journal: OrderEventJournal | None = None,
        audit_ledger: OrderAuditLedger | None = None,
        policy: OrderRepositoryPolicy | None = None,
    ) -> None:
        self.policy = policy or OrderRepositoryPolicy()
        self.repository = repository or JsonOrderRepository(policy=self.policy)
        self.journal = journal or OrderEventJournal(policy=self.policy)
        self.audit_ledger = audit_ledger or OrderAuditLedger(policy=self.policy)

    def persist_created(
        self,
        aggregate: CanonicalOrderAggregate,
        event: CanonicalOrderEvent,
        *,
        actor: str = "system",
    ) -> OrderPersistenceResult:
        if self.policy.require_event_aggregate_match:
            if event.aggregate_id != aggregate.aggregate_id:
                raise ValueError("Event aggregate id does not match aggregate")
        if self.policy.require_event_version_match:
            if event.aggregate_version != aggregate.version:
                raise ValueError("Event version does not match aggregate version")

        result = self.repository.create(aggregate)
        self.journal.append(event)
        audit = self.audit_ledger.append(event, actor=actor)
        return OrderPersistenceResult(
            **{
                **result.to_dict(),
                "event": event,
                "audit_entry": audit,
            }
        )

    def persist_transition(
        self,
        aggregate: CanonicalOrderAggregate,
        event: CanonicalOrderEvent,
        *,
        expected_version: int,
        actor: str = "system",
    ) -> OrderPersistenceResult:
        if event.aggregate_id != aggregate.aggregate_id:
            raise ValueError("Event aggregate id does not match aggregate")
        if event.aggregate_version != aggregate.version:
            raise ValueError("Event version does not match aggregate version")

        result = self.repository.save(
            aggregate,
            expected_version=expected_version,
        )
        self.journal.append(event)
        audit = self.audit_ledger.append(event, actor=actor)
        return OrderPersistenceResult(
            **{
                **result.to_dict(),
                "event": event,
                "audit_entry": audit,
            }
        )

    def replay(self, aggregate_id: str) -> OrderJournalReplayResult:
        events = self.journal.events_for(aggregate_id)
        if not events:
            return OrderJournalReplayResult(
                valid=False,
                allowed=False,
                aggregate_id=aggregate_id,
                event_count=0,
                final_version=0,
                final_state="UNKNOWN",
                rejection_reasons=("NO_EVENTS",),
            )

        reasons: list[str] = []
        expected_version = 1
        previous_state = "NONE"
        for event in events:
            if event.aggregate_version != expected_version:
                reasons.append("EVENT_VERSION_GAP")
            if event.previous_state != previous_state:
                reasons.append("EVENT_STATE_CHAIN_MISMATCH")
            expected_version += 1
            previous_state = event.new_state

        return OrderJournalReplayResult(
            valid=True,
            allowed=not reasons,
            aggregate_id=aggregate_id,
            event_count=len(events),
            final_version=events[-1].aggregate_version,
            final_state=events[-1].new_state,
            events=events,
            rejection_reasons=tuple(dict.fromkeys(reasons)),
        )

    def verify_integrity(self) -> tuple[bool, tuple[str, ...]]:
        return self.audit_ledger.verify()
