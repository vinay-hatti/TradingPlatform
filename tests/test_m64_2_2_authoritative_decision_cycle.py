from __future__ import annotations

from hashlib import sha256
import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from trading_ai.institutional_options.models import (
    InstitutionalDecisionSnapshotModel,
    InstitutionalOpportunityModel,
)
from trading_ai.stock_intelligence.models import StockScannerPublicationModel
from trading_ai.portfolio_risk_allocation.decision_intelligence import (
    DecisionGenerationCoverageError,
    InstitutionalDecisionIntelligenceService,
)
from trading_ai.portfolio_risk_allocation.models import (
    PortfolioCorrelationSnapshotModel,
    PortfolioDecisionIntelligenceModel,
    PortfolioIntelligencePublicationModel,
    PortfolioRiskSnapshotModel,
)


PORTFOLIO = "PAPER-PRIMARY"
RUN = "stock-run-current"
OLD_RISK = "M64-RISK-OLD"
NEW_RISK = "M64-RISK-NEW"
OPPORTUNITY = "m62-opp-current"
DECISION = "m62-decision-current"


def _hash(payload: dict) -> str:
    return sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _risk(snapshot_id: str, timestamp: str) -> PortfolioRiskSnapshotModel:
    payload = {
        "greeks": {"delta": 0, "gamma": 0, "theta": 0, "vega": 0, "rho": 0},
        "exposures": {"symbol": {}, "sector": {}, "strategy": {}},
        "capital": {
            "net_liquidation": 1_000_000,
            "buying_power": 4_000_000,
            "capital_usage_pct": 3.0,
            "open_risk": 37_000,
            "portfolio_heat_pct": 3.7,
            "trading_risk_basis": "GOVERNED_PRE_EXPIRATION_DEFINED_LOSS",
        },
    }
    return PortfolioRiskSnapshotModel(
        snapshot_id=snapshot_id,
        portfolio_id=PORTFOLIO,
        snapshot_timestamp=timestamp,
        broker_publication_id=None,
        status="READY",
        health_score=90,
        net_liquidation=1_000_000,
        buying_power=4_000_000,
        capital_committed=30_000,
        open_risk=37_000,
        var_95=1_000,
        expected_shortfall_95=1_500,
        portfolio_heat_pct=3.7,
        concentration_score=10,
        diversification_score=90,
        payload_json=payload,
    )


def _opportunity(opportunity_id: str = OPPORTUNITY) -> InstitutionalOpportunityModel:
    return InstitutionalOpportunityModel(
        opportunity_id=opportunity_id,
        symbol="AAPL" if opportunity_id == OPPORTUNITY else "MSFT",
        asset_class="EQUITY",
        state="READY_FOR_EXECUTION",
        direction="BULLISH",
        category="TREND_CONTINUATION",
        overall_score=85,
        confidence=82,
        conviction="HIGH",
        thesis_id=f"thesis-{opportunity_id}",
        stock_publication_name="current_stock_intelligence",
        stock_scanner_run_id=RUN,
        stock_candidate_id=f"candidate-{opportunity_id}",
        stock_state_hash=f"state-{opportunity_id}",
        option_snapshot_id="options-current",
        version=1,
        created_at="2026-08-14T20:00:00+00:00",
        updated_at="2026-08-14T20:00:00+00:00",
        payload_json={"symbol": "AAPL" if opportunity_id == OPPORTUNITY else "MSFT"},
    )


def _institutional_decision(
    opportunity_id: str = OPPORTUNITY,
    decision_id: str = DECISION,
    *,
    embedded: dict | None = None,
) -> InstitutionalDecisionSnapshotModel:
    payload = {
        "symbol": "AAPL" if opportunity_id == OPPORTUNITY else "MSFT",
        "sector": "Information Technology",
        "valuation": {"capital": {"capital_required": 500}, "expected_value": 125},
        "selected_contract": {"greeks": {"delta": 0.5}},
    }
    if embedded:
        payload["portfolio_decision"] = embedded
    return InstitutionalDecisionSnapshotModel(
        decision_snapshot_id=decision_id,
        opportunity_id=opportunity_id,
        strategy_candidate_id=f"strategy-{opportunity_id}",
        contract_recommendation_id=f"contract-{opportunity_id}",
        valuation_id=f"valuation-{opportunity_id}",
        execution_recommendation_id=f"execution-{opportunity_id}",
        management_snapshot_id=f"management-{opportunity_id}",
        institutional_score=85,
        calibrated_probability=0.70,
        expected_value=125,
        capital_required=500,
        selected_strategy="LONG_CALL",
        policy_version="M62",
        state_hash=f"institutional-{opportunity_id}",
        created_at="2026-08-14T20:00:00+00:00",
        payload_json=payload,
    )


