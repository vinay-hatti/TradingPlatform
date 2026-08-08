from __future__ import annotations

from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_options_ingestion_advances_institutional_options_by_default():
    root = _root()
    options = (root / "scripts/ingest_options_data.py").read_text()
    common = (root / "scripts/ingestion_split_common.py").read_text()

    assert "--skip-institutional-options" in options
    assert "--skip-institutional-strategies" in options
    assert "--skip-institutional-contracts" in options
    assert "--skip-institutional-decisions" in options
    assert "--require-institutional-options" in options
    assert "--institutional-options-limit" in options

    assert "advance_institutional_options=not wrapper.skip_institutional_options" in options
    assert "run_institutional_strategies=not wrapper.skip_institutional_strategies" in options
    assert "run_institutional_contracts=not wrapper.skip_institutional_contracts" in options
    assert "run_institutional_decisions=not wrapper.skip_institutional_decisions" in options

    assert "InstitutionalStrategyGenerationService" in common
    assert "InstitutionalContractOptimizationService" in common
    assert "InstitutionalDecisionService" in common


def test_options_advancement_uses_separate_transactions_and_ordered_stages():
    root = _root()
    common = (root / "scripts/ingestion_split_common.py").read_text()
    function = common.split("def advance_institutional_options_workflow", 1)[1].split(
        "def date_from_args", 1
    )[0]

    assert "with SessionLocal() as session:" in function
    assert "session.commit()" in function
    assert "session.rollback()" in function

    strategy = function.index('"strategies"')
    contracts = function.index('"contracts"', strategy)
    decisions = function.index('"decisions"', contracts)
    assert strategy < contracts < decisions


def test_options_workflow_does_not_materialize_opportunities():
    root = _root()
    common = (root / "scripts/ingestion_split_common.py").read_text()
    function = common.split("def advance_institutional_options_workflow", 1)[1].split(
        "def date_from_args", 1
    )[0]

    assert "InstitutionalOpportunityIngestionService" not in function
    assert "materialize_institutional_options_opportunities" not in function


def test_options_advancement_is_reported_and_strictly_governable():
    root = _root()
    common = (root / "scripts/ingestion_split_common.py").read_text()

    assert '"institutional_options_advancement": institutional_options_advancement' in common
    assert "require_institutional_advancement" in common
    assert "Institutional Options downstream advancement encountered unexpected failures" in common
    assert '"status": "SKIPPED"' in common
