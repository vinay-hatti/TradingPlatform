from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from trading_ai.institutional_options.models import (
    InstitutionalDecisionSnapshotModel,
    InstitutionalOpportunityModel,
)
from trading_ai.portfolio_risk_allocation import orchestration as orchestration_module
from trading_ai.portfolio_risk_allocation.models import (
    PortfolioDecisionIntelligenceModel,
    PortfolioIntelligencePublicationModel,
    PortfolioOptimizationSnapshotModel,
    PortfolioRiskSnapshotModel,
)
from trading_ai.portfolio_risk_allocation.orchestration import (
    Milestone64ContinuousPortfolioIntelligenceService,
)
from trading_ai.portfolio_risk_allocation.optimizer import (
    PortfolioOptimizationService,
)
from trading_ai.portfolio_risk_allocation.service import (
    PortfolioRiskAllocationService,
)
from trading_ai.portfolio_management.database_models import (
    PortfolioPositionModel,
)
from trading_ai.stock_intelligence.models import StockScannerPublicationModel


PORTFOLIO = "PAPER-PRIMARY"
RUN = "stock-run-current"
RISK = "M64-RISK-CURRENT"
OPPORTUNITY = "m62-opp-current"
INSTITUTIONAL_DECISION = "m62-decision-current"
OPTIMIZATION = "M64-OPT-CURRENT"
PUBLICATION = "M64-PUB-CURRENT"


def _hash(payload: dict) -> str:
    return sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _risk_payload() -> dict:
    return {
        "policy_version": PortfolioRiskAllocationService.POLICY_VERSION,
        "generated_by": "test-actor",
        "position_count": 1,
        "greeks": {"delta": 10, "gamma": 1, "theta": -2, "vega": 3},
        "exposures": {
            "symbol": {"AAPL": 1_000},
            "sector": {"Technology": 1_000},
            "strategy": {"LONG_CALL": 1_000},
        },
        "capital": {
            "net_liquidation": 100_000,
            "buying_power": 200_000,
            "capital_usage_pct": 1.0,
            "open_risk": 500,
            "portfolio_heat_pct": 0.5,
            "trading_risk_basis": "GOVERNED_PRE_EXPIRATION_DEFINED_LOSS",
        },
        "risk": {"var_95_one_day": 250, "expected_shortfall_95_one_day": 350},
        "positions": [
            {"symbol": "AAPL", "quantity": 1, "option_mark": 5.0},
        ],
    }


def _risk_dict(*, actor: str = "test-actor") -> dict:
    payload = _risk_payload()
    payload["generated_by"] = actor
    snapshot = {
        "snapshot_id": RISK,
        "portfolio_id": PORTFOLIO,
        "snapshot_timestamp": "2026-08-15T18:00:00+00:00",
        "broker_publication_id": None,
        "status": "READY",
        "health_score": 95,
        "net_liquidation": 100_000,
        "buying_power": 200_000,
        "capital_committed": 1_000,
        "open_risk": 500,
        "var_95": 250,
        "expected_shortfall_95": 350,
        "portfolio_heat_pct": 0.5,
        "concentration_score": 10,
        "diversification_score": 90,
        "payload_json": payload,
    }
    payload["semantic_fingerprint"] = (
        PortfolioRiskAllocationService.semantic_fingerprint(snapshot)
    )
    payload["state_integrity_fingerprint"] = (
        PortfolioRiskAllocationService.state_integrity_fingerprint(snapshot)
    )
    return snapshot


def _portfolio_decision() -> dict:
    return {
        "decision": "ACCEPT",
        "decision_identity": {
            "portfolio_id": PORTFOLIO,
            "opportunity_id": OPPORTUNITY,
            "institutional_decision_snapshot_id": INSTITUTIONAL_DECISION,
            "risk_snapshot_id": RISK,
        },
        "lifecycle": {
            "status": "CURRENT",
            "source_stock_scanner_run_id": RUN,
            "risk_snapshot_id": RISK,
        },
    }


