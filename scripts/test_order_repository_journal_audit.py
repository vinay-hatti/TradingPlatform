from __future__ import annotations

import json
import tempfile
from pathlib import Path

from trading_ai.order_management.order_audit_ledger import OrderAuditLedger
from trading_ai.order_management.order_event_journal import OrderEventJournal
from trading_ai.order_management.order_persistence_service import (
    OrderPersistenceService,
)
from trading_ai.order_management.order_profile import (
    CanonicalOrderCommand,
    CanonicalOrderLeg,
)
from trading_ai.order_management.order_repository import JsonOrderRepository
from trading_ai.order_management.order_repository_exceptions import (
    DuplicateOrderError,
    DuplicateOrderEventError,
    OptimisticConcurrencyError,
)
from trading_ai.order_management.order_repository_policy import (
    OrderRepositoryPolicy,
)
from trading_ai.order_management.order_repository_serialization import dumps
from trading_ai.order_management.order_service import CanonicalOrderService


def main() -> None:
    lifecycle = CanonicalOrderService()
    command = CanonicalOrderCommand(
        command_id="cmd-create-001",
        command_type="CREATE",
        aggregate_id="agg-repository-001",
        client_order_id="client-repository-001",
        account_id="PAPER-001",
        idempotency_key="idem-repository-001",
        order_type="LIMIT",
        time_in_force="DAY",
        limit_price=5.00,
        legs=(
            CanonicalOrderLeg(
                leg_id="leg-1",
                symbol="AAPL  260821C00200000",
                asset_class="OPTION",
                side="BUY_TO_OPEN",
                quantity=2,
                position_effect="OPEN",
            ),
        ),
    )
    created = lifecycle.create(command)
    assert created.allowed and created.aggregate and created.event

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        policy = OrderRepositoryPolicy()
        repository = JsonOrderRepository(root / "orders.json", policy)
        journal = OrderEventJournal(root / "events.jsonl", policy)
        ledger = OrderAuditLedger(root / "audit.jsonl", policy)
        persistence = OrderPersistenceService(
            repository=repository,
            journal=journal,
            audit_ledger=ledger,
            policy=policy,
        )

        create_result = persistence.persist_created(
            created.aggregate,
            created.event,
            actor="unit-test",
        )
        assert create_result.allowed
        assert create_result.persisted_version == 1
        assert create_result.audit_entry is not None
        assert repository.require(created.aggregate.aggregate_id).state == "NEW"
        assert journal.latest_version(created.aggregate.aggregate_id) == 1

        try:
            persistence.persist_created(
                created.aggregate,
                created.event,
            )
            raise AssertionError("Expected duplicate aggregate rejection")
        except DuplicateOrderError:
            pass

        validated = lifecycle.transition(
            created.aggregate,
            "VALIDATE",
            event_id="evt-validate-001",
        )
        assert validated.allowed and validated.aggregate and validated.event

        update_result = persistence.persist_transition(
            validated.aggregate,
            validated.event,
            expected_version=1,
            actor="unit-test",
        )
        assert update_result.allowed
        assert update_result.persisted_version == 2
        assert repository.require(created.aggregate.aggregate_id).state == "VALIDATED"

        routed = lifecycle.transition(
            validated.aggregate,
            "ROUTE",
            event_id="evt-route-001",
        )
        assert routed.allowed and routed.aggregate and routed.event

        try:
            persistence.persist_transition(
                routed.aggregate,
                routed.event,
                expected_version=1,
            )
            raise AssertionError("Expected optimistic concurrency conflict")
        except OptimisticConcurrencyError as exc:
            assert exc.expected_version == 1
            assert exc.actual_version == 2

        route_result = persistence.persist_transition(
            routed.aggregate,
            routed.event,
            expected_version=2,
        )
        assert route_result.allowed
        assert route_result.persisted_version == 3

        try:
            journal.append(routed.event)
            raise AssertionError("Expected duplicate event rejection")
        except DuplicateOrderEventError:
            pass

        replay = persistence.replay(created.aggregate.aggregate_id)
        assert replay.allowed
        assert replay.event_count == 3
        assert replay.final_version == 3
        assert replay.final_state == "ROUTED"

        repository_reloaded = JsonOrderRepository(root / "orders.json", policy)
        reloaded = repository_reloaded.require(created.aggregate.aggregate_id)
        assert reloaded.version == 3
        assert reloaded.state == "ROUTED"
        assert reloaded.legs[0].symbol == "AAPL  260821C00200000"

        journal_reloaded = OrderEventJournal(root / "events.jsonl", policy)
        assert len(journal_reloaded.events_for(created.aggregate.aggregate_id)) == 3

        valid, errors = ledger.verify()
        assert valid
        assert errors == ()
        assert len(ledger.entries()) == 3

        # Deliberately tamper with one audit entry and verify detection.
        lines = (root / "audit.jsonl").read_text(encoding="utf-8").splitlines()
        tampered = json.loads(lines[1])
        tampered["event_type"] = "TAMPERED_EVENT"
        lines[1] = json.dumps(tampered, sort_keys=True)
        (root / "audit.jsonl").write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8",
        )
        valid, errors = ledger.verify()
        assert not valid
        assert any(
            reason.startswith("ENTRY_HASH_MISMATCH")
            for reason in errors
        )

        payload = dumps(route_result)
        assert '"persisted_version": 3' in payload
        assert '"recommendation": "PERSISTED"' in payload

    print(
        "All order repository, event journal, audit ledger, and "
        "optimistic-concurrency assertions passed."
    )


if __name__ == "__main__":
    main()
