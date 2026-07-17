from __future__ import annotations

import tempfile
from datetime import date, timedelta
from pathlib import Path

from trading_ai.broker.broker_execution_service import BrokerExecutionService
from trading_ai.broker.broker_idempotency_registry import BrokerIdempotencyRegistry
from trading_ai.broker.broker_order_service import BrokerOrderService
from trading_ai.broker.broker_profile import BrokerAuthenticationRequest
from trading_ai.broker.broker_service import BrokerService
from trading_ai.broker.fake_broker_adapter import FakeBrokerAdapter
from trading_ai.broker.fake_broker_execution_adapter import (
    FakeBrokerExecutionAdapter,
)
from trading_ai.broker.instrument_mapper import InstrumentMapper

from trading_ai.order_management.order_audit_ledger import OrderAuditLedger
from trading_ai.order_management.order_command_handler import OrderCommandHandler
from trading_ai.order_management.order_event_journal import OrderEventJournal
from trading_ai.order_management.order_execution_router import OrderExecutionRouter
from trading_ai.order_management.order_persistence_service import (
    OrderPersistenceService,
)
from trading_ai.order_management.order_profile import (
    CanonicalOrderCommand,
    CanonicalOrderLeg,
)
from trading_ai.order_management.order_repository import JsonOrderRepository
from trading_ai.order_management.order_repository_policy import (
    OrderRepositoryPolicy,
)
from trading_ai.order_management.order_routing_profile import (
    OrderRouteCandidate,
)
from trading_ai.order_management.order_service import CanonicalOrderService
from trading_ai.order_management.order_workflow_service import (
    OrderWorkflowService,
)

from trading_ai.risk_gateway.options_risk_profile import (
    OptionGreekProfile,
    ScenarioShockProfile,
)
from trading_ai.risk_gateway.order_risk_mapper import (
    canonical_order_to_risk_request,
)
from trading_ai.risk_gateway.order_workflow_risk_guard import (
    OrderWorkflowRiskGuard,
)
from trading_ai.risk_gateway.portfolio_risk_profile import (
    PortfolioSnapshotProfile,
)
from trading_ai.risk_gateway.pretrade_risk_profile import (
    PreTradeAccountProfile,
)
from trading_ai.risk_gateway.risk_gateway_service import RiskGatewayService
from trading_ai.risk_gateway.trading_control_engine import TradingControlEngine
from trading_ai.risk_gateway.trading_control_policy import TradingControlPolicy
from trading_ai.risk_gateway.trading_control_profile import (
    TradingSessionRiskProfile,
)
from trading_ai.risk_gateway.trading_control_repository import (
    JsonTradingControlRepository,
)
from trading_ai.risk_gateway.trading_control_serialization import dumps
from trading_ai.risk_gateway.trading_control_service import (
    TradingControlService,
)