def _factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        StockScannerPublicationModel.__table__,
        InstitutionalOpportunityModel.__table__,
        InstitutionalDecisionSnapshotModel.__table__,
        PortfolioRiskSnapshotModel.__table__,
        PortfolioDecisionIntelligenceModel.__table__,
        PortfolioOptimizationSnapshotModel.__table__,
        PortfolioIntelligencePublicationModel.__table__,
    ):
        table.create(engine, checkfirst=True)
    factory = sessionmaker(engine, expire_on_commit=False)
    risk = _risk_dict()
    with factory() as session:
        session.add(StockScannerPublicationModel(
            id="stock-publication",
            symbol="ALL",
            scanner_run_id=RUN,
            candidate_id=None,
            snapshot_timestamp="2026-08-15T18:00:00+00:00",
            payload_json={},
            publication_name="current_stock_intelligence",
            status="READY",
        ))
        session.add(InstitutionalOpportunityModel(
            opportunity_id=OPPORTUNITY,
            symbol="AAPL",
            asset_class="EQUITY",
            state="READY_FOR_EXECUTION",
            direction="BULLISH",
            category="TREND_CONTINUATION",
            overall_score=85,
            confidence=82,
            conviction="HIGH",
            thesis_id="thesis-current",
            stock_publication_name="current_stock_intelligence",
            stock_scanner_run_id=RUN,
            stock_candidate_id="candidate-current",
            stock_state_hash="stock-state-current",
            option_snapshot_id="option-snapshot-current",
            version=3,
            created_at="2026-08-15T18:00:00+00:00",
            updated_at="2026-08-15T18:00:00+00:00",
            payload_json={},
        ))
        session.add(InstitutionalDecisionSnapshotModel(
            decision_snapshot_id=INSTITUTIONAL_DECISION,
            opportunity_id=OPPORTUNITY,
            strategy_candidate_id="strategy-current",
            contract_recommendation_id="contract-current",
            valuation_id="valuation-current",
            execution_recommendation_id="execution-current",
            management_snapshot_id="management-current",
            institutional_score=85,
            calibrated_probability=0.70,
            expected_value=125,
            capital_required=500,
            selected_strategy="LONG_CALL",
            policy_version="M62",
            state_hash="institutional-state-current",
            created_at="2026-08-15T18:00:00+00:00",
            payload_json={"symbol": "AAPL"},
        ))
        session.add(PortfolioRiskSnapshotModel(**risk))
        session.commit()
    return factory, risk


def _publish_complete_authority(factory, risk: dict) -> dict:
    service = Milestone64ContinuousPortfolioIntelligenceService(factory)
    contract = service._authority_input_contract(PORTFOLIO, risk)
    portfolio_decision = _portfolio_decision()
    with factory() as session:
        institutional = session.get(
            InstitutionalDecisionSnapshotModel,
            INSTITUTIONAL_DECISION,
        )
        institutional.payload_json = {
            **dict(institutional.payload_json or {}),
            "portfolio_decision": portfolio_decision,
        }
        session.add(PortfolioDecisionIntelligenceModel(
            decision_intelligence_id="M64-DI-CURRENT",
            portfolio_id=PORTFOLIO,
            opportunity_id=OPPORTUNITY,
            institutional_decision_snapshot_id=INSTITUTIONAL_DECISION,
            risk_snapshot_id=RISK,
            portfolio_fit_score=80,
            opportunity_cost_score=80,
            final_portfolio_score=80,
            recommended_quantity=1,
            recommended_capital=500,
            decision="ACCEPT",
            rank=1,
            state_hash=_hash(portfolio_decision),
            created_at="2026-08-15T18:00:00+00:00",
            payload_json=portfolio_decision,
        ))
        session.add(PortfolioOptimizationSnapshotModel(
            optimization_snapshot_id=OPTIMIZATION,
            portfolio_id=PORTFOLIO,
            risk_snapshot_id=RISK,
            generated_at="2026-08-15T18:00:00+00:00",
            status="READY",
            objective_score=80,
            selected_count=1,
            recommended_capital=500,
            state_hash="optimization-state-current",
            payload_json={"stock_scanner_run_id": RUN},
        ))
        session.add(PortfolioIntelligencePublicationModel(
            publication_id=PUBLICATION,
            publication_name=PortfolioOptimizationService.PUBLICATION_NAME,
            portfolio_id=PORTFOLIO,
            risk_snapshot_id=RISK,
            optimization_snapshot_id=OPTIMIZATION,
            published_at="2026-08-15T18:00:00+00:00",
            status="READY",
            payload_json={
                "stock_scanner_run_id": RUN,
                "authority_input": service._publication_authority_input(contract),
                "objective": {"selected_count": 1},
                "recommended_actions": [],
            },
        ))
        session.commit()
    return contract


