from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from trading_ai.database.base import Base
from trading_ai.institutional_options.domain import StrategyComparison
from trading_ai.institutional_options.models import StrategyComparisonModel
from trading_ai.institutional_options.repository import InstitutionalOpportunityRepository


def _comparison(comparison_id: str, selected_id: str, policy: str) -> StrategyComparison:
    return StrategyComparison(
        comparison_id=comparison_id,
        opportunity_id="opp-idempotent",
        ranked_strategy_candidate_ids=(selected_id, "alternative"),
        selected_strategy_candidate_id=selected_id,
        comparison_policy_version=policy,
        rationale=(f"selected {selected_id}",),
    )


def test_strategy_comparison_rebuild_updates_singleton_by_opportunity():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repository = InstitutionalOpportunityRepository(session)
        repository.save_strategy_comparison(_comparison("cmp-first", "strategy-a", "M62-PH3-1.0"))
        session.flush()
        repository.save_strategy_comparison(_comparison("cmp-rebuild", "strategy-b", "M62-PH5-1.0"))
        session.commit()

        rows = session.query(StrategyComparisonModel).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.comparison_id == "cmp-first"
        assert row.selected_strategy_candidate_id == "strategy-b"
        assert row.policy_version == "M62-PH5-1.0"
        assert row.payload_json["comparison_id"] == "cmp-first"
        assert row.payload_json["selected_strategy_candidate_id"] == "strategy-b"
