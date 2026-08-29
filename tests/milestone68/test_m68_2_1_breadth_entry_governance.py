from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace

from trading_ai.inflection_intelligence.engine import (
    Bar,
    InstitutionalInflectionEngine,
)
from trading_ai.inflection_intelligence.service import (
    _as_date,
    _as_datetime,
    _canonical_hash,
    _json_safe,
    InstitutionalInflectionService,
)
from trading_ai.trade_plan_certification.engine import (
    certify_institutional_underlying_plan,
    plan_fingerprint,
)
from trading_ai.institutional_options.domain import (
    InstitutionalOpportunity,
    OpportunityLineage,
    OpportunityState,
    ThesisDirection,
)
from trading_ai.institutional_options.management import (
    ContractLineageRegenerationRequired,
)
from trading_ai.institutional_options.opportunity_ingestion import (
    _separate_source_and_contract_option_lineage,
)
from trading_ai.institutional_options.repository import (
    InstitutionalOpportunityRepository,
)


ROOT = Path(__file__).resolve().parents[2]


def test_source_lineage_date_and_timestamp_parsers_are_independent() -> None:
    assert _as_date("2026-08-14") == date(2026, 8, 14)
    assert _as_date("2026-08-14T20:23:47.319880+00:00") == date(2026, 8, 14)
    assert _as_date(datetime(2026, 8, 14, 20, 23, tzinfo=timezone.utc)) == date(
        2026, 8, 14
    )
    assert _as_date(None) is None
    assert _as_date("not-a-date") is None

    parsed = _as_datetime("2026-08-15T20:23:47.319880+00:00")
    assert parsed == datetime(2026, 8, 15, 20, 23, 47, 319880, tzinfo=timezone.utc)
    assert _as_datetime(None) is None
    assert _as_datetime("not-a-timestamp") is None


def test_governed_payload_temporal_lineage_is_json_safe_and_hash_stable() -> None:
    timestamp = datetime(2026, 8, 15, 20, 23, 47, 319880, tzinfo=timezone.utc)
    payload = {
        "lineage": {
            "source_as_of_date": date(2026, 8, 14),
            "breadth": {
                "snapshot_timestamp": timestamp,
                "as_of_date": date(2026, 8, 14),
            },
        }
    }
    normalized = _json_safe(payload)
    assert normalized["lineage"]["source_as_of_date"] == "2026-08-14"
    assert normalized["lineage"]["breadth"]["snapshot_timestamp"] == (
        "2026-08-15T20:23:47.319880+00:00"
    )
    json.dumps(normalized, allow_nan=False)
    assert _canonical_hash(payload) == _canonical_hash(normalized)

    try:
        _json_safe({"unsupported": object()})
    except TypeError:
        pass
    else:
        raise AssertionError("Unsupported payload objects must fail closed")


class _FakeScalarResult:
    def __init__(self, *, rows=None, first=None):
        self._rows = list(rows or [])
        self._first = first

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._first


class _FakeSession:
    def __init__(self, results):
        self._results = iter(results)

    def execute(self, _statement):
        return next(self._results)


