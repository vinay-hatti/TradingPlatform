from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Mapping

from trading_ai.research_workstation.phase3_dashboard import (
    Phase3DashboardEngine,
    write_phase3_dashboard_html,
    write_phase3_dashboard_json,
)
from trading_ai.research_workstation.portfolio_planning import (
    AllocationCandidateProfile,
    PortfolioAllocationEngine,
    write_portfolio_allocation_report,
)
from trading_ai.research_workstation.pretrade_governance import (
    PreTradeGovernanceEngine,
    write_governance_decision_report,
)
from trading_ai.research_workstation.trade_construction import (
    TradeConstructionEngine,
    write_trade_construction_report,
)
from trading_ai.research_workstation.trade_lifecycle import (
    TradeLifecycleEngine,
    write_trade_lifecycle_report,
)

from .phase3_pipeline_profile import Phase3PipelineResultProfile
from .phase3_pipeline_serialization import write_phase3_pipeline_report


class Phase3PipelineEngine:
    def __init__(
        self,
        *,
        trade_construction_engine: TradeConstructionEngine | None = None,
        portfolio_allocation_engine: PortfolioAllocationEngine | None = None,
        trade_lifecycle_engine: TradeLifecycleEngine | None = None,
        pretrade_governance_engine: PreTradeGovernanceEngine | None = None,
        dashboard_engine: Phase3DashboardEngine | None = None,
    ) -> None:
        self.trade_construction_engine = (
            trade_construction_engine or TradeConstructionEngine()
        )
        self.portfolio_allocation_engine = (
            portfolio_allocation_engine or PortfolioAllocationEngine()
        )
        self.trade_lifecycle_engine = (
            trade_lifecycle_engine or TradeLifecycleEngine()
        )
        self.pretrade_governance_engine = (
            pretrade_governance_engine or PreTradeGovernanceEngine()
        )
        self.dashboard_engine = dashboard_engine or Phase3DashboardEngine()

    @staticmethod
    def _date(value: Any, *, name: str) -> date:
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError(
                    f"{name} must use YYYY-MM-DD format."
                ) from exc
        raise ValueError(f"{name} must be a date or ISO date string.")

    @staticmethod
    def _number(
        source: Mapping[str, Any],
        name: str,
        default: float = 0.0,
    ) -> float:
        value = source.get(name, default)
        return float(default if value is None else value)

    @staticmethod
    def _integer(
        source: Mapping[str, Any],
        name: str,
        default: int = 0,
    ) -> int:
        value = source.get(name, default)
        return int(default if value is None else value)

    @staticmethod
    def _allocation_candidate(
        *,
        candidate_id: str,
        symbol: str,
        sector: str,
        strategy_name: str,
        requested_contracts: int,
        maximum_contracts: int,
        risk_per_contract: float,
        buying_power_per_contract: float,
        maximum_profit_per_contract: float,
        probability_of_profit: float,
        expected_return_pct: float,
        annualized_volatility_pct: float,
        expected_shortfall_per_contract: float,
        liquidity_score: float,
        delta_per_contract: float,
        gamma_per_contract: float,
        theta_per_contract: float,
        vega_per_contract: float,
        direction: str,
    ) -> AllocationCandidateProfile:
        return AllocationCandidateProfile(
            candidate_id=candidate_id,
            symbol=symbol,
            sector=sector,
            strategy_name=strategy_name,
            requested_contracts=requested_contracts,
            maximum_contracts=maximum_contracts,
            risk_per_contract=risk_per_contract,
            buying_power_per_contract=buying_power_per_contract,
            maximum_profit_per_contract=maximum_profit_per_contract,
            probability_of_profit=probability_of_profit,
            expected_return_pct=expected_return_pct,
            annualized_volatility_pct=annualized_volatility_pct,
            expected_shortfall_per_contract=expected_shortfall_per_contract,
            liquidity_score=liquidity_score,
            delta_per_contract=delta_per_contract,
            gamma_per_contract=gamma_per_contract,
            theta_per_contract=theta_per_contract,
            vega_per_contract=vega_per_contract,
            direction=direction,
            metadata={
                "source": "PHASE3_PIPELINE",
            },
        )

    def run(
        self,
        *,
        manifest: Mapping[str, Any],
        output_directory: str | Path,
    ) -> Phase3PipelineResultProfile:
        output_dir = Path(output_directory)
        output_dir.mkdir(parents=True, exist_ok=True)

        trade = dict(manifest.get("trade", {}))
        account = dict(manifest.get("account", {}))
        planning = dict(manifest.get("portfolio_planning", {}))
        lifecycle_input = dict(manifest.get("lifecycle", {}))
        governance_input = dict(manifest.get("governance", {}))

        trade_id = str(trade.get("trade_id", "TRADE-001"))
        symbol = str(trade.get("symbol", "")).upper().strip()
        strategy_name = str(
            trade.get("strategy_name", "")
        ).upper().strip()
        direction = str(
            trade.get("direction", "NEUTRAL")
        ).upper().strip()
        sector = str(trade.get("sector", "UNKNOWN")).upper().strip()

        if not symbol:
            raise ValueError("trade.symbol is required.")
        if not strategy_name:
            raise ValueError("trade.strategy_name is required.")

        account_equity = self._number(
            account, "account_equity", 100000.0
        )
        requested_contracts = self._integer(
            trade, "requested_contracts", 1
        )

        raw_legs = tuple(trade.get("legs", ()) or ())
        if not raw_legs:
            raise ValueError("trade.legs must contain at least one leg.")

        normalized_legs = []
        for index, raw_leg in enumerate(raw_legs, start=1):
            leg = dict(raw_leg)
            leg["expiration"] = self._date(
                leg.get("expiration"),
                name=f"trade.legs[{index}].expiration",
            )
            normalized_legs.append(leg)

        maximum_profit_per_contract = trade.get(
            "maximum_profit_per_contract"
        )
        maximum_loss_per_contract = trade.get(
            "maximum_loss_per_contract"
        )
        probability_of_profit = self._number(
            trade, "probability_of_profit", 0.0
        )

        trade_construction = self.trade_construction_engine.construct(
            symbol=symbol,
            strategy_name=strategy_name,
            direction=direction,
            legs=tuple(normalized_legs),
            account_equity=account_equity,
            maximum_profit_per_contract=(
                None
                if maximum_profit_per_contract is None
                else float(maximum_profit_per_contract)
            ),
            maximum_loss_per_contract=(
                None
                if maximum_loss_per_contract is None
                else float(maximum_loss_per_contract)
            ),
            probability_of_profit=probability_of_profit,
            breakeven_points=tuple(
                float(value)
                for value in trade.get("breakeven_points", ())
            ),
            quantity_ratios=tuple(
                int(value)
                for value in trade.get(
                    "quantity_ratios",
                    (1 for _ in normalized_legs),
                )
            ),
            requested_contracts=requested_contracts,
        )

        construction_report = write_trade_construction_report(
            trade_construction,
            output_dir / "trade_construction.json",
        )

        ticket = trade_construction.ticket
        blueprint = trade_construction.blueprint
        risk_per_contract = float(
            blueprint.maximum_loss_per_contract
            if blueprint.maximum_loss_per_contract is not None
            else trade_construction.capital.risk_per_contract
        )
        buying_power_per_contract = float(
            trade_construction.capital.buying_power_per_contract
        )
        profit_per_contract = float(
            blueprint.maximum_profit_per_contract or 0.0
        )

        greeks = dict(planning.get("greeks_per_contract", {}))
        allocation_candidate = self._allocation_candidate(
            candidate_id=str(
                planning.get("candidate_id", trade_id)
            ),
            symbol=symbol,
            sector=sector,
            strategy_name=strategy_name,
            requested_contracts=requested_contracts,
            maximum_contracts=self._integer(
                planning,
                "maximum_contracts",
                max(1, requested_contracts),
            ),
            risk_per_contract=risk_per_contract,
            buying_power_per_contract=buying_power_per_contract,
            maximum_profit_per_contract=profit_per_contract,
            probability_of_profit=probability_of_profit,
            expected_return_pct=self._number(
                planning, "expected_return_pct", 0.08
            ),
            annualized_volatility_pct=self._number(
                planning, "annualized_volatility_pct", 0.25
            ),
            expected_shortfall_per_contract=self._number(
                planning,
                "expected_shortfall_per_contract",
                risk_per_contract * 0.50,
            ),
            liquidity_score=self._number(
                planning, "liquidity_score", 85.0
            ),
            delta_per_contract=self._number(
                greeks, "delta", 0.0
            ),
            gamma_per_contract=self._number(
                greeks, "gamma", 0.0
            ),
            theta_per_contract=self._number(
                greeks, "theta", 0.0
            ),
            vega_per_contract=self._number(
                greeks, "vega", 0.0
            ),
            direction=direction,
        )

        correlations: dict[tuple[str, str], float] = {}
        for item in planning.get("correlations", ()) or ():
            row = dict(item)
            left = str(row.get("left", symbol))
            right = str(row.get("right", symbol))
            correlations[(left, right)] = float(
                row.get("correlation", 0.0)
            )

        portfolio_allocation = self.portfolio_allocation_engine.allocate(
            account_equity=account_equity,
            candidates=(allocation_candidate,),
            correlations=correlations,
        )
        allocation_report = write_portfolio_allocation_report(
            portfolio_allocation,
            output_dir / "portfolio_allocation.json",
        )

        as_of_date = self._date(
            lifecycle_input.get("as_of_date"),
            name="lifecycle.as_of_date",
        )
        expiration = normalized_legs[0]["expiration"]
        event_date_value = lifecycle_input.get("event_date")
        event_date = (
            None
            if event_date_value in {None, ""}
            else self._date(
                event_date_value,
                name="lifecycle.event_date",
            )
        )

        trade_lifecycle = self.trade_lifecycle_engine.plan(
            symbol=symbol,
            strategy_name=strategy_name,
            expiration=expiration,
            as_of_date=as_of_date,
            entry_limit_price=float(blueprint.net_limit_price),
            net_credit_debit=float(blueprint.net_credit_debit),
            maximum_profit=ticket.maximum_profit,
            maximum_loss=ticket.maximum_loss,
            probability_of_profit=probability_of_profit,
            confidence=self._number(
                lifecycle_input,
                "confidence",
                probability_of_profit,
            ),
            spread_pct=max(
                float(leg.spread_pct)
                for leg in blueprint.legs
            ),
            defined_risk=bool(blueprint.defined_risk),
            current_delta_exposure=float(
                portfolio_allocation.exposure.portfolio_delta
            ),
            event_date=event_date,
        )
        lifecycle_report = write_trade_lifecycle_report(
            trade_lifecycle,
            output_dir / "trade_lifecycle.json",
        )

        governance = self.pretrade_governance_engine.evaluate(
            trade_id=trade_id,
            symbol=symbol,
            strategy_name=strategy_name,
            trade_construction=trade_construction,
            portfolio_allocation=portfolio_allocation,
            lifecycle=trade_lifecycle,
            broker_ready=bool(
                governance_input.get("broker_ready", True)
            ),
            compliance_cleared=bool(
                governance_input.get("compliance_cleared", True)
            ),
            event_risk_present=bool(
                governance_input.get(
                    "event_risk_present",
                    event_date is not None,
                )
            ),
            override_requested=bool(
                governance_input.get("override_requested", False)
            ),
            override_approved=bool(
                governance_input.get("override_approved", False)
            ),
            override_reviewer=governance_input.get(
                "override_reviewer"
            ),
            override_reason=governance_input.get("override_reason"),
            override_scope=tuple(
                str(value)
                for value in governance_input.get(
                    "override_scope", ()
                )
            ),
        )
        governance_report = write_governance_decision_report(
            governance,
            output_dir / "pretrade_governance.json",
        )

        dashboard = self.dashboard_engine.build(
            trade_id=trade_id,
            symbol=symbol,
            strategy_name=strategy_name,
            trade_construction=trade_construction,
            portfolio_allocation=portfolio_allocation,
            lifecycle=trade_lifecycle,
            governance=governance,
        )
        dashboard_json = write_phase3_dashboard_json(
            dashboard,
            output_dir / "phase3_dashboard.json",
        )
        dashboard_html = write_phase3_dashboard_html(
            dashboard,
            output_dir / "phase3_dashboard.html",
        )

        provisional = Phase3PipelineResultProfile(
            trade_id=trade_id,
            symbol=symbol,
            strategy_name=strategy_name,
            output_directory=output_dir,
            trade_construction_report=construction_report,
            portfolio_allocation_report=allocation_report,
            trade_lifecycle_report=lifecycle_report,
            pretrade_governance_report=governance_report,
            dashboard_json_report=dashboard_json,
            dashboard_html_report=dashboard_html,
            pipeline_report=output_dir / "phase3_pipeline.json",
            overall_status=dashboard.overall_status,
            approval_status=dashboard.approval_status,
            execution_allowed=dashboard.execution_allowed,
            metadata={
                "milestone": 34,
                "phase": 3,
                "step": 5,
                "source": "PHASE3_END_TO_END_PIPELINE",
            },
        )
        pipeline_report = write_phase3_pipeline_report(
            provisional,
            provisional.pipeline_report,
        )

        return Phase3PipelineResultProfile(
            trade_id=provisional.trade_id,
            symbol=provisional.symbol,
            strategy_name=provisional.strategy_name,
            output_directory=provisional.output_directory,
            trade_construction_report=provisional.trade_construction_report,
            portfolio_allocation_report=provisional.portfolio_allocation_report,
            trade_lifecycle_report=provisional.trade_lifecycle_report,
            pretrade_governance_report=provisional.pretrade_governance_report,
            dashboard_json_report=provisional.dashboard_json_report,
            dashboard_html_report=provisional.dashboard_html_report,
            pipeline_report=pipeline_report,
            overall_status=provisional.overall_status,
            approval_status=provisional.approval_status,
            execution_allowed=provisional.execution_allowed,
            metadata=provisional.metadata,
        )