def test_risk_semantic_fingerprint_excludes_only_observation_metadata():
    first = _risk_dict(actor="scheduled-owner")
    second = _risk_dict(actor="operator")
    second["snapshot_id"] = "M64-RISK-OTHER"
    second["snapshot_timestamp"] = "2026-08-15T18:05:00+00:00"
    second["payload_json"]["positions"] = list(
        reversed(second["payload_json"]["positions"])
    )

    assert (
        PortfolioRiskAllocationService.semantic_fingerprint(first)
        == PortfolioRiskAllocationService.semantic_fingerprint(second)
    )

    changed = _risk_dict()
    changed["payload_json"]["positions"][0]["option_mark"] = 5.25
    assert (
        PortfolioRiskAllocationService.semantic_fingerprint(first)
        != PortfolioRiskAllocationService.semantic_fingerprint(changed)
    )


def test_authority_fingerprint_changes_when_institutional_input_changes():
    factory, risk = _factory()
    service = Milestone64ContinuousPortfolioIntelligenceService(factory)
    first = service._authority_input_contract(PORTFOLIO, risk)

    with factory() as session:
        decision = session.get(
            InstitutionalDecisionSnapshotModel,
            INSTITUTIONAL_DECISION,
        )
        decision.state_hash = "institutional-state-changed"
        session.commit()

    second = service._authority_input_contract(PORTFOLIO, risk)
    assert first["eligible_decision_count"] == 1
    assert first["missing_institutional_decisions"] == []
    assert first["fingerprint"] != second["fingerprint"]


def test_authority_fingerprint_covers_correlation_and_optimizer_position_inputs():
    factory, risk = _factory()
    engine = factory.kw["bind"]
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE price_history (symbol TEXT, date TEXT, close REAL)"
        ))
    PortfolioPositionModel.__table__.create(engine, checkfirst=True)
    service = Milestone64ContinuousPortfolioIntelligenceService(factory)
    first = service._authority_input_contract(PORTFOLIO, risk)

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO price_history(symbol, date, close) "
                "VALUES ('AAPL', '2026-08-15', 230.0)"
            )
        )
    second = service._authority_input_contract(PORTFOLIO, risk)
    assert (
        first["correlation_input_fingerprint"]
        != second["correlation_input_fingerprint"]
    )

    with factory() as session:
        session.add(PortfolioPositionModel(
            position_id="position-current",
            portfolio_id=PORTFOLIO,
            symbol="AAPL",
            strategy_id="strategy-current",
            strategy_type="LONG_CALL",
            direction="LONG",
            status="OPEN",
            quantity=1,
            entry_price=5.0,
            current_price=5.0,
            capital_committed=500,
            maximum_loss=500,
            maximum_profit=None,
            realized_pnl=0,
            unrealized_pnl=0,
            opened_at="2026-08-15T18:00:00+00:00",
            updated_at="2026-08-15T18:00:00+00:00",
            sector="Technology",
            industry="Software",
            correlation_group="Technology",
            delta=0,
            gamma=0,
            theta=0,
            vega=0,
            rho=0,
            source_artifact="test",
            metadata_json={},
        ))
        session.commit()
    third = service._authority_input_contract(PORTFOLIO, risk)
    assert (
        second["optimizer_position_fingerprint"]
        != third["optimizer_position_fingerprint"]
    )
    assert second["fingerprint"] != third["fingerprint"]


def test_current_authority_validation_is_exact_and_fail_closed():
    factory, risk = _factory()
    contract = _publish_complete_authority(factory, risk)
    service = Milestone64ContinuousPortfolioIntelligenceService(factory)

    validation = service._current_authority_validation(PORTFOLIO, contract)
    assert validation["status"] == "VALID"
    assert all(validation["checks"].values())
    assert validation["decision_count"] == 1
    assert validation["embedded_decision_count"] == 1

    with factory() as session:
        risk_row = session.get(PortfolioRiskSnapshotModel, RISK)
        risk_row.net_liquidation += 1
        session.commit()

    invalid_risk = service._current_authority_validation(PORTFOLIO, contract)
    assert invalid_risk["status"] == "INVALID"
    assert invalid_risk["checks"]["risk_fingerprint_integrity"] is False

    with factory() as session:
        risk_row = session.get(PortfolioRiskSnapshotModel, RISK)
        risk_row.net_liquidation -= 1
        session.commit()

    with factory() as session:
        institutional = session.get(
            InstitutionalDecisionSnapshotModel,
            INSTITUTIONAL_DECISION,
        )
        payload = dict(institutional.payload_json or {})
        embedded = dict(payload["portfolio_decision"])
        identity = dict(embedded["decision_identity"])
        identity["risk_snapshot_id"] = "M64-RISK-STALE"
        embedded["decision_identity"] = identity
        payload["portfolio_decision"] = embedded
        institutional.payload_json = payload
        session.commit()

    invalid = service._current_authority_validation(PORTFOLIO, contract)
    assert invalid["status"] == "INVALID"
    assert invalid["checks"]["embedded_decisions_current"] is False


