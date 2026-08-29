from __future__ import annotations

import tempfile
from pathlib import Path

from trading_ai.paper_trading.paper_trading_policy import (
    PaperTradingAutomationPolicy,
)
from trading_ai.paper_trading.paper_trading_profile import (
    PaperTradingSessionProfile,
)
from trading_ai.paper_trading.paper_trading_runtime_repository import (
    JsonPaperTradingRuntimeRepository,
)
from trading_ai.paper_trading.paper_trading_serialization import dumps
from trading_ai.paper_trading.paper_trading_session_service import (
    PaperTradingSessionService,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        repository = JsonPaperTradingRuntimeRepository(
            Path(temp) / "runtime_states.json"
        )
        service = PaperTradingSessionService(
            policy=PaperTradingAutomationPolicy(),
            repository=repository,
        )

        profile = PaperTradingSessionProfile(
            session_id="paper-session-001",
            account_id="PAPER-001",
            environment="paper",
            strategy_names=("LONG_CALL", "BULL_CALL_SPREAD"),
            symbols=("AAPL", "MSFT"),
            cycle_interval_seconds=60,
            starting_capital=100000.0,
        )
        created, state = service.create(profile)
        assert created.allowed
        assert state is not None
        assert state.session.state == "CREATED"
        assert state.version == 1

        prepared, state = service.transition(
            profile.session_id,
            "PREPARE",
        )
        assert prepared.allowed
        assert state.session.state == "READY"

        started, state = service.transition(
            profile.session_id,
            "START",
        )
        assert started.allowed
        assert state.session.state == "RUNNING"
        assert state.session.started_at is not None

        state, cycle = service.begin_cycle(profile.session_id)
        assert cycle.sequence_number == 1
        assert cycle.state == "STARTED"
        assert state.cycle_count == 1

        state = service.complete_cycle(
            profile.session_id,
            candidate_count=5,
            approved_count=3,
            submitted_count=2,
            rejected_count=2,
        )
        assert state.last_cycle is not None
        assert state.last_cycle.state == "COMPLETED"
        assert state.orders_created == 5
        assert state.orders_submitted == 2
        assert state.orders_rejected == 2

        paused, state = service.transition(
            profile.session_id,
            "PAUSE",
        )
        assert paused.allowed
        assert state.session.state == "PAUSED"

        resumed, state = service.transition(
            profile.session_id,
            "RESUME",
        )
        assert resumed.allowed
        assert state.session.state == "RUNNING"

        stopping, state = service.transition(
            profile.session_id,
            "STOP",
        )
        assert stopping.allowed
        assert state.session.state == "STOPPING"

        finalized, state = service.transition(
            profile.session_id,
            "FINALIZE",
        )
        assert finalized.allowed
        assert state.session.state == "STOPPED"
        assert state.session.stopped_at is not None

        reloaded = JsonPaperTradingRuntimeRepository(
            Path(temp) / "runtime_states.json"
        ).require(profile.session_id)
        assert reloaded.session.state == "STOPPED"
        assert reloaded.orders_submitted == 2
        assert reloaded.version == state.version

        payload = dumps(reloaded)
        assert '"state": "STOPPED"' in payload
        assert '"orders_submitted": 2' in payload

        invalid = PaperTradingSessionProfile(
            session_id="invalid-session",
            account_id="PAPER-001",
            environment="live",
            strategy_names=(),
            symbols=(),
            cycle_interval_seconds=1,
            starting_capital=0.0,
        )
        decision, invalid_state = service.engine.create(invalid)
        assert not decision.allowed
        assert invalid_state is None
        assert "ENVIRONMENT" in decision.rejection_reasons
        assert "STRATEGY_NAMES" in decision.rejection_reasons
        assert "SYMBOLS" in decision.rejection_reasons
        assert "CYCLE_INTERVAL" in decision.rejection_reasons
        assert "STARTING_CAPITAL" in decision.rejection_reasons

    print(
        "All paper-trading session contracts, automation policy, and "
        "runtime-state assertions passed."
    )


if __name__ == "__main__":
    main()