def main() -> None:
    future = date.today() + timedelta(days=45)
    mapping = InstrumentMapper().map({
        "asset_class": "OPTION",
        "underlying_symbol": "AAPL",
        "expiration": future.isoformat(),
        "strike": 200.0,
        "option_type": "CALL",
    })
    assert mapping.allowed

    account = PreTradeAccountProfile(
        account_id="PAPER-001",
        currency="USD",
        net_liquidation=200000.0,
        buying_power=300000.0,
        option_buying_power=150000.0,
        cash_balance=100000.0,
        excess_liquidity=150000.0,
    )

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        control_repository = JsonTradingControlRepository(
            root / "trading_controls.json"
        )
        control_service = TradingControlService(control_repository)
        control_state = control_service.state("PAPER-001")

        healthy_session = TradingSessionRiskProfile(
            account_id="PAPER-001",
            session_id="session-001",
            starting_equity=200000.0,
            peak_equity=205000.0,
            current_equity=202000.0,
            daily_realized_pnl=-1000.0,
            daily_unrealized_pnl=500.0,
            consecutive_losing_trades=1,
            rejected_orders=0,
            risk_breaches=0,
        )

        broker_adapter = FakeBrokerAdapter()
        broker_service = BrokerService(broker_adapter)
        assert broker_service.authenticate(
            BrokerAuthenticationRequest(
                environment="paper",
                account_id="PAPER-001",
            )
        ).allowed
        execution_adapter = FakeBrokerExecutionAdapter()

        repository_policy = OrderRepositoryPolicy()
        repository = JsonOrderRepository(
            root / "orders.json",
            repository_policy,
        )
        persistence = OrderPersistenceService(
            repository=repository,
            journal=OrderEventJournal(
                root / "events.jsonl",
                repository_policy,
            ),
            audit_ledger=OrderAuditLedger(
                root / "audit.jsonl",
                repository_policy,
            ),
            policy=repository_policy,
        )
        workflow = OrderWorkflowService(
            command_handler=OrderCommandHandler(
                CanonicalOrderService()
            ),
            persistence_service=persistence,
            router=OrderExecutionRouter((
                OrderRouteCandidate(
                    route_id="paper",
                    broker="fake",
                    environment="paper",
                    account_id="PAPER-001",
                    supports_equities=True,
                    supports_options=True,
                    supports_multi_leg_options=True,
                    supports_live_trading=False,
                ),
            )),
            broker_execution_services={
                "paper": BrokerExecutionService(
                    broker_service=broker_service,
                    execution_adapter=execution_adapter,
                    order_service=BrokerOrderService(),
                    idempotency_registry=BrokerIdempotencyRegistry(
                        root / "broker_idempotency.json"
                    ),
                )
            },
            repository=repository,
        )

        command = CanonicalOrderCommand(
            command_id="cmd-risk-guard-001",
            command_type="CREATE",
            aggregate_id="agg-risk-guard-001",
            client_order_id="client-risk-guard-001",
            account_id="PAPER-001",
            idempotency_key="idem-risk-guard-001",
            order_type="LIMIT",
            time_in_force="DAY",
            limit_price=5.0,
            legs=(
                CanonicalOrderLeg(
                    leg_id="leg-1",
                    symbol=mapping.canonical_symbol,
                    broker_symbol=mapping.broker_symbol,
                    asset_class="OPTION",
                    side="BUY_TO_OPEN",
                    quantity=1,
                    position_effect="OPEN",
                    metadata={
                        "multiplier": 100,
                        "strike": 200.0,
                        "option_type": "CALL",
                        "expiration": future.isoformat(),
                        "underlying_symbol": "AAPL",
                        "sector": "TECHNOLOGY",
                    },
                ),
            ),
        )
        assert workflow.create(command).allowed
        assert workflow.validate_and_route(
            command.aggregate_id,
            requested_route="paper",
        ).allowed

        aggregate = repository.require(command.aggregate_id)
        risk_order = canonical_order_to_risk_request(
            aggregate,
            {"leg-1": 5.0},
        )
        portfolio_snapshot = PortfolioSnapshotProfile(
            account=account,
            positions=(),
        )
        greek_legs = (
            OptionGreekProfile(
                leg_id="leg-1",
                symbol=mapping.canonical_symbol,
                underlying_symbol="AAPL",
                quantity=1,
                multiplier=100,
                side="BUY_TO_OPEN",
                delta=0.50,
                gamma=0.02,
                vega=0.18,
                theta=-0.05,
                rho=0.08,
                underlying_price=205.0,
                option_price=5.0,
                strike=200.0,
                expiration=future.isoformat(),
                option_type="CALL",
            ),
        )

        gateway = RiskGatewayService()
        approved = gateway.evaluate(
            order=risk_order,
            account=account,
            portfolio_snapshot=portfolio_snapshot,
            session=healthy_session,
            control_state=control_state,
            greek_legs=greek_legs,
            scenarios=(
                ScenarioShockProfile(
                    scenario_id="down_10",
                    underlying_shock_pct=-0.10,
                ),
            ),
        )
        assert approved.allowed
        assert approved.recommendation == "APPROVE"

        guard = OrderWorkflowRiskGuard(
            risk_gateway=gateway,
            order_workflow_service=workflow,
        )
        submitted = guard.submit(
            aggregate_id=command.aggregate_id,
            route_id="paper",
            instrument_mappings={"leg-1": mapping},
            risk_evaluation_kwargs={
                "order": risk_order,
                "account": account,
                "portfolio_snapshot": portfolio_snapshot,
                "session": healthy_session,
                "control_state": control_state,
                "greek_legs": greek_legs,
                "scenarios": (
                    ScenarioShockProfile(
                        scenario_id="down_10",
                        underlying_shock_pct=-0.10,
                    ),
                ),
            },
        )
        assert submitted.allowed
        assert submitted.workflow_result is not None
        assert submitted.workflow_result.state == "SUBMITTED"
        assert len(execution_adapter.list_orders()) == 1

        control_state = control_service.set_manual_kill_switch(
            account_id="PAPER-001",
            active=True,
            reason="OPERATOR_TEST",
            actor="risk-admin",
        )
        kill_switch_decision = TradingControlEngine().evaluate(
            risk_order,
            healthy_session,
            control_state,
        )
        assert not kill_switch_decision.allowed
        assert "MANUAL_KILL_SWITCH" in kill_switch_decision.rejection_reasons

        loss_session = TradingSessionRiskProfile(
            account_id="PAPER-001",
            session_id="session-loss",
            starting_equity=200000.0,
            peak_equity=205000.0,
            current_equity=180000.0,
            daily_realized_pnl=-12000.0,
            daily_unrealized_pnl=-5000.0,
            consecutive_losing_trades=5,
            rejected_orders=0,
            risk_breaches=5,
        )
        loss_control = TradingControlEngine().evaluate(
            risk_order,
            loss_session,
            control_state,
        )
        assert not loss_control.allowed
        assert "DAILY_REALIZED_LOSS" in loss_control.rejection_reasons
        assert "DAILY_TOTAL_LOSS" in loss_control.rejection_reasons
        assert "INTRADAY_DRAWDOWN" in loss_control.rejection_reasons
        assert "CONSECUTIVE_LOSING_TRADES" in loss_control.rejection_reasons
        assert "RISK_BREACHES" in loss_control.rejection_reasons

        control_state = control_service.set_manual_kill_switch(
            account_id="PAPER-001",
            active=False,
            reason="RESET",
            actor="risk-admin",
        )
        control_state = control_service.add_halt(
            account_id="PAPER-001",
            scope_type="SYMBOL",
            scope_value=mapping.canonical_symbol,
            reason="SYMBOL_VOLATILITY",
            source="risk-engine",
            reduce_only=True,
        )
        symbol_halt = TradingControlEngine().evaluate(
            risk_order,
            healthy_session,
            control_state,
        )
        assert not symbol_halt.allowed
        assert "SYMBOL_HALT" in symbol_halt.rejection_reasons

        close_order = type(risk_order)(
            aggregate_id="agg-close",
            client_order_id="client-close",
            account_id=risk_order.account_id,
            order_type=risk_order.order_type,
            time_in_force=risk_order.time_in_force,
            legs=tuple(
                type(leg)(
                    **{
                        **leg.__dict__,
                        "side": "SELL_TO_CLOSE",
                        "position_effect": "CLOSE",
                    }
                )
                for leg in risk_order.legs
            ),
            limit_price=risk_order.limit_price,
            stop_price=risk_order.stop_price,
            strategy_name=risk_order.strategy_name,
            route_id=risk_order.route_id,
            metadata=risk_order.metadata,
        )
        reduce_only = TradingControlEngine().evaluate(
            close_order,
            healthy_session,
            control_state,
        )
        assert reduce_only.allowed
        assert reduce_only.recommendation == "ALLOW_REDUCE_ONLY"
        assert "REDUCE_ONLY_HALT_OVERRIDE" in reduce_only.warnings

        persisted = JsonTradingControlRepository(
            root / "trading_controls.json"
        ).require("PAPER-001")
        assert persisted.version >= 4
        assert any(halt.active for halt in persisted.halts)

        payload = dumps(approved)
        assert '"recommendation": "APPROVE"' in payload
        assert '"decision_count": 4' in payload

    print(
        "All daily-loss, drawdown, kill-switch, trading-halt, and "
        "risk-gateway workflow assertions passed."
    )


if __name__ == "__main__":
    main()
