from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from trading_ai.database.base import Base
from trading_ai.institutional_options.domain import (
    ContractLegRecommendation,
    ContractRecommendation,
    ContractSide,
    StrategyCandidate,
    StrategyDisposition,
)
from trading_ai.institutional_options.models import (
    ContractRecommendationModel,
    StrategyCandidateModel,
)
from trading_ai.institutional_options.repository import InstitutionalOpportunityRepository
from trading_ai.institutional_options.contract_optimization import PolygonPersistedOptionRepository


def _candidate(identifier: str, score: float) -> StrategyCandidate:
    return StrategyCandidate(
        strategy_candidate_id=identifier,
        opportunity_id="opp-1",
        strategy="LONG_CALL",
        disposition=StrategyDisposition.ELIGIBLE,
        eligibility_score=score,
        strategy_score=score,
        complexity="LOW",
        rank=1,
        selected=False,
    )


def test_strategy_upsert_uses_opportunity_strategy_natural_key():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repository = InstitutionalOpportunityRepository(session)
        repository.save_strategy_candidates([_candidate("candidate-original", 70.0)])
        session.flush()
        repository.save_strategy_candidates([_candidate("candidate-new-id", 88.0)])
        session.commit()

        rows = session.query(StrategyCandidateModel).all()
        assert len(rows) == 1
        assert rows[0].strategy_candidate_id == "candidate-original"
        assert rows[0].eligibility_score == 88.0
        assert rows[0].payload_json["strategy_candidate_id"] == "candidate-original"


def test_contract_recommendation_refreshes_same_strategy_and_snapshot():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    leg = ContractLegRecommendation(
        leg_id="leg-1",
        option_symbol="O:TEST260918C00100000",
        contract_id=None,
        expiry="2026-09-18",
        strike=100.0,
        option_type="CALL",
        side=ContractSide.BUY,
        quantity_ratio=1,
        multiplier="100",
        bid=1.0,
        ask=1.2,
        last=1.1,
        volume=10,
        open_interest=100,
        implied_volatility=0.3,
        delta=0.5,
        gamma=0.1,
        theta=-0.02,
        vega=0.05,
    )
    with Session(engine) as session:
        repository = InstitutionalOpportunityRepository(session)
        first = ContractRecommendation(
            contract_recommendation_id="contract-original",
            opportunity_id="opp-1",
            strategy_candidate_id="candidate-original",
            option_snapshot_id="snapshot-1",
            strategy="LONG_CALL",
            legs=(leg,),
            executable=True,
            liquidity_score=70.0,
            estimated_slippage=0.1,
            net_debit_credit=1.1,
        )
        second = ContractRecommendation(
            contract_recommendation_id="contract-new-id",
            opportunity_id="opp-1",
            strategy_candidate_id="candidate-original",
            option_snapshot_id="snapshot-1",
            strategy="LONG_CALL",
            legs=(leg,),
            executable=True,
            liquidity_score=95.0,
            estimated_slippage=0.05,
            net_debit_credit=1.05,
        )
        repository.save_contract_recommendation(first)
        session.flush()
        repository.save_contract_recommendation(second)
        session.commit()

        rows = session.query(ContractRecommendationModel).all()
        assert len(rows) == 1
        assert rows[0].contract_recommendation_id == "contract-original"
        assert rows[0].liquidity_score == 95.0
        assert rows[0].payload_json["contract_recommendation_id"] == "contract-original"


def test_canonical_class_share_alias_contract_is_preserved():
    assert PolygonPersistedOptionRepository.symbol_aliases("BRK-B") == (
        "BRK-B",
        "BRK.B",
        "BRKB",
    )