def test_unchanged_scheduled_cycle_is_noop_but_retention_still_runs(monkeypatch):
    calls = {
        "risk_build": [],
        "risk_persist": 0,
        "decision_build": 0,
        "optimizer_build": 0,
        "retention": 0,
    }
    risk = _risk_dict()

    class FakeRiskService:
        def __init__(self, factory):
            self.factory = factory

        def build(self, portfolio_id, actor, *, persist=True):
            calls["risk_build"].append(persist)
            return risk

        def persist(self, snapshot):
            calls["risk_persist"] += 1
            return snapshot

        def snapshot(self, portfolio_id, risk_snapshot_id=None):
            return risk

    class FakeDecisionService:
        def __init__(self, factory):
            self.factory = factory

        def build(self, *args, **kwargs):
            calls["decision_build"] += 1
            raise AssertionError("unchanged cycle must not rebuild decisions")

    class FakeOptimizerService:
        def __init__(self, factory):
            self.factory = factory

        def build(self, *args, **kwargs):
            calls["optimizer_build"] += 1
            raise AssertionError("unchanged cycle must not rebuild optimizer")

    class FakeHistoryService:
        def __init__(self, factory):
            self.factory = factory

        def prune_expired_history(self, portfolio_id, progress=None):
            calls["retention"] += 1
            return {"status": "COMPLETE", "pruned": 0}

    monkeypatch.setattr(
        orchestration_module,
        "PortfolioRiskAllocationService",
        FakeRiskService,
    )
    monkeypatch.setattr(
        orchestration_module,
        "InstitutionalDecisionIntelligenceService",
        FakeDecisionService,
    )
    monkeypatch.setattr(
        orchestration_module,
        "PortfolioOptimizationService",
        FakeOptimizerService,
    )
    monkeypatch.setattr(
        orchestration_module,
        "M64DecisionHistoryPurgeService",
        FakeHistoryService,
    )

    service = Milestone64ContinuousPortfolioIntelligenceService(lambda: None)

    @contextmanager
    def lock(*args, **kwargs):
        yield {"wait_seconds": 0.0, "lock_key": "test", "acquired_at": "now"}

    contract = {
        "fingerprint": "unchanged-fingerprint",
        "risk_semantic_fingerprint": risk["payload_json"][
            "semantic_fingerprint"
        ],
        "stock_scanner_run_id": RUN,
        "eligible_decision_count": 1,
        "missing_institutional_decisions": [],
        "_opportunity_ids": (OPPORTUNITY,),
    }
    validation = {
        "status": "VALID",
        "publication_status": "READY",
        "checks": {"fingerprint_matches": True},
        "publication_id": PUBLICATION,
        "risk_snapshot_id": RISK,
        "optimization_snapshot_id": OPTIMIZATION,
        "eligible_decision_count": 1,
        "decision_count": 1,
        "embedded_decision_count": 1,
        "selected_count": 1,
        "action_count": 0,
    }
    service._cycle_lock = lock
    service._authority_input_contract = lambda portfolio_id, candidate: contract
    service._current_authority_validation = (
        lambda portfolio_id, candidate: validation
    )
    events: list[str] = []

    result = service.run(
        PORTFOLIO,
        skip_unchanged_authority=True,
        progress=lambda stage, details: events.append(stage),
    )

    assert result["status"] == "READY"
    assert result["cycle_outcome"] == "NO_CHANGE"
    assert result["authoritative_rebuild_performed"] is False
    assert result["superseded_decision_count"] == 0
    assert calls == {
        "risk_build": [False],
        "risk_persist": 0,
        "decision_build": 0,
        "optimizer_build": 0,
        "retention": 1,
    }
    assert "cycle_noop_unchanged_authority" in events


def test_scheduler_enables_noop_by_default_and_exposes_force_override():
    root = Path(__file__).resolve().parents[1]
    source = (root / "scripts/run_m64_portfolio_intelligence.py").read_text()
    assert "skip_unchanged_authority=not force_authoritative_rebuild" in source
    assert "--force-authoritative-rebuild" in source
    assert "force_authoritative_rebuild: bool = False" in source
