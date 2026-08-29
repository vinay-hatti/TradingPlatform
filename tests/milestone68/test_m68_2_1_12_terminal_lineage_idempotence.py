from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import trading_ai.institutional_options.opportunity_ingestion as ingestion
from trading_ai.institutional_options.opportunity_ingestion import (
    EligibilityDecision,
    ExistingOpportunityResolution,
    InstitutionalOpportunityIngestionService,
    _build_existing_opportunity_resolution,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    ROOT
    / "tests/milestone68/fixtures/"
    "m68_2_1_12_terminal_lineage_collisions.json"
)


def _namespace(payload: dict) -> SimpleNamespace:
    return SimpleNamespace(**payload)


def _load_fixture():
    payload = json.loads(FIXTURE.read_text())
    candidates = [
        _namespace(row["candidate"]) for row in payload["rows"]
    ]
    exact_rows = [
        _namespace(row["exact_current_lineage_owner"])
        for row in payload["rows"]
    ]
    logical_rows = [
        _namespace(row["older_logical_owner"])
        for row in payload["rows"]
    ]
    return payload, candidates, exact_rows, logical_rows


def test_all_68_persisted_terminal_collisions_select_exact_owner():
    payload, candidates, exact_rows, logical_rows = _load_fixture()
    resolution = _build_existing_opportunity_resolution(
        candidates=candidates,
        exact_rows=exact_rows,
        continuity_rows=logical_rows,
    )

    assert payload["collision_count"] == 68
    assert len(resolution.exact_by_candidate) == 68
    assert len(resolution.terminal_exact_candidate_ids) == 68
    assert len(resolution.prevented_collision_candidate_ids) == 68
    assert len(resolution.prevented_collision_symbols) == 68
    assert resolution.unsafe_logical_claims == {}
    assert resolution.exact_symbol_mismatches == ()

    fixture_by_candidate = {
        row["candidate"]["id"]: row for row in payload["rows"]
    }
    for candidate_id in resolution.prevented_collision_candidate_ids:
        fixture_row = fixture_by_candidate[candidate_id]
        exact = resolution.exact_by_candidate[candidate_id]
        logical = fixture_row["older_logical_owner"]
        assert exact.opportunity_id == (
            fixture_row["exact_current_lineage_owner"]["opportunity_id"]
        )
        assert exact.state == "REJECTED"
        assert exact.opportunity_id != logical["opportunity_id"]


def test_logical_owner_cannot_be_claimed_by_two_unmaterialized_candidates():
    candidate = _namespace({
        "id": "candidate-a",
        "symbol": "EXPE",
        "payload_json": {
            "direction": "BULLISH",
            "primary_timeframe": "1d",
            "scores": {"primary_category": "BULLISH"},
        },
    })
    second = _namespace({
        "id": "candidate-b",
        "symbol": "EXPE",
        "payload_json": dict(candidate.payload_json),
    })
    logical = _namespace({
        "opportunity_id": "older-opportunity",
        "stock_candidate_id": "older-candidate",
        "symbol": "EXPE",
        "state": "READY_FOR_EXECUTION",
        "direction": "BULLISH",
        "category": "BULLISH",
        "payload_json": {
            "category": "BULLISH",
            "metadata": {"primary_timeframe": "1d"},
        },
    })

    resolution = _build_existing_opportunity_resolution(
        candidates=(candidate, second),
        exact_rows=(),
        continuity_rows=(logical,),
    )
    assert resolution.unsafe_logical_claims == {
        "older-opportunity": ("candidate-a", "candidate-b")
    }


def test_ingestion_preserves_terminal_exact_row_without_repository_write(
    monkeypatch,
):
    candidate = _namespace({
        "id": "current-candidate",
        "symbol": "EXPE",
        "score": 75.0,
        "snapshot_timestamp": "2026-08-16T21:01:20+00:00",
        "payload_json": {
            "direction": "BULLISH",
            "primary_timeframe": "1d",
            "scores": {"primary_category": "BULLISH"},
        },
    })
    terminal = _namespace({
        "opportunity_id": "current-terminal-opportunity",
        "stock_candidate_id": "current-candidate",
        "symbol": "EXPE",
        "state": "REJECTED",
    })
    publication = _namespace({
        "publication_name": "current_stock_intelligence",
        "scanner_run_id": "current-run",
    })
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.all.return_value = [candidate]
    session = MagicMock()
    session.query.return_value = query
    eligibility = MagicMock()
    eligibility.evaluate.return_value = EligibilityDecision(True)
    service = InstitutionalOpportunityIngestionService(
        session,
        eligibility=eligibility,
    )
    service.latest_publication = MagicMock(return_value=publication)
    service.repository = MagicMock()
    resolution = ExistingOpportunityResolution(
        exact_by_candidate={"current-candidate": terminal},
        logical_by_continuity={},
        terminal_exact_candidate_ids=("current-candidate",),
        prevented_collision_candidate_ids=("current-candidate",),
        prevented_collision_symbols=("EXPE",),
    )
    monkeypatch.setattr(
        ingestion,
        "_load_existing_opportunity_resolution",
        lambda *args, **kwargs: resolution,
    )

    result = service.ingest()

    assert result.existing == 1
    assert result.terminal_exact_preserved == 1
    assert result.lineage_collisions_prevented == 1
    assert result.refreshed == 0
    assert result.discovered == 0
    service.repository.save_opportunity.assert_not_called()
    service.repository.transition.assert_not_called()


def test_recovery_preflight_and_execute_enforce_lineage_resolution():
    recovery = (
        ROOT / "scripts/run_m68_2_1_10_resume_ingestion_authority.py"
    ).read_text()
    ingestion = (
        ROOT
        / "src/trading_ai/institutional_options/opportunity_ingestion.py"
    ).read_text()

    assert "inspect_opportunity_lineage_resolution" in recovery
    assert 'reason = "UNSAFE_OPPORTUNITY_LINEAGE"' in recovery
    assert "expected_collisions" in recovery
    assert "terminal_exact_preserved" in recovery
    assert "exact_row or logical_row" in ingestion
    assert "Preserve completed exact source decisions" in ingestion
    assert "unsafe_logical_claims" in ingestion
