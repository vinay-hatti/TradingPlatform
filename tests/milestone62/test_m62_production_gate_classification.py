from __future__ import annotations

from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_options_gate_separates_governed_outcomes_from_unexpected_failures():
    root = _root()
    common = (root / "scripts/ingestion_split_common.py").read_text()
    function = common.split("def advance_institutional_options_workflow", 1)[1].split(
        "def date_from_args", 1
    )[0]

    assert "GOVERNED_NO_STRATEGY" in function
    assert "GOVERNED_NO_CONTRACT" in function
    assert "MISSING_OPTION_DATA" in function
    assert "UNEXPECTED_FAILURE" in function
    assert '"governed_no_strategy"' in function
    assert '"governed_no_contract"' in function
    assert '"missing_option_data"' in function
    assert '"unexpected_failures"' in function
    assert "require_success and unexpected_failures" in function


def test_options_gate_supports_separate_complete_coverage_policy():
    root = _root()
    options = (root / "scripts/ingest_options_data.py").read_text()
    common = (root / "scripts/ingestion_split_common.py").read_text()

    assert "--require-institutional-options-complete" in options
    assert "require_institutional_advancement_complete" in options
    assert "require_complete=require_institutional_advancement_complete" in common
    assert "require_complete and completeness_failures" in common


def test_options_final_report_contains_production_counters():
    root = _root()
    common = (root / "scripts/ingestion_split_common.py").read_text()

    for counter in (
        "strategies_generated",
        "governed_no_strategy",
        "contracts_optimized",
        "governed_no_contract",
        "missing_option_data",
        "unexpected_failures",
        "decisions_created",
        "decisions_refreshed",
    ):
        assert f'"{counter}"' in common
    assert "Institutional Options advancement summary" in common
