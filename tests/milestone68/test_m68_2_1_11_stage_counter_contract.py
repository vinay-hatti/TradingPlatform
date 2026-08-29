from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

from trading_ai.institutional_options.domain import (
    InstitutionalOpportunity,
    OpportunityState,
    ThesisDirection,
)
from trading_ai.institutional_options.valuation import (
    InstitutionalStrategyValuationService,
)


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import ingestion_split_common


def opportunity_payload() -> dict:
    return {
        "opportunity_id": "m62-opp-test",
        "symbol": "XLE",
        "asset_class": "EQUITY",
        "state": "CONTRACTS_OPTIMIZED",
        "direction": "BULLISH",
        "category": "BULLISH",
        "overall_score": 72.5,
        "confidence": 91.0,
        "conviction": "MODERATE",
        "lineage": {
            "stock_publication_name": "current_stock_intelligence",
            "stock_scanner_run_id": "stock-run",
            "stock_candidate_id": "candidate",
            "stock_state_hash": "hash",
            "source_option_snapshot_id": "options-run",
            "contract_option_snapshot_id": "polygon-options-2026-08-16",
        },
        "thesis_id": "m62-thesis-test",
        "metadata": {"execution_disposition": "WAITING_FOR_ENTRY"},
        "inflection_intelligence": {
            "direction": "BULLISH",
            "signal_strength": 72.0,
        },
        "future_evidence_contract": {"version": "M99"},
    }


def test_versioned_opportunity_payload_accepts_inflection_and_future_evidence():
    opportunity = InstitutionalOpportunity.from_payload(opportunity_payload())
    assert opportunity.state is OpportunityState.CONTRACTS_OPTIMIZED
    assert opportunity.direction is ThesisDirection.BULLISH
    assert opportunity.inflection_intelligence["signal_strength"] == 72.0
    assert opportunity.intelligence_extensions["future_evidence_contract"] == {
        "version": "M99"
    }
    assert opportunity.lineage.option_snapshot_id == (
        "polygon-options-2026-08-16"
    )


def test_valuation_uses_versioned_opportunity_deserializer():
    source = inspect.getsource(InstitutionalStrategyValuationService.value)
    assert "InstitutionalOpportunity.from_payload" in source
    assert "InstitutionalOpportunity(\n                        **" not in source


def test_decision_reconciles_incomplete_ready_prerequisites():
    source = (
        ROOT / "src/trading_ai/institutional_options/decision.py"
    ).read_text()
    assert "_ready_chain_is_complete" in source
    assert "invalidate_ready_for_execution" in source
    assert "M68.2.1.10-DECISION-PREREQUISITES-1.0" in source


def test_conditional_entry_is_governed_not_an_advancement_failure():
    decision = (
        ROOT / "src/trading_ai/institutional_options/decision.py"
    ).read_text()
    advancement = (ROOT / "scripts/ingestion_split_common.py").read_text()
    authority = (
        ROOT
        / "src/trading_ai/institutional_options/advancement_authority.py"
    ).read_text()
    assert "governed_not_ready" in decision
    assert 'disposition != "READY_NOW"' in decision
    assert 'summary["governed_not_ready"]' in advancement
    assert '"governed_not_ready"' in authority


def _summary() -> dict[str, int]:
    return {
        "governed_no_strategy": 0,
        "governed_no_contract": 0,
        "missing_option_data": 0,
        "governed_not_ready": 0,
        "reconciled_ready": 0,
        "unexpected_failures": 0,
    }


def test_runtime_shaped_stage_counters_merge_without_keyerror_or_double_count():
    summary = _summary()
    payload = {
        "requested": 362,
        "created": 28,
        "governed_not_ready": 45,
        "reconciled_ready": 19,
    }
    classified = {
        "governed_no_strategy": 1,
        "governed_no_contract": 2,
        "missing_option_data": 3,
        "unexpected_failures": 0,
    }

    ingestion_split_common.merge_advancement_stage_counters(
        summary=summary,
        payload=payload,
        classified_counts=classified,
    )

    assert summary == {
        "governed_no_strategy": 1,
        "governed_no_contract": 2,
        "missing_option_data": 3,
        "governed_not_ready": 45,
        "reconciled_ready": 19,
        "unexpected_failures": 0,
    }


def test_stage_result_counters_default_to_zero_and_reject_negative_values():
    summary = _summary()
    ingestion_split_common.merge_advancement_stage_counters(
        summary=summary,
        payload={},
        classified_counts={},
    )
    assert summary == _summary()

    with pytest.raises(ValueError, match="cannot be negative"):
        ingestion_split_common.merge_advancement_stage_counters(
            summary=summary,
            payload={"governed_not_ready": -1},
            classified_counts={},
        )


def test_stage_counter_namespaces_are_not_cross_indexed():
    source = (ROOT / "scripts/ingestion_split_common.py").read_text()
    assert "summary[key] += counts[key]" not in source
    assert "merge_advancement_stage_counters(" in source


def test_recovery_preflight_resumes_partially_materialized_latest_run():
    source = (
        ROOT / "scripts/run_m68_2_1_10_resume_ingestion_authority.py"
    ).read_text()
    assert "RESUME_PARTIAL_ADVANCEMENT" in source
    assert "LATEST_AUTHORITY_ALREADY_COMPLETE" in source
    assert "advancement_fingerprint" in source
    target_section = source[
        source.index("def preflight()") : source.index("def retire_older_orphans")
    ]
    assert "~exists().where" not in target_section.split(
        "older_orphan_rows", 1
    )[0]


def test_recovery_rematerialization_is_explicitly_idempotent():
    source = (
        ROOT / "scripts/run_m68_2_1_10_resume_ingestion_authority.py"
    ).read_text()
    assert "Materialization is continuity-key idempotent" in source
    assert "m68-2-1-10-resumable-controlled-recovery" in source
