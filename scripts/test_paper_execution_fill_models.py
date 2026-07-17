from __future__ import annotations

import tempfile
from pathlib import Path

from trading_ai.paper_trading.paper_execution_policy import (
    PaperExecutionPolicy,
)
from trading_ai.paper_trading.paper_execution_profile import (
    PaperExecutionRequest,
    PaperMarketQuote,
)
from trading_ai.paper_trading.paper_execution_repository import (
    JsonPaperExecutionRepository,
)
from trading_ai.paper_trading.paper_execution_serialization import dumps
from trading_ai.paper_trading.paper_execution_service import (
    PaperExecutionService,
)
from trading_ai.paper_trading.paper_scan_profile import (
    PaperDecisionPipelineResult,
    PaperScanCandidate,
)
from trading_ai.paper_trading.paper_signal_order_mapper import (
    PaperSignalOrderMapper,
)
from trading_ai.paper_trading.paper_trading_profile import (
    PaperTradingSessionProfile,
)
from trading_ai.paper_trading.paper_trading_runtime_repository import (
    JsonPaperTradingRuntimeRepository,
)
from trading_ai.paper_trading.paper_trading_session_service import (
    PaperTradingSessionService,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        runtime_repo = JsonPaperTradingRuntimeRepository(
            root / "runtime.json"
        )
        session_service = PaperTradingSessionService(
            repository=runtime_repo
        )
        profile = PaperTradingSessionProfile(
            session_id="paper-session-003",
            account_id="PAPER-001",
            environment="paper",
            strategy_names=("LONG_CALL",),
            symbols=("AAPL_CALL_200",),
            cycle_interval_seconds=60,
            starting_capital=100000.0,
        )
        assert session_service.create(profile)[0].allowed
        assert session_service.transition(profile.session_id, "PREPARE")[0].allowed
        assert session_service.transition(profile.session_id, "START")[0].allowed
        state, cycle = session_service.begin_cycle(profile.session_id)

        candidate = PaperScanCandidate(
            candidate_id="cand-exec-1",
            symbol="AAPL_CALL_200",
            strategy_name="LONG_CALL",
            asset_class="OPTION",
            direction="LONG",
            score=90.0,
            probability=0.75,
            market_price=5.0,
            quantity=2,
            limit_price=5.10,
            expiration="2026-08-21",
            strike=200.0,
            option_type="CALL",
        )
        decision = PaperDecisionPipelineResult(
            candidate_id=candidate.candidate_id,
            symbol=candidate.symbol,
            strategy_name=candidate.strategy_name,
            approved=True,
            score=candidate.score,
            probability=candidate.probability,
            recommendation="CREATE_ORDER",
            institutional_decision={"allowed": True},
            risk_gateway_decision={"allowed": True},
        )
        draft = PaperSignalOrderMapper().map(
            candidate=candidate,
            decision=decision,
            account_id="PAPER-001",
        )

        execution_repo = JsonPaperExecutionRepository(
            root / "executions.json"
        )
        service = PaperExecutionService(
            policy=PaperExecutionPolicy(
                default_latency_ms=125,
                default_slippage_bps=2.0,
                option_contract_commission=0.65,
            ),
            execution_repository=execution_repo,
            runtime_repository=runtime_repo,
        )
        quote = PaperMarketQuote(
            symbol=candidate.symbol,
            bid=4.95,
            ask=5.00,
            last=4.98,
            timestamp="2026-07-16T15:00:00+00:00",
            bid_size=10,
            ask_size=10,
        )
        result = service.execute(
            PaperExecutionRequest(
                execution_key="exec-key-1",
                session_id=profile.session_id,
                cycle_id=cycle.cycle_id,
                order_draft=draft,
                quotes={candidate.symbol: quote},
            )
        )
        assert result.allowed
        assert result.record is not None
        assert result.record.status == "FILLED"
        assert result.record.filled_quantity == 2
        assert result.record.remaining_quantity == 0
        assert len(result.record.fills) == 1
        fill = result.record.fills[0]
        assert fill.fill_price > quote.ask
        assert fill.slippage_bps == 2.0
        assert fill.commission == 1.30
        assert fill.latency_ms == 125
        assert result.record.commissions == 1.30
        assert result.record.net_cash_flow < 0

        replay = service.execute(
            PaperExecutionRequest(
                execution_key="exec-key-1",
                session_id=profile.session_id,
                cycle_id=cycle.cycle_id,
                order_draft=draft,
                quotes={candidate.symbol: quote},
            )
        )
        assert replay.allowed
        assert replay.recommendation == "IDEMPOTENT_REPLAY"
        assert replay.record is not None
        assert replay.record.execution_key == result.record.execution_key
        assert replay.record.aggregate_id == result.record.aggregate_id
        assert replay.record.status == result.record.status
        assert replay.record.filled_quantity == result.record.filled_quantity
        assert replay.record.average_fill_price == result.record.average_fill_price
        assert replay.record.commissions == result.record.commissions

        non_marketable_candidate = PaperScanCandidate(
            **{
                **candidate.__dict__,
                "candidate_id": "cand-exec-2",
                "limit_price": 4.50,
            }
        )
        non_marketable_draft = PaperSignalOrderMapper().map(
            candidate=non_marketable_candidate,
            decision=PaperDecisionPipelineResult(
                candidate_id="cand-exec-2",
                symbol=candidate.symbol,
                strategy_name=candidate.strategy_name,
                approved=True,
                score=90.0,
                probability=0.75,
                recommendation="CREATE_ORDER",
                institutional_decision={"allowed": True},
                risk_gateway_decision={"allowed": True},
            ),
            account_id="PAPER-001",
        )
        working = service.execute(
            PaperExecutionRequest(
                execution_key="exec-key-2",
                session_id=profile.session_id,
                cycle_id=cycle.cycle_id,
                order_draft=non_marketable_draft,
                quotes={candidate.symbol: quote},
            )
        )
        assert working.allowed
        assert working.record is not None
        assert working.record.status == "WORKING"
        assert working.record.filled_quantity == 0
        assert working.record.remaining_quantity == 2

        partial_service = PaperExecutionService(
            policy=PaperExecutionPolicy(
                maximum_fill_fraction_per_attempt=0.50,
                option_contract_commission=0.65,
            ),
            execution_repository=execution_repo,
        )
        partial = partial_service.execute(
            PaperExecutionRequest(
                execution_key="exec-key-3",
                session_id=profile.session_id,
                cycle_id=cycle.cycle_id,
                order_draft=draft,
                quotes={
                    candidate.symbol: PaperMarketQuote(
                        symbol=candidate.symbol,
                        bid=4.95,
                        ask=5.00,
                        last=4.98,
                        timestamp="2026-07-16T15:00:00+00:00",
                        bid_size=1,
                        ask_size=1,
                    )
                },
                metadata={
                    "latency_ms": 250,
                    "slippage_bps": 5.0,
                },
            )
        )
        assert partial.allowed
        assert partial.record is not None
        assert partial.record.status == "PARTIALLY_FILLED"
        assert partial.record.filled_quantity == 1
        assert partial.record.remaining_quantity == 1
        assert partial.record.fills[0].latency_ms == 250
        assert partial.record.fills[0].slippage_bps == 5.0
        assert partial.record.fills[0].commission == 0.65

        reloaded = JsonPaperExecutionRepository(
            root / "executions.json"
        ).get("exec-key-1")
        assert reloaded is not None
        assert reloaded.status == "FILLED"

        runtime = runtime_repo.require(profile.session_id)
        assert runtime.orders_submitted == 2
        assert runtime.fills_received == 1

        payload = dumps(result)
        assert '"status": "FILLED"' in payload
        assert '"commissions": 1.3' in payload

    print(
        "All paper-broker execution, fill simulation, slippage, "
        "commission, and latency assertions passed."
    )


if __name__ == "__main__":
    main()