def _portfolio_decision(risk_id: str, status: str = "CURRENT") -> dict:
    return {
        "policy_version": "M64",
        "symbol": "AAPL",
        "decision": "ACCEPT",
        "decision_identity": {
            "opportunity_id": OPPORTUNITY,
            "institutional_decision_snapshot_id": DECISION,
            "risk_snapshot_id": risk_id,
            "portfolio_id": PORTFOLIO,
        },
        "lifecycle": {
            "status": status,
            "source_stock_scanner_run_id": RUN,
            "risk_snapshot_id": risk_id,
        },
    }


class _PinnedRiskStub:
    def __init__(self, factory):
        self.factory = factory
        self.seen_risk_ids: list[str | None] = []

    def snapshot(self, portfolio_id, risk_snapshot_id=None):
        with self.factory() as session:
            row = session.get(PortfolioRiskSnapshotModel, risk_snapshot_id)
            return None if row is None else {
                column.name: getattr(row, column.name) for column in row.__table__.columns
            }

    def assess(self, candidate, portfolio_id, *, risk_snapshot_id=None):
        self.seen_risk_ids.append(risk_snapshot_id)
        return {
            "assessment_status": "READY",
            "input_integrity": {
                "status": "READY",
                "net_liquidation": 1_000_000,
                "buying_power": 4_000_000,
                "risk_snapshot_id": risk_snapshot_id,
            },
            "portfolio_fit_score": 85,
            "decision": "ACCEPT",
            "recommended_quantity": 1,
            "recommended_capital": 500,
            "current_portfolio_heat_pct": 3.7,
            "marginal_portfolio_heat_pct": 0.05,
            "projected_portfolio_heat_pct": 3.75,
            "remaining_portfolio_heat_capacity_pct": 16.25,
            "blocking_reasons": [],
            "rule_evaluations": [],
            "policy_thresholds": {},
        }


@pytest.fixture()
def factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    tables = [
        StockScannerPublicationModel.__table__,
        InstitutionalOpportunityModel.__table__,
        InstitutionalDecisionSnapshotModel.__table__,
        PortfolioRiskSnapshotModel.__table__,
        PortfolioCorrelationSnapshotModel.__table__,
        PortfolioDecisionIntelligenceModel.__table__,
        PortfolioIntelligencePublicationModel.__table__,
    ]
    for table in tables:
        table.create(engine, checkfirst=True)
    session_factory = sessionmaker(engine, expire_on_commit=False)
    old_payload = _portfolio_decision(OLD_RISK)
    with session_factory() as session:
        session.add(StockScannerPublicationModel(
            id="publication-stock",
            symbol="ALL",
            scanner_run_id=RUN,
            candidate_id=None,
            snapshot_timestamp="2026-08-14T20:00:00+00:00",
            payload_json={},
            publication_name="current_stock_intelligence",
            status="READY",
        ))
        session.add_all([
            _risk(OLD_RISK, "2026-08-14T20:00:00+00:00"),
            _risk(NEW_RISK, "2026-08-14T20:05:00+00:00"),
            _opportunity(),
            _institutional_decision(embedded=old_payload),
            PortfolioDecisionIntelligenceModel(
                decision_intelligence_id="M64-DI-OLD",
                portfolio_id=PORTFOLIO,
                opportunity_id=OPPORTUNITY,
                institutional_decision_snapshot_id=DECISION,
                risk_snapshot_id=OLD_RISK,
                portfolio_fit_score=80,
                opportunity_cost_score=80,
                final_portfolio_score=80,
                recommended_quantity=1,
                recommended_capital=500,
                decision="ACCEPT",
                rank=1,
                state_hash=_hash(old_payload),
                created_at="2026-08-14T20:00:00+00:00",
                payload_json=old_payload,
            ),
            PortfolioIntelligencePublicationModel(
                publication_id="M64-PUB-CURRENT",
                publication_name="current_portfolio_allocation",
                portfolio_id=PORTFOLIO,
                risk_snapshot_id=OLD_RISK,
                optimization_snapshot_id="M64-OPT-OLD",
                published_at="2026-08-14T20:00:00+00:00",
                status="READY",
                payload_json={"stock_scanner_run_id": RUN, "risk_snapshot_id": OLD_RISK},
            ),
        ])
        session.commit()
    return session_factory