def test_all_breadth_resolution_paths_emit_json_timestamps() -> None:
    service = InstitutionalInflectionService.__new__(
        InstitutionalInflectionService
    )
    source_date = date(2026, 8, 14)
    timestamp = datetime(2026, 8, 15, 20, 23, tzinfo=timezone.utc)

    sector = SimpleNamespace(
        breadth_score=88.5,
        constituent_count=25,
        confidence=95.0,
        sector="Energy",
        sector_etf="XLE",
        snapshot_timestamp=timestamp,
        as_of_date=source_date,
        provenance="POLYGON_PERSISTED",
    )
    sector_payload = service._breadth_payload(
        _FakeSession([_FakeScalarResult(rows=[sector])]),
        symbol="XLE",
        source_as_of_date=source_date,
        publication_timestamp=timestamp,
    )

    market = SimpleNamespace(
        breadth_score=63.5,
        evaluated_symbols=614,
        universe_name="CANONICAL",
        breadth_regime="HEALTHY_BROAD",
        snapshot_timestamp=timestamp,
        as_of_date=source_date,
    )
    market_payload = service._breadth_payload(
        _FakeSession([
            _FakeScalarResult(rows=[]),
            _FakeScalarResult(first=None),
            _FakeScalarResult(first=market),
        ]),
        symbol="TEST",
        source_as_of_date=source_date,
        publication_timestamp=timestamp,
    )

    overview = SimpleNamespace(
        breadth_score=59.0,
        confidence_score=87.0,
        breadth_regime="MIXED",
        snapshot_timestamp=timestamp,
        as_of_date=source_date,
    )
    overview_payload = service._breadth_payload(
        _FakeSession([
            _FakeScalarResult(rows=[]),
            _FakeScalarResult(first=None),
            _FakeScalarResult(first=None),
            _FakeScalarResult(first=overview),
        ]),
        symbol="TEST",
        source_as_of_date=source_date,
        publication_timestamp=timestamp,
    )

    for payload in (sector_payload, market_payload, overview_payload):
        assert payload["snapshot_timestamp"] == "2026-08-15T20:23:00+00:00"
        json.dumps(payload, allow_nan=False)


def bars() -> list[Bar]:
    return [
        Bar(
            close=100.0 + index * 0.6,
            high=100.4 + index * 0.6,
            low=99.6 + index * 0.6,
            volume=1_000_000 + index * 2_500,
            as_of=f"2026-07-{index + 1:02d}",
        )
        for index in range(40)
    ]


def option_inputs() -> tuple[dict, dict]:
    return (
        {"implied_volatility": 0.29, "spread_pct": 2.5},
        {
            "bull_probability": 0.68,
            "bear_probability": 0.32,
            "confidence_score": 92.0,
        },
    )


def stock_cert(reference_price: float) -> dict:
    reference = {
        "price": reference_price,
        "timestamp": "2026-08-15T20:23:47+00:00",
        "source": "LATEST_UNDERLYING_INGESTION",
        "provider": "POLYGON",
    }
    fingerprint = plan_fingerprint(
        direction="BULLISH",
        reference_market=reference,
        entry_zone_low=55.7467,
        entry_zone_high=56.1181,
        structural_stop=54.6837,
        targets=[61.9733, 64.0],
    )
    return {
        "certification_id": "TPC-XLE-TEST",
        "status": "PASS",
        "certification_scope": "STOCK_TRADE_PLAN",
        "reference_market": reference,
        "plan_fingerprint": fingerprint,
        "source_plan_fingerprint": fingerprint,
    }


def legs() -> list[dict]:
    return [
        {
            "side": "BUY",
            "option_symbol": "O:XLE260918C00056000",
            "expiry": "2026-09-18",
            "strike": 56,
        },
        {
            "side": "SELL",
            "option_symbol": "O:XLE260918C00062000",
            "expiry": "2026-09-18",
            "strike": 62,
        },
    ]


def management() -> dict:
    return {
        "underlying_entry_zone_low": 55.7467,
        "underlying_entry_zone_high": 56.1181,
        "underlying_stop": 54.6837,
        "underlying_targets": [61.9733, 64.0],
        "trailing_policy": "UNDERLYING_HIGHER_LOW",
        "volatility_exit_rule": "IV_COLLAPSE_AND_THESIS_DETERIORATION",
    }


def entry_policy() -> dict:
    return {
        "entry_type": "DEMAND_BOUNCE",
        "preferred_entry": 55.9324,
        "zone_low": 55.7467,
        "zone_high": 56.1181,
        "confirmation_trigger": 62.1181,
        "chase_limit": 56.6038,
    }


def certify(reference_price: float) -> dict:
    return certify_institutional_underlying_plan(
        stock_certification=stock_cert(reference_price),
        direction="BULLISH",
        entry_zone_low=55.7467,
        entry_zone_high=56.1181,
        structural_stop=54.6837,
        targets=[61.9733, 64.0],
        strategy="BULL_CALL_SPREAD",
        legs=legs(),
        contract_executable=True,
        dynamic_management=management(),
        entry_policy=entry_policy(),
        geometry_context={"atr": 1.48},
    )


