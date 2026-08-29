from collections import Counter

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from trading_ai.analytics_dashboard.service import current_valuation_snapshot_query
from trading_ai.option_valuation_intelligence.models import OptionValuationSnapshotModel


def _snapshot(index: int, *, run_id: str, edge: float, classification: str):
    return OptionValuationSnapshotModel(
        snapshot_id=f"snapshot-{run_id}-{index}",
        contract_recommendation_id=f"contract-{run_id}-{index}",
        opportunity_id=f"opportunity-{run_id}-{index}",
        symbol=f"S{index}",
        classification=classification,
        market_mid=5.0,
        fair_value=5.0,
        mispricing_pct=(edge - 50.0) / 2.0,
        edge_score=edge,
        confidence=80.0,
        stability_index=80.0,
        state_hash=f"hash-{run_id}-{index}",
        snapshot_timestamp=f"2026-08-15T20:{index:02d}:00+00:00",
        payload_json={"valuation_run_id": run_id},
    )


def test_current_run_is_filtered_before_global_edge_order_and_limit():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    OptionValuationSnapshotModel.__table__.create(engine)

    expected = [
        "STRONG_UNDERPRICED",
        "MODERATELY_UNDERPRICED",
        "FAIR_VALUE",
        "MODERATELY_OVERPRICED",
        "STRONG_OVERPRICED",
    ]
    with Session(engine) as session:
        # Historical rows deliberately outrank every current row. The old
        # implementation limited these first, then discarded them in Python.
        session.add_all(
            _snapshot(index, run_id="HISTORICAL", edge=100.0, classification="STRONG_UNDERPRICED")
            for index in range(20)
        )
        session.add_all(
            _snapshot(index, run_id="CURRENT", edge=70.0 - index * 10, classification=classification)
            for index, classification in enumerate(expected)
        )
        session.commit()

        rows = session.execute(
            current_valuation_snapshot_query(valuation_run_id="CURRENT", limit=5)
        ).scalars().all()

    assert len(rows) == 5
    assert {row.payload_json["valuation_run_id"] for row in rows} == {"CURRENT"}
    assert Counter(row.classification for row in rows) == Counter(expected)


def test_current_run_filter_is_part_of_sql_statement_before_limit():
    statement = current_valuation_snapshot_query(
        valuation_run_id="M69-RUN-CURRENT",
        limit=344,
    )
    compiled = statement.compile()
    rendered = str(compiled)
    parameter_values = set(compiled.params.values())
    # SQLAlchemy binds both the PostgreSQL JSON key and its expected value.
    # They therefore belong to the compiled parameter contract instead of
    # necessarily appearing as literal text in the rendered SQL statement.
    assert "valuation_run_id" in parameter_values
    assert "M69-RUN-CURRENT" in parameter_values
    assert statement.whereclause is not None
    assert "WHERE" in rendered
    assert "LIMIT" in rendered
    assert rendered.index("WHERE") < rendered.index("ORDER BY") < rendered.index("LIMIT")
