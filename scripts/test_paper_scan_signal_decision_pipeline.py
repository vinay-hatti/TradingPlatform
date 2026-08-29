from __future__ import annotations
import tempfile
from pathlib import Path

from trading_ai.paper_trading.paper_scan_cycle_service import PaperScanCycleService
from trading_ai.paper_trading.paper_scan_profile import PaperScanCandidate
from trading_ai.paper_trading.paper_scan_serialization import dumps
from trading_ai.paper_trading.paper_trading_profile import PaperTradingSessionProfile
from trading_ai.paper_trading.paper_trading_runtime_repository import JsonPaperTradingRuntimeRepository
from trading_ai.paper_trading.paper_trading_session_service import PaperTradingSessionService

def main():
    with tempfile.TemporaryDirectory() as temp:
        session_service = PaperTradingSessionService(
            repository=JsonPaperTradingRuntimeRepository(
                Path(temp) / "runtime.json"
            )
        )
        profile = PaperTradingSessionProfile(
            session_id="paper-session-002",
            account_id="PAPER-001",
            environment="paper",
            strategy_names=("LONG_CALL",),
            symbols=("AAPL", "MSFT"),
            cycle_interval_seconds=60,
            starting_capital=100000.0,
        )
        assert session_service.create(profile)[0].allowed
        assert session_service.transition(profile.session_id, "PREPARE")[0].allowed
        assert session_service.transition(profile.session_id, "START")[0].allowed

        candidates = (
            PaperScanCandidate(
                candidate_id="cand-1",
                symbol="AAPL_CALL_200",
                strategy_name="LONG_CALL",
                asset_class="OPTION",
                direction="LONG",
                score=88.0,
                probability=0.72,
                market_price=5.0,
                quantity=1,
                expiration="2026-08-21",
                strike=200.0,
                option_type="CALL",
                sector="TECHNOLOGY",
            ),
            PaperScanCandidate(
                candidate_id="cand-2",
                symbol="MSFT",
                strategy_name="MOMENTUM",
                asset_class="EQUITY",
                direction="LONG",
                score=60.0,
                probability=0.40,
                market_price=400.0,
                quantity=10,
            ),
        )
        service = PaperScanCycleService(session_service=session_service)
        result = service.run(
            session_id=profile.session_id,
            candidates=candidates,
            institutional_decisions={
                "cand-1": {
                    "allowed": True,
                    "recommendation": "TRADE",
                }
            },
            risk_gateway_decisions={
                "cand-1": {
                    "allowed": True,
                    "recommendation": "APPROVE",
                }
            },
        )

        assert result.candidate_count == 2
        assert result.approved_count == 1
        assert result.rejected_count == 1
        assert result.order_draft_count == 1

        draft = result.order_drafts[0]
        assert draft.command.command_type == "CREATE"
        assert draft.command.account_id == "PAPER-001"
        assert draft.command.strategy_name == "LONG_CALL"
        assert draft.command.legs[0].side == "BUY_TO_OPEN"
        assert draft.command.legs[0].metadata["multiplier"] == 100
        assert draft.risk_metadata["risk_gateway_approved"] is True

        state = session_service.repository.require(profile.session_id)
        assert state.cycle_count == 1
        assert state.orders_created == 2
        assert state.orders_submitted == 0
        assert state.orders_rejected == 1
        assert state.last_cycle is not None
        assert state.last_cycle.state == "COMPLETED"

        blocked = service.run(
            session_id=profile.session_id,
            candidates=(candidates[0],),
            institutional_decisions={
                "cand-1": {"allowed": True}
            },
            risk_gateway_decisions={
                "cand-1": {
                    "allowed": False,
                    "rejection_reasons": ("MAXIMUM_SCENARIO_LOSS",),
                }
            },
        )
        assert blocked.approved_count == 0
        assert blocked.order_draft_count == 0
        assert blocked.rejected_count == 1
        assert (
            "RISK_GATEWAY_REJECTED"
            in blocked.decisions[0].rejection_reasons
        )

        payload = dumps(result)
        assert '"order_draft_count": 1' in payload
        assert '"execution_deferred": true' in payload

    print(
        "All automated scan-cycle, signal-to-order, and "
        "decision-pipeline assertions passed."
    )

if __name__ == "__main__":
    main()
