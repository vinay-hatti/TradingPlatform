from __future__ import annotations

import inspect
from pathlib import Path

from trading_ai.inflection_intelligence.models import (
    InflectionPublicationModel,
    InflectionSnapshotModel,
)
from trading_ai.institutional_options.advancement_authority import (
    AUTHORITY_KEY,
    AUTHORITY_VERSION,
)
from trading_ai.institutional_options.domain import OpportunityLineage
from trading_ai.portfolio_risk_allocation.orchestration import (
    Milestone64ContinuousPortfolioIntelligenceService,
)


ROOT = Path(__file__).resolve().parents[2]


def test_every_runtime_coverage_status_fits_persisted_contract():
    source = (ROOT / "src/trading_ai/inflection_intelligence/service.py").read_text()
    statuses = (
        "CURRENT_EXACT",
        "ABSTAIN_INCOMPLETE_BREADTH_AND_OPTIONS",
        "ABSTAIN_INCOMPLETE_BREADTH",
        "UNDERLYING_CURRENT_OPTIONS_OPTIONAL",
        "ABSTAIN_INCOMPLETE_OPTIONS",
    )
    snapshot_capacity = (
        InflectionSnapshotModel.__table__
        .c.coverage_status.type.length
    )
    publication_capacity = (
        InflectionPublicationModel.__table__
        .c.coverage_status.type.length
    )
    assert snapshot_capacity == publication_capacity == 64
    assert all(status in source for status in statuses)
    assert max(map(len, statuses)) <= snapshot_capacity


def test_versioned_option_lineage_round_trips_and_ignores_extensions():
    lineage = OpportunityLineage.from_payload({
        "stock_publication_name": "current_stock_intelligence",
        "stock_scanner_run_id": "stock-run",
        "stock_candidate_id": "candidate",
        "stock_state_hash": "hash",
        "source_option_snapshot_id": "raw-options-run",
        "contract_option_snapshot_id": "polygon-options-2026-08-16",
        "option_snapshot_id": "legacy-value",
        "future_extension": {"safe": True},
    })
    assert lineage.source_option_snapshot_id == "raw-options-run"
    assert lineage.contract_option_snapshot_id == "polygon-options-2026-08-16"
    assert lineage.option_snapshot_id == "polygon-options-2026-08-16"


def test_legacy_option_lineage_populates_both_explicit_aliases():
    lineage = OpportunityLineage.from_payload({
        "stock_publication_name": "current_stock_intelligence",
        "stock_scanner_run_id": "stock-run",
        "stock_candidate_id": "candidate",
        "stock_state_hash": "hash",
        "option_snapshot_id": "polygon-options-2026-08-15",
    })
    assert lineage.source_option_snapshot_id == lineage.option_snapshot_id
    assert lineage.contract_option_snapshot_id == lineage.option_snapshot_id


def test_m64_validates_advancement_before_building_risk():
    source = inspect.getsource(Milestone64ContinuousPortfolioIntelligenceService.run)
    assert source.index("validate_current_advancement_authority") < source.index(
        "PortfolioRiskAllocationService"
    )
    assert AUTHORITY_KEY == "institutional_options_advancement_authority"
    assert AUTHORITY_VERSION.startswith("M68.2.1.8-")


def test_exact_current_m64_materiality_and_noop_baseline_is_preserved():
    source = (
        ROOT / "src/trading_ai/portfolio_risk_allocation/orchestration.py"
    ).read_text()
    assert "M64.2.4.7-AUTHORITY-INPUT-FINGERPRINT-1.0" in source
    assert "M64.2.4.7-BASELINE-MATERIALITY-CYCLE-1.0" in source
    assert "cycle_noop_unchanged_authority" in source
    assert "suppressed_submaterial_change_count" in source


def test_options_cycle_invalidates_then_publishes_advancement_marker():
    source = (ROOT / "scripts/ingestion_split_common.py").read_text()
    assert source.index("invalidate_advancement_authority(") < source.index(
        'execute(\n        "strategies"'
    )
    assert source.index('execute(\n        "decisions"') < source.index(
        'payload["authority"] = persist_advancement_authority('
    )


def test_failed_underlying_finalization_retires_only_unmaterialized_run():
    source = (ROOT / "scripts/ingestion_split_common.py").read_text()
    assert "fail_unmaterialized_stock_publication" in source
    assert "if publication is None or opportunity_count" in source
    assert 'publication.status = "FAILED"' in source


def test_inflection_progress_uses_runtime_result_contract():
    source = (ROOT / "scripts/ingestion_split_common.py").read_text()
    assert 'diagnostics.get("disposition_counts")' in source
    assert "result.get('average_signal_strength', 0)" in source
    assert 'diagnostics.get("classifications")' not in source


def test_contract_selection_has_deterministic_prevaluation_authority():
    generation = (
        ROOT / "src/trading_ai/institutional_options/strategy_generation.py"
    ).read_text()
    optimization = (
        ROOT / "src/trading_ai/institutional_options/contract_optimization.py"
    ).read_text()
    assert "ranked_ids[0] if ranked_ids else None" in generation
    assert '"PRE_CONTRACT_RANK_AUTHORITY"' in optimization
    assert '"selection_recovered_by"' in optimization


def test_manual_wrapper_does_not_run_options_after_underlying_failure():
    source = (
        ROOT / "scripts/run_m68_2_1_8_manual_ingestion_cycle.sh"
    ).read_text()
    underlying = source.index("scripts/ingest_underlying_data.py")
    failed_exit = source.index('exit "$underlying_exit"')
    options = source.index("scripts/ingest_options_data.py")
    assert underlying < failed_exit < options