def test_missing_breadth_abstains_without_weight_renormalization() -> None:
    candidate, dealer = option_inputs()
    result = InstitutionalInflectionEngine().evaluate(
        "TEST",
        bars(),
        candidate_payload=candidate,
        dealer_payload=dealer,
        breadth_score=None,
        build_mode="OPTIONS_ENRICHMENT",
    )
    assert result["disposition"] == "ABSTAIN"
    assert "breadth" in result["missing_inputs"]
    assert result["weight_contract"]["policy"] == "FIXED_NO_RENORMALIZATION"
    assert result["weight_contract"]["configured_weight_total"] == 1.0
    assert result["weight_contract"]["available_weight_total"] == 0.89
    assert result["component_decomposition"]["breadth"]["weighted_contribution"] == 0.0


def test_exact_breadth_materially_contributes_at_fixed_weight() -> None:
    candidate, dealer = option_inputs()
    result = InstitutionalInflectionEngine().evaluate(
        "TEST",
        bars(),
        candidate_payload=candidate,
        dealer_payload=dealer,
        breadth_score=88.57,
        build_mode="OPTIONS_ENRICHMENT",
    )
    breadth = result["component_decomposition"]["breadth"]
    assert breadth["available"] is True
    assert breadth["raw_score"] == 77.14
    assert breadth["configured_weight"] == 0.11
    assert breadth["weighted_contribution"] == 8.4854


def test_xle_like_extended_plan_requires_regeneration() -> None:
    certification = certify(61.91)
    assert certification["status"] == "PASS"
    assert certification["trade_builder_ready"] is False
    assert certification["execution_disposition"] == "REGENERATE_REQUIRED"
    assert "TARGET_1_REMAINING_ROOM_INSUFFICIENT" in (
        certification["entry_execution"]["reason_codes"]
    )


def test_same_plan_is_ready_only_inside_governed_entry_range() -> None:
    certification = certify(55.90)
    assert certification["status"] == "PASS"
    assert certification["trade_builder_ready"] is True
    assert certification["execution_disposition"] == "READY_NOW"


def test_source_contracts_enforce_point_in_time_and_handoff_governance() -> None:
    service = (
        ROOT / "src/trading_ai/inflection_intelligence/service.py"
    ).read_text()
    management_source = (
        ROOT / "src/trading_ai/institutional_options/management.py"
    ).read_text()
    handoff = (
        ROOT / "src/trading_ai/institutional_options/handoff.py"
    ).read_text()
    assert "<= publication_timestamp" in service
    assert "DIRECT_SECTOR_ETF" in service
    assert "CANONICAL_MARKET_FALLBACK" in service
    assert 'row.snapshot_timestamp.isoformat()' in service
    assert 'market.snapshot_timestamp.isoformat()' in service
    assert 'overview.snapshot_timestamp.isoformat()' in service
    assert "result = _json_safe(result)" in service
    assert 'original_payload.get("context_score")' not in service
    assert "m68.2.1-conditional-entry-governance" in management_source
    assert 'execution_disposition") != "READY_NOW"' in handoff


def _opportunity_with_source_option_run() -> InstitutionalOpportunity:
    return InstitutionalOpportunity(
        opportunity_id="m62-opp-lineage-test",
        symbol="XLE",
        asset_class="EQUITY",
        state=OpportunityState.READY_FOR_EXECUTION,
        direction=ThesisDirection.BULLISH,
        category="BULLISH",
        overall_score=80.0,
        confidence=90.0,
        conviction="HIGH",
        lineage=OpportunityLineage(
            stock_publication_name="current_stock_intelligence",
            stock_scanner_run_id="stock-scan-current",
            stock_candidate_id="stock-candidate-current",
            stock_state_hash="state-hash",
            option_snapshot_id="options-20260815T193005482216Z",
            option_snapshot_timestamp="2026-08-15T19:30:05+00:00",
        ),
        thesis_id="m62-thesis-lineage-test",
    )


