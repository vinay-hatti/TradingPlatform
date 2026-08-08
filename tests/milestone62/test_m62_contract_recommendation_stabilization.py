from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from trading_ai.database.base import Base
from trading_ai.institutional_options.contract_optimization import (
    ContractOptimizationPolicy,
    ExactPolygonContractOptimizer,
    OptionContractRecord,
    PolygonPersistedOptionRepository,
)
from trading_ai.institutional_options.domain import StrategyCandidate, StrategyDisposition
from trading_ai.institutional_options.models import ContractRecommendationModel
from trading_ai.institutional_options.repository import InstitutionalOpportunityRepository


def candidate(strategy="LONG_CALL"):
    return StrategyCandidate(
        strategy_candidate_id="strategy-1", opportunity_id="opportunity-1", strategy=strategy,
        disposition=StrategyDisposition.ELIGIBLE, eligibility_score=90.0, complexity="LOW",
    )


def contract(symbol="O:TEST260918C00100000", option_type="CALL", strike=100.0, delta=.55):
    return OptionContractRecord(
        option_symbol=symbol, quote_date=date(2026, 8, 4), expiry=date(2026, 9, 18),
        option_type=option_type, strike=strike, bid=4.8, ask=5.0, last=4.9, volume=100,
        open_interest=1000, implied_volatility=.30, delta=delta, gamma=.05, theta=-.04, vega=.10,
    )


def test_recommendation_payload_contains_strategy_and_scorecard():
    recommendation = ExactPolygonContractOptimizer().optimize(
        candidate(), [contract()], 100.0, "options-snapshot",
    )
    assert recommendation.executable is True
    assert recommendation.strategy == "LONG_CALL"
    assert recommendation.rejection_reasons == ()
    assert recommendation.optimization_scores["overall_contract_score"] > 0


def test_non_executable_payload_contains_rejection_reasons():
    recommendation = ExactPolygonContractOptimizer().optimize(
        candidate("BULL_CALL_SPREAD"), [contract()], 100.0, "options-snapshot",
    )
    assert recommendation.executable is False
    assert recommendation.strategy == "BULL_CALL_SPREAD"
    assert recommendation.rejection_reasons
    assert recommendation.optimization_scores["overall_contract_score"] == 0


def test_recommendation_metadata_persists_in_payload():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        recommendation = ExactPolygonContractOptimizer().optimize(
            candidate(), [contract()], 100.0, "options-snapshot",
        )
        InstitutionalOpportunityRepository(session).save_contract_recommendation(recommendation)
        session.commit()
        row = session.get(ContractRecommendationModel, recommendation.contract_recommendation_id)
        assert row.payload_json["strategy"] == "LONG_CALL"
        assert row.payload_json["optimization_scores"]["overall_contract_score"] > 0


def test_class_share_symbol_aliases_are_supported():
    assert PolygonPersistedOptionRepository.symbol_aliases("BRK-B") == ("BRK-B", "BRK.B", "BRKB")
    assert PolygonPersistedOptionRepository.symbol_aliases("BF.B") == ("BF.B", "BF-B", "BFB")
