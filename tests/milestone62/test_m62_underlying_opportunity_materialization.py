from __future__ import annotations

from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_underlying_ingestion_materializes_institutional_options_by_default():
    root = _root()
    underlying = (root / "scripts/ingest_underlying_data.py").read_text()
    common = (root / "scripts/ingestion_split_common.py").read_text()

    assert "--skip-institutional-options" in underlying
    assert "--require-institutional-options" in underlying
    assert "materialize_institutional_options=not wrapper.skip_institutional_options" in underlying
    assert "InstitutionalOpportunityIngestionService" in common
    assert "session.commit()" in common
    assert 'publication_name=args.stock_intelligence_publication_name' in common


def test_materialization_runs_after_stock_publication_and_before_report_completion():
    root = _root()
    common = (root / "scripts/ingestion_split_common.py").read_text()

    stock_index = common.index("stock_publication = core._publish_stock_intelligence")
    materialize_index = common.index("materialize_institutional_options_opportunities(", stock_index)
    report_index = common.index('"institutional_options": institutional_options', materialize_index)
    assert stock_index < materialize_index < report_index


def test_underlying_materialization_is_failure_isolated_and_governable():
    root = _root()
    common = (root / "scripts/ingestion_split_common.py").read_text()

    assert '"status": "FAILED"' in common
    assert "if require_institutional_options:" in common
    assert "Institutional Options materialization failed" in common
    assert '"status": "SKIPPED"' in common


def test_underlying_stage_does_not_run_options_dependent_pipeline():
    root = _root()
    common = (root / "scripts/ingestion_split_common.py").read_text()
    function = common.split("def materialize_institutional_options_opportunities", 1)[1].split("def finalize_shared_state", 1)[0]

    assert "InstitutionalOpportunityIngestionService" in function
    for forbidden in (
        "InstitutionalStrategyGenerationService",
        "InstitutionalContractOptimizationService",
        "InstitutionalStrategyValuationService",
        "InstitutionalDecisionService",
    ):
        assert forbidden not in function