def test_generation_is_staged_until_atomic_activation(factory):
    service = InstitutionalDecisionIntelligenceService(factory)
    stub = _PinnedRiskStub(factory)
    service.risk_service = stub

    generated = service.build(
        PORTFOLIO,
        risk_snapshot_id=NEW_RISK,
        require_complete=True,
    )

    assert generated["eligible"] == generated["built"] == 1
    assert generated["coverage_pct"] == 100.0
    assert generated["authority_status"] == "STAGED_COMPLETE"
    assert stub.seen_risk_ids == [NEW_RISK]
    with factory() as session:
        old = session.scalar(select(PortfolioDecisionIntelligenceModel).where(
            PortfolioDecisionIntelligenceModel.risk_snapshot_id == OLD_RISK
        ))
        new = session.scalar(select(PortfolioDecisionIntelligenceModel).where(
            PortfolioDecisionIntelligenceModel.risk_snapshot_id == NEW_RISK
        ))
        publication = session.get(PortfolioIntelligencePublicationModel, "M64-PUB-CURRENT")
        decision = session.get(InstitutionalDecisionSnapshotModel, DECISION)
        assert old.payload_json["lifecycle"]["status"] == "CURRENT"
        assert new.payload_json["lifecycle"]["status"] == "STAGED"
        assert publication.risk_snapshot_id == OLD_RISK
        assert decision.payload_json["portfolio_decision"]["decision_identity"]["risk_snapshot_id"] == OLD_RISK

    with factory() as session:
        activation = service.activate_generation(
            session,
            portfolio_id=PORTFOLIO,
            risk_snapshot_id=NEW_RISK,
            stock_scanner_run_id=RUN,
        )
        publication = session.get(PortfolioIntelligencePublicationModel, "M64-PUB-CURRENT")
        publication.risk_snapshot_id = NEW_RISK
        publication.optimization_snapshot_id = "M64-OPT-NEW"
        publication.payload_json = {"stock_scanner_run_id": RUN, "risk_snapshot_id": NEW_RISK}
        session.commit()
    assert activation["activated"] == 1
    assert activation["missing"] == 0

    with factory() as session:
        old = session.scalar(select(PortfolioDecisionIntelligenceModel).where(
            PortfolioDecisionIntelligenceModel.risk_snapshot_id == OLD_RISK
        ))
        new = session.scalar(select(PortfolioDecisionIntelligenceModel).where(
            PortfolioDecisionIntelligenceModel.risk_snapshot_id == NEW_RISK
        ))
        decision = session.get(InstitutionalDecisionSnapshotModel, DECISION)
        assert old.payload_json["lifecycle"]["status"] == "SUPERSEDED"
        assert new.payload_json["lifecycle"]["status"] == "CURRENT"
        assert decision.payload_json["portfolio_decision"]["decision_identity"]["risk_snapshot_id"] == NEW_RISK


def test_incomplete_source_coverage_never_retires_current_authority(factory):
    with factory() as session:
        session.add(_opportunity("m62-opp-missing-decision"))
        session.commit()
    service = InstitutionalDecisionIntelligenceService(factory)
    service.risk_service = _PinnedRiskStub(factory)

    with pytest.raises(DecisionGenerationCoverageError, match="lack an Institutional Options decision"):
        service.build(PORTFOLIO, risk_snapshot_id=NEW_RISK, require_complete=True)

    with factory() as session:
        old = session.scalar(select(PortfolioDecisionIntelligenceModel).where(
            PortfolioDecisionIntelligenceModel.risk_snapshot_id == OLD_RISK
        ))
        publication = session.get(PortfolioIntelligencePublicationModel, "M64-PUB-CURRENT")
        assert old.payload_json["lifecycle"]["status"] == "CURRENT"
        assert publication.risk_snapshot_id == OLD_RISK
        assert session.scalar(select(PortfolioDecisionIntelligenceModel).where(
            PortfolioDecisionIntelligenceModel.risk_snapshot_id == NEW_RISK
        )) is None


def test_current_reader_uses_publication_not_newest_unpublished_risk(factory):
    service = InstitutionalDecisionIntelligenceService(factory)
    current = service.current(OPPORTUNITY, PORTFOLIO)
    rankings = service.rankings(PORTFOLIO)
    assert current["decision_identity"]["risk_snapshot_id"] == OLD_RISK
    assert [item["decision_identity"]["risk_snapshot_id"] for item in rankings] == [OLD_RISK]