def test_opportunity_refresh_preserves_executable_contract_lineage() -> None:
    existing = SimpleNamespace(
        state="READY_FOR_EXECUTION",
        option_snapshot_id="polygon-options-2026-08-15",
        payload_json={
            "lineage": {
                "option_snapshot_id": "polygon-options-2026-08-15",
                "option_snapshot_timestamp": "2026-08-15",
            }
        },
    )
    refreshed = _separate_source_and_contract_option_lineage(
        _opportunity_with_source_option_run(),
        existing,
    )
    assert refreshed.lineage.option_snapshot_id == (
        "polygon-options-2026-08-15"
    )
    assert refreshed.metadata[
        "m68_2_1_3_source_option_snapshot_id"
    ] == "options-20260815T193005482216Z"
    assert refreshed.metadata[
        "m68_2_1_3_contract_option_snapshot_id"
    ] == "polygon-options-2026-08-15"
    assert refreshed.metadata["source_option_snapshot_id"] == (
        "options-20260815T193005482216Z"
    )
    assert refreshed.metadata["contract_option_snapshot_id"] == (
        "polygon-options-2026-08-15"
    )


def test_pre_contract_opportunity_does_not_claim_raw_run_as_contract() -> None:
    refreshed = _separate_source_and_contract_option_lineage(
        _opportunity_with_source_option_run(),
        None,
    )
    assert refreshed.lineage.option_snapshot_id is None
    assert refreshed.metadata[
        "m68_2_1_3_source_option_snapshot_id"
    ] == "options-20260815T193005482216Z"
    assert refreshed.metadata["source_option_snapshot_id"] == (
        "options-20260815T193005482216Z"
    )
    assert refreshed.metadata["contract_option_snapshot_id"] is None


def test_missing_exact_contract_has_typed_regeneration_disposition() -> None:
    error = ContractLineageRegenerationRequired(
        expected_option_snapshot_id="options-current-run",
        available_option_snapshot_ids=("polygon-options-2026-08-05",),
    )
    assert error.expected_option_snapshot_id == "options-current-run"
    assert error.available_option_snapshot_ids == (
        "polygon-options-2026-08-05",
    )
    assert "expected=options-current-run" in str(error)


class _NoExecutionQuery:
    def filter_by(self, **_values):
        return self

    def one_or_none(self):
        return None


class _ContractLineageSession:
    def __init__(self, row):
        self.row = row
        self.added = []

    def flush(self):
        return None

    def get(self, _model, _identifier):
        return self.row

    def query(self, _model):
        return _NoExecutionQuery()

    def add(self, value):
        self.added.append(value)


def test_contract_regeneration_governs_unavailable_current_chain() -> None:
    row = SimpleNamespace(
        opportunity_id="m62-opp-lineage-test",
        state="READY_FOR_EXECUTION",
        option_snapshot_id="options-20260815T193005482216Z",
        version=7,
        updated_at="2026-08-15T19:30:05+00:00",
        payload_json={
            "state": "READY_FOR_EXECUTION",
            "lineage": {
                "option_snapshot_id": (
                    "options-20260815T193005482216Z"
                ),
            },
            "metadata": {
                "source_option_snapshot_id": (
                    "options-20260815T193005482216Z"
                ),
            },
        },
    )
    session = _ContractLineageSession(row)
    repository = InstitutionalOpportunityRepository(session)
    repository.reset_for_contract_regeneration(
        row.opportunity_id,
        expected_option_snapshot_id=row.option_snapshot_id,
        available_option_snapshot_ids=(
            "polygon-options-2026-08-05",
        ),
        reason="Exact package mismatch",
    )
    assert row.state == "STRATEGIES_GENERATED"
    assert row.option_snapshot_id is None
    assert row.payload_json["lineage"]["source_option_snapshot_id"] == (
        "options-20260815T193005482216Z"
    )
    assert row.payload_json["metadata"][
        "m68_2_1_3_contract_regeneration_required"
    ] is True

    repository.resolve_contract_regeneration_unavailable(
        row.opportunity_id,
        reason="No executable current Polygon package",
    )
    assert row.state == "STRATEGIES_GENERATED"
    assert row.payload_json["metadata"]["execution_disposition"] == (
        "NO_EXECUTABLE_CURRENT_CONTRACT"
    )
    assert row.payload_json["metadata"][
        "m68_2_1_3_contract_regeneration_required"
    ] is False
    assert len(session.added) == 2


def test_recovery_contract_regenerates_and_globally_selects_feasible_package_before_m64_handoff() -> None:
    repository = (
        ROOT / "src/trading_ai/institutional_options/repository.py"
    ).read_text()
    recovery = (
        ROOT / "scripts/run_m68_2_recover_current_authority.py"
    ).read_text()
    ingestion = (
        ROOT / "src/trading_ai/institutional_options/opportunity_ingestion.py"
    ).read_text()
    optimizer = (
        ROOT / "src/trading_ai/institutional_options/contract_optimization.py"
    ).read_text()
    assert "reset_for_contract_regeneration" in repository
    assert "TPC-LIN-021" in repository
    assert "resolve_contract_regeneration_unavailable" in repository
    assert "TPC-LIN-022" in repository
    assert "NO_EXECUTABLE_CURRENT_CONTRACT" in repository
    assert "InstitutionalContractOptimizationService" in recovery
    assert "post_regeneration_entry_governance" in recovery
    assert "falsely_ready_contract_lineage" in recovery
    assert "governed_unavailable" in recovery
    assert "unexpected_failures" in recovery
    assert "resumed_pending_contract_regeneration_ids" in recovery
    assert "m68_2_1_3_contract_regeneration_required" in recovery
    assert "StrategyComparisonModel" in optimizer
    assert "ranked_packages" in optimizer
    assert "feasible_packages" in optimizer
    assert "if not feasible_packages" in optimizer
    assert "EXHAUSTIVE_EXECUTABLE_PACKAGE_AUTHORITY" in optimizer
    assert "all_eligible_strategies_evaluated" in optimizer
    assert "higher_ranked_feasible_excluded" in optimizer
    assert "m68_2_1_13_global_feasible_package_proven" in optimizer
    # M68.2.1.13 deliberately superseded M68.2.1.4's selected-only
    # contract gate. The strategy-stage winner is provisional until every
    # eligible exact contract package has been evaluated. Restoring these
    # names would reintroduce the defect where an unbuildable provisional
    # winner strands a better globally feasible package.
    assert "selected_executable_count" not in optimizer
    assert "for authoritative selected strategy" not in optimizer
    assert "SOURCE_AND_CONTRACT_IDENTITIES_SEPARATED" in ingestion


def test_inflection_candidate_explorer_filters_and_expands_inline() -> None:
    ui = (
        ROOT / "ui/workstation/src/InflectionAnalyticsPage.tsx"
    ).read_text()
    assert "HEADER_FILTER_FIELDS" in ui
    assert "CandidateHeaderFilter" in ui
    assert "headerFilterStyle" in ui
    for field in (
        "symbol",
        "company_name",
        "direction",
        "transition_state",
        "disposition",
        "sector",
        "strategy",
        "market_regime",
        "opportunity_state",
        "coverage_status",
        "source_as_of_date",
    ):
        assert field in ui
    assert "directionalScoreBand" in ui
    assert "minimumStrength" in ui
    assert "minimumConfidence" in ui
    assert "minimumInputQuality" in ui
    assert "minimumOpportunityScore" in ui
    assert "expandedSnapshotId" in ui
    assert "aria-expanded" in ui
    assert "InlineCandidateDetail" in ui
    assert "DetailDrawer" not in ui
    assert "repeat(auto-fit, minmax(175px, 1fr))" not in ui
    assert "borderLeft: '2px solid var(--accent)'" in ui
    assert "repeat(3, minmax(250px, 1fr))" in ui
    assert "columns: evidence.length > 4 ? 2 : 1" in ui
