from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy import desc
from sqlalchemy.orm import Session

from trading_ai.stock_intelligence.models import (
    StockScannerCandidateModel,
    StockScannerPublicationModel,
)

from .domain import (
    InstitutionalOpportunity,
    OpportunityLineage,
    OpportunityState,
    OpportunityThesis,
    ThesisDirection,
)
from .policy import OpportunityGovernancePolicy
from .repository import InstitutionalOpportunityRepository
from .models import InstitutionalOpportunityModel


@dataclass(frozen=True)
class OpportunityEligibilityPolicy:
    minimum_score: float = 55.0
    minimum_confidence: float = 55.0
    minimum_freshness: float = 60.0
    maximum_age_hours: float = 72.0
    require_dynamic_plan: bool = True
    require_structural_stop: bool = True
    require_targets: bool = True
    require_state_hash: bool = True
    reject_neutral_direction: bool = True
    policy_version: str = "M62-PH2-1.0"


@dataclass(frozen=True)
class EligibilityDecision:
    eligible: bool
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    opportunity_quality: float = 0.0


@dataclass(frozen=True)
class OpportunityIngestionResult:
    publication_name: str
    stock_scanner_run_id: str | None
    requested: int
    discovered: int
    validated: int
    rejected: int
    existing: int = 0
    refreshed: int = 0
    existing_rejected: int = 0
    exact_current_lineage_rows: int = 0
    terminal_exact_preserved: int = 0
    lineage_collisions_prevented: int = 0
    unsafe_logical_contentions: int = 0
    opportunity_ids: tuple[str, ...] = ()
    rejection_counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ExistingOpportunityResolution:
    """Deterministic ownership indexes for one Stock Intelligence projection.

    Exact ``(stock_scanner_run_id, stock_candidate_id)`` ownership is the
    authoritative identity for a resumed projection, regardless of lifecycle
    state. Logical continuity is only a fallback for a candidate that has not
    yet been materialized for the current Stock run.
    """

    exact_by_candidate: dict[str, InstitutionalOpportunityModel] = field(
        repr=False
    )
    logical_by_continuity: dict[
        tuple[str, str, str, str], InstitutionalOpportunityModel
    ] = field(repr=False)
    terminal_exact_candidate_ids: tuple[str, ...] = ()
    prevented_collision_candidate_ids: tuple[str, ...] = ()
    prevented_collision_symbols: tuple[str, ...] = ()
    unsafe_logical_claims: dict[str, tuple[str, ...]] = field(
        default_factory=dict
    )
    exact_symbol_mismatches: tuple[str, ...] = ()
    pre_execution_row_count: int = 0


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _direction(value: str | None) -> ThesisDirection:
    normalized = str(value or "").upper()
    if "BULL" in normalized:
        return ThesisDirection.BULLISH
    if "BEAR" in normalized:
        return ThesisDirection.BEARISH
    return ThesisDirection.NEUTRAL



def _normalized_category(value: Any) -> str:
    return str(value or "").strip().upper().replace("-", "_").replace(" ", "_")


def _category_direction_conflict(category: Any, direction: ThesisDirection) -> bool:
    """Return True only for unambiguously contradictory setup labels.

    Reversal/reclaim labels are intentionally exempt because a failed breakdown can
    be bullish and a failed breakout can be bearish.
    """
    normalized = _normalized_category(category)
    if not normalized or direction == ThesisDirection.NEUTRAL:
        return False

    bullish_reversal_exemptions = (
        "FAILED_BREAKDOWN", "BREAKDOWN_REVERSAL", "BREAKDOWN_RECLAIM",
        "BEAR_TRAP", "RECLAIM",
    )
    bearish_reversal_exemptions = (
        "FAILED_BREAKOUT", "BREAKOUT_FAILURE", "BREAKOUT_REJECTION",
        "BULL_TRAP", "REJECTION",
    )

    if direction == ThesisDirection.BULLISH:
        if any(token in normalized for token in bullish_reversal_exemptions):
            return False
        return any(token in normalized for token in ("BREAKDOWN", "DISTRIBUTION", "BEARISH"))

    if any(token in normalized for token in bearish_reversal_exemptions):
        return False
    return any(token in normalized for token in ("BREAKOUT", "ACCUMULATION", "BULLISH"))




PRE_EXECUTION_CONTINUITY_STATES = {
    OpportunityState.DISCOVERED.value,
    OpportunityState.VALIDATED.value,
    OpportunityState.STRATEGIES_GENERATED.value,
    OpportunityState.CONTRACTS_OPTIMIZED.value,
    OpportunityState.READY_FOR_EXECUTION.value,
}

CONTRACT_LINEAGE_STATES = {
    OpportunityState.CONTRACTS_OPTIMIZED.value,
    OpportunityState.READY_FOR_EXECUTION.value,
}


def _separate_source_and_contract_option_lineage(
    opportunity: InstitutionalOpportunity,
    existing_row: InstitutionalOpportunityModel | None,
) -> InstitutionalOpportunity:
    """Keep market-input and executable-contract snapshot identities distinct.

    Stock Intelligence publishes the raw option ingestion run (``options-*``),
    while M62 contract optimization publishes the executable package identity
    (``polygon-options-YYYY-MM-DD``).  Refreshing an existing opportunity must
    never replace the latter with the former while preserving a downstream
    lifecycle state.
    """

    source_snapshot_id = opportunity.lineage.option_snapshot_id
    source_snapshot_timestamp = opportunity.lineage.option_snapshot_timestamp
    contract_snapshot_id: str | None = None
    contract_snapshot_timestamp: str | None = None

    if (
        existing_row is not None
        and str(existing_row.state) in CONTRACT_LINEAGE_STATES
        and existing_row.option_snapshot_id
    ):
        contract_snapshot_id = str(existing_row.option_snapshot_id)
        existing_payload = dict(existing_row.payload_json or {})
        existing_lineage = dict(existing_payload.get("lineage") or {})
        contract_snapshot_timestamp = (
            str(existing_lineage.get("option_snapshot_timestamp") or "")
            or None
        )

    metadata = {
        **dict(opportunity.metadata or {}),
        "m68_2_1_3_option_lineage_policy": (
            "SOURCE_AND_CONTRACT_IDENTITIES_SEPARATED"
        ),
        "m68_2_1_3_source_option_snapshot_id": source_snapshot_id,
        "m68_2_1_3_source_option_snapshot_timestamp": (
            source_snapshot_timestamp
        ),
        "m68_2_1_3_contract_option_snapshot_id": contract_snapshot_id,
        "source_option_snapshot_id": source_snapshot_id,
        "source_option_snapshot_timestamp": source_snapshot_timestamp,
        "contract_option_snapshot_id": contract_snapshot_id,
    }
    return replace(
        opportunity,
        lineage=replace(
            opportunity.lineage,
            option_snapshot_id=contract_snapshot_id,
            option_snapshot_timestamp=contract_snapshot_timestamp,
        ),
        metadata=metadata,
    )


def _stable_json_fingerprint(value: Any) -> str:
    payload = json.dumps(value or {}, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _candidate_continuity_key(payload: dict[str, Any], *, symbol: str) -> tuple[str, str, str, str]:
    scores = payload.get("scores") or {}
    return (
        str(symbol or "").strip().upper(),
        _direction(payload.get("direction")).value,
        _normalized_category(scores.get("primary_category") or payload.get("category")),
        str(payload.get("primary_timeframe") or "1d").strip().lower(),
    )


def _row_continuity_key(row: InstitutionalOpportunityModel) -> tuple[str, str, str, str]:
    payload = dict(row.payload_json or {})
    thesis = payload.get("thesis") or {}
    metadata = payload.get("metadata") or {}
    setup = payload.get("category") or thesis.get("setup_category") or row.category
    timeframe = (
        thesis.get("primary_timeframe")
        or metadata.get("primary_timeframe")
        or payload.get("primary_timeframe")
        or "1d"
    )
    return (
        str(row.symbol or "").strip().upper(),
        str(row.direction or payload.get("direction") or "NEUTRAL").strip().upper(),
        _normalized_category(setup),
        str(timeframe).strip().lower(),
    )


def _build_existing_opportunity_resolution(
    *,
    candidates: Iterable[StockScannerCandidateModel],
    exact_rows: Iterable[InstitutionalOpportunityModel],
    continuity_rows: Iterable[InstitutionalOpportunityModel],
) -> ExistingOpportunityResolution:
    """Resolve current candidate ownership without mutating lifecycle history.

    ``exact_rows`` intentionally includes terminal rows. A terminal exact row
    is a completed decision for that source candidate, not an invitation to
    resurrect an older logical opportunity. ``continuity_rows`` is already
    ordered newest first by the database loader, so ``setdefault`` provides a
    stable fallback only when no exact materialized identity exists.
    """

    candidate_values = tuple(candidates)
    exact_by_candidate: dict[str, InstitutionalOpportunityModel] = {}
    exact_symbol_mismatches: list[str] = []
    for row in exact_rows:
        candidate_id = str(row.stock_candidate_id or "")
        if candidate_id:
            exact_by_candidate.setdefault(candidate_id, row)

    logical_by_continuity: dict[
        tuple[str, str, str, str], InstitutionalOpportunityModel
    ] = {}
    continuity_values = tuple(continuity_rows)
    for row in continuity_values:
        logical_by_continuity.setdefault(_row_continuity_key(row), row)

    terminal_exact_candidate_ids: list[str] = []
    prevented_collision_candidate_ids: list[str] = []
    prevented_collision_symbols: list[str] = []
    logical_claims: dict[str, list[str]] = {}
    for candidate in candidate_values:
        candidate_id = str(candidate.id)
        symbol = str(candidate.symbol or "").strip().upper()
        payload = dict(candidate.payload_json or {})
        exact_row = exact_by_candidate.get(candidate_id)
        logical_row = logical_by_continuity.get(
            _candidate_continuity_key(payload, symbol=symbol)
        )
        if exact_row is not None:
            if str(exact_row.symbol or "").strip().upper() != symbol:
                exact_symbol_mismatches.append(candidate_id)
            if str(exact_row.state) not in PRE_EXECUTION_CONTINUITY_STATES:
                terminal_exact_candidate_ids.append(candidate_id)
            if (
                logical_row is not None
                and str(logical_row.opportunity_id)
                != str(exact_row.opportunity_id)
            ):
                prevented_collision_candidate_ids.append(candidate_id)
                prevented_collision_symbols.append(symbol)
            continue
        if logical_row is not None:
            logical_claims.setdefault(
                str(logical_row.opportunity_id), []
            ).append(candidate_id)

    unsafe_logical_claims = {
        opportunity_id: tuple(sorted(candidate_ids))
        for opportunity_id, candidate_ids in logical_claims.items()
        if len(candidate_ids) > 1
    }
    return ExistingOpportunityResolution(
        exact_by_candidate=exact_by_candidate,
        logical_by_continuity=logical_by_continuity,
        terminal_exact_candidate_ids=tuple(
            sorted(set(terminal_exact_candidate_ids))
        ),
        prevented_collision_candidate_ids=tuple(
            sorted(set(prevented_collision_candidate_ids))
        ),
        prevented_collision_symbols=tuple(
            sorted(set(prevented_collision_symbols))
        ),
        unsafe_logical_claims=unsafe_logical_claims,
        exact_symbol_mismatches=tuple(
            sorted(set(exact_symbol_mismatches))
        ),
        pre_execution_row_count=len(continuity_values),
    )


def _load_existing_opportunity_resolution(
    session: Session,
    *,
    stock_scanner_run_id: str,
    candidates: Iterable[StockScannerCandidateModel],
) -> ExistingOpportunityResolution:
    candidate_values = tuple(candidates)
    candidate_ids = tuple(str(item.id) for item in candidate_values)
    candidate_symbols = tuple(sorted({
        str(item.symbol or "").strip().upper()
        for item in candidate_values
        if str(item.symbol or "").strip()
    }))
    exact_rows: list[InstitutionalOpportunityModel] = []
    if candidate_ids:
        exact_rows = (
            session.query(InstitutionalOpportunityModel)
            .filter(
                InstitutionalOpportunityModel.stock_scanner_run_id
                == stock_scanner_run_id,
                InstitutionalOpportunityModel.stock_candidate_id.in_(
                    candidate_ids
                ),
            )
            .all()
        )
    continuity_rows: list[InstitutionalOpportunityModel] = []
    if candidate_symbols:
        continuity_rows = (
            session.query(InstitutionalOpportunityModel)
            .filter(
                InstitutionalOpportunityModel.symbol.in_(candidate_symbols),
                InstitutionalOpportunityModel.state.in_(
                    tuple(PRE_EXECUTION_CONTINUITY_STATES)
                ),
            )
            .order_by(
                desc(InstitutionalOpportunityModel.updated_at),
                desc(InstitutionalOpportunityModel.created_at),
            )
            .all()
        )
    return _build_existing_opportunity_resolution(
        candidates=candidate_values,
        exact_rows=exact_rows,
        continuity_rows=continuity_rows,
    )


def inspect_opportunity_lineage_resolution(
    session: Session,
    stock_scanner_run_id: str,
) -> dict[str, Any]:
    """Read-only recovery gate for exact and logical opportunity ownership."""

    candidates = (
        session.query(StockScannerCandidateModel)
        .filter(
            StockScannerCandidateModel.scanner_run_id
            == stock_scanner_run_id
        )
        .order_by(
            desc(StockScannerCandidateModel.score),
            StockScannerCandidateModel.symbol,
        )
        .all()
    )
    resolution = _load_existing_opportunity_resolution(
        session,
        stock_scanner_run_id=stock_scanner_run_id,
        candidates=candidates,
    )
    safe = not (
        resolution.unsafe_logical_claims
        or resolution.exact_symbol_mismatches
    )
    return {
        "version": "M68.2.1.12-TERMINAL-LINEAGE-IDEMPOTENCE-1.0",
        "status": "SAFE" if safe else "UNSAFE",
        "stock_scanner_run_id": stock_scanner_run_id,
        "candidate_count": len(candidates),
        "exact_current_lineage_rows": len(
            resolution.exact_by_candidate
        ),
        "terminal_exact_rows_to_preserve": len(
            resolution.terminal_exact_candidate_ids
        ),
        "lineage_collisions_prevented": len(
            resolution.prevented_collision_candidate_ids
        ),
        "lineage_collision_symbols": list(
            resolution.prevented_collision_symbols
        ),
        "pre_execution_row_count": resolution.pre_execution_row_count,
        "unsafe_logical_contentions": len(
            resolution.unsafe_logical_claims
        ),
        "unsafe_logical_claims": {
            key: list(value)
            for key, value in resolution.unsafe_logical_claims.items()
        },
        "exact_symbol_mismatches": list(
            resolution.exact_symbol_mismatches
        ),
    }


def _iso_age_hours(value: str | None, now: datetime) -> float:
    if not value:
        return float("inf")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0.0, (now - parsed.astimezone(timezone.utc)).total_seconds() / 3600.0)
    except ValueError:
        return float("inf")


class StockOpportunityEligibilityService:
    def __init__(self, policy: OpportunityEligibilityPolicy | None = None) -> None:
        self.policy = policy or OpportunityEligibilityPolicy()

    def evaluate(self, payload: dict[str, Any], *, snapshot_timestamp: str | None, now: datetime | None = None) -> EligibilityDecision:
        now = now or datetime.now(timezone.utc)
        scores = payload.get("scores") or {}
        trade_plan = payload.get("trade_plan") or {}
        certification = trade_plan.get("certification") or {}
        entry = trade_plan.get("entry") or {}
        stop = trade_plan.get("stop") or {}
        targets_payload = trade_plan.get("targets") or {}
        target_items = targets_payload.get("targets") or []
        target_prices = [item.get("price") if isinstance(item, dict) else item for item in target_items]
        target_prices = [item for item in target_prices if _number(item) > 0]

        reasons: list[str] = []
        warnings: list[str] = []
        score = _number(scores.get("overall"), 0)
        confidence = _number(scores.get("confidence"), 0)
        freshness = _number(scores.get("freshness"), 0)
        direction = _direction(payload.get("direction"))
        category = (scores.get("primary_category") or payload.get("category") or "")
        age_hours = _iso_age_hours(snapshot_timestamp, now)

        if score < self.policy.minimum_score:
            reasons.append("UNDERLYING_SCORE_BELOW_MINIMUM")
        if confidence < self.policy.minimum_confidence:
            reasons.append("UNDERLYING_CONFIDENCE_BELOW_MINIMUM")
        if freshness < self.policy.minimum_freshness:
            reasons.append("STOCK_INTELLIGENCE_STALE")
        if age_hours > self.policy.maximum_age_hours:
            reasons.append("PUBLICATION_TOO_OLD")
        if self.policy.reject_neutral_direction and direction == ThesisDirection.NEUTRAL:
            reasons.append("NEUTRAL_DIRECTION")
        if _category_direction_conflict(category, direction):
            reasons.append("CATEGORY_DIRECTION_CONFLICT")
        if self.policy.require_state_hash and not payload.get("state_hash"):
            reasons.append("STATE_HASH_MISSING")
        if self.policy.require_dynamic_plan and not trade_plan:
            reasons.append("DYNAMIC_PLAN_MISSING")
        if not certification:
            reasons.append("TRADE_PLAN_CERTIFICATION_MISSING")
        elif str(certification.get("status") or "").upper() != "PASS":
            reasons.append("TRADE_PLAN_CERTIFICATION_FAILED")
        if self.policy.require_structural_stop and _number(stop.get("recommended_stop")) <= 0:
            reasons.append("STRUCTURAL_STOP_MISSING")
        if self.policy.require_targets and not target_prices:
            reasons.append("DYNAMIC_TARGETS_MISSING")
        if _number(entry.get("zone_low")) <= 0 or _number(entry.get("zone_high")) <= 0:
            reasons.append("ENTRY_ZONE_MISSING")
        if _number(entry.get("zone_low")) > _number(entry.get("zone_high")):
            reasons.append("ENTRY_ZONE_INVALID")

        context = payload.get("context") or {}
        if str(context.get("market_regime", "")).upper() in {"", "UNKNOWN", "UNAVAILABLE"}:
            warnings.append("MARKET_CONTEXT_UNAVAILABLE")
        if str(context.get("dealer_positioning", "")).upper() in {"", "UNKNOWN", "UNAVAILABLE"}:
            warnings.append("DEALER_CONTEXT_UNAVAILABLE")

        management_quality = _number(trade_plan.get("management_quality"), 0)
        structural_rr = _number(trade_plan.get("structural_reward_risk"), 0)
        alignment = _number(payload.get("alignment_score"), 0)
        volume = payload.get("institutional_volume") or {}
        volume_score = _number(volume.get("institutional_participation_score"), 50)
        idi = payload.get("decision_intelligence") or {}
        idi_quality = _number(idi.get("overall_trade_quality"), score)
        idi_readiness = _number(idi.get("decision_readiness"), confidence)
        quality = min(100.0, max(0.0,
            idi_quality * 0.34 + idi_readiness * 0.18 + score * 0.17 + confidence * 0.12 + management_quality * 0.08 +
            min(100.0, structural_rr * 25.0) * 0.04 + alignment * 0.03 + volume_score * 0.04
        ))
        if idi and idi_readiness < 55:
            warnings.append("DECISION_READINESS_BELOW_PREFERRED_THRESHOLD")
        return EligibilityDecision(not reasons, tuple(reasons), tuple(warnings), round(quality, 4))


class StockOpportunityThesisAdapter:
    def adapt(
        self,
        *,
        candidate: StockScannerCandidateModel,
        publication: StockScannerPublicationModel,
        opportunity_id: str,
        thesis_id: str,
    ) -> tuple[InstitutionalOpportunity, OpportunityThesis]:
        payload = dict(candidate.payload_json or {})
        scores = payload.get("scores") or {}
        trade_plan = payload.get("trade_plan") or {}
        certification = trade_plan.get("certification") or {}
        reference_market = trade_plan.get("reference_market") or certification.get("reference_market") or {}
        entry = trade_plan.get("entry") or {}
        stop = trade_plan.get("stop") or {}
        targets_payload = trade_plan.get("targets") or {}
        target_items = targets_payload.get("targets") or []
        targets = tuple(
            _number(item.get("price") if isinstance(item, dict) else item)
            for item in target_items
            if _number(item.get("price") if isinstance(item, dict) else item) > 0
        )
        context = payload.get("context") or {}
        context_evidence = dict(context.get("evidence") or {})
        forecast_evidence = dict(context_evidence.get("forecast_details") or {})
        participation = payload.get("participation") or {}
        breakout = payload.get("breakout") or {}
        volume = payload.get("institutional_volume") or {}
        idi = payload.get("decision_intelligence") or {}
        barrier = idi.get("barrier_probability") or {}
        outcome_probability = idi.get("outcome_probability") or {}
        states = payload.get("timeframe_states") or {}
        primary_timeframe = payload.get("primary_timeframe") or "1d"
        primary_state = states.get(primary_timeframe) or {}
        direction = _direction(payload.get("direction"))

        evidence: list[str] = []
        if _number(payload.get("alignment_score")) >= 70:
            evidence.append("Multi-timeframe alignment is strong")
        if participation.get("state") and participation.get("state") != "NEUTRAL":
            evidence.append(f"Participation state: {participation.get('state')}")
        if breakout.get("state") and breakout.get("state") != "NONE":
            evidence.append(f"Breakout state: {breakout.get('state')}")
        if volume.get("signal") and volume.get("signal") not in {"NEUTRAL", "UNAVAILABLE"}:
            evidence.append(f"Institutional volume: {volume.get('signal')} · RVOL {_number(volume.get('relative_volume_1d'),0):.2f}x")
        if context.get("relative_strength_grade"):
            evidence.append(f"Relative strength: {context.get('relative_strength_grade')}")
        if idi:
            evidence.append(f"Institutional trade quality: {_number(idi.get('overall_trade_quality'),0):.1f} · grade {idi.get('institutional_grade') or '—'}")
            evidence.append(f"Decision readiness: {_number(idi.get('decision_readiness'),0):.1f} · {idi.get('decision') or 'WATCH'}")
            if outcome_probability.get("status") == "SHADOW_READY":
                evidence.append(
                    "M77 shadow probability: "
                    f"P(Target 1 before stop) {_number(outcome_probability.get('target_1_before_stop'),0):.1f}% · "
                    f"{outcome_probability.get('recommended_disposition') or 'ABSTAIN'} "
                    "(no trade-authority effect)"
                )
            elif _number(barrier.get("target_1_before_stop"),0) > 0:
                evidence.append(f"Barrier prior: P(Target 1 before stop) {_number(barrier.get('target_1_before_stop'),0):.1f}% (uncalibrated)")
        evidence.extend(str(item) for item in (entry.get("rationale") or [])[:3])

        risks = list(payload.get("warnings") or [])
        risks.extend(str(item) for item in (trade_plan.get("exit") or {}).get("warnings", []))

        publication_payload = dict(publication.payload_json or {})
        publication_lineage = publication_payload.get("lineage") or {}
        if not isinstance(publication_lineage, dict):
            publication_lineage = {}
        lineage = OpportunityLineage(
            stock_publication_name=publication.publication_name,
            stock_scanner_run_id=publication.scanner_run_id,
            stock_candidate_id=candidate.id,
            stock_state_hash=str(payload.get("state_hash") or ""),
            market_publication_name=(
                publication_payload.get("market_publication_name")
                or publication_lineage.get("market_publication_name")
                or "current_market_state"
            ),
            market_run_id=(
                publication_payload.get("market_run_id")
                or publication_lineage.get("market_publication_run_id")
                or publication_lineage.get("market_run_id")
            ),
            option_snapshot_id=(
                publication_payload.get("option_snapshot_id")
                or publication_lineage.get("option_snapshot_id")
            ),
            option_snapshot_timestamp=(
                publication_payload.get("option_snapshot_timestamp")
                or publication_lineage.get("option_snapshot_timestamp")
            ),
            source_provider="POLYGON_PERSISTED",
        )
        thesis = OpportunityThesis(
            thesis_id=thesis_id,
            opportunity_id=opportunity_id,
            direction=direction,
            setup_category=str(scores.get("primary_category") or candidate.category),
            primary_timeframe=str(primary_timeframe),
            market_regime=context.get("market_regime"),
            sector_context=context.get("sector_alignment") or context.get("sector_context"),
            trend_state=str(primary_state.get("direction") or payload.get("direction") or "NEUTRAL"),
            structure_state=str(primary_state.get("structure") or payload.get("structure") or "SIDEWAYS"),
            participation_state=participation.get("state"),
            dealer_context=context.get("dealer_positioning"),
            forecast_context=context.get("forecast_direction"),
            entry_zone_low=_number(entry.get("zone_low")),
            entry_zone_high=_number(entry.get("zone_high")),
            invalidation_level=_number(stop.get("recommended_stop")),
            targets=targets,
            expected_holding_days_min=max(1, int(_number(trade_plan.get("expected_hold_days"), 5) * 0.6)),
            expected_holding_days_max=max(2, int(_number(trade_plan.get("expected_hold_days"), 10) * 1.5)),
            evidence=tuple(dict.fromkeys(evidence)),
            risks=tuple(dict.fromkeys(risks)),
        )
        opportunity = InstitutionalOpportunity(
            opportunity_id=opportunity_id,
            symbol=candidate.symbol,
            asset_class=str((payload.get("metadata") or {}).get("asset_class") or "EQUITY"),
            state=OpportunityState.DISCOVERED,
            direction=direction,
            category=thesis.setup_category,
            overall_score=_number(scores.get("overall"), candidate.score),
            confidence=_number(scores.get("confidence"), 0),
            conviction=self._conviction(_number(scores.get("overall"), candidate.score), _number(scores.get("confidence"), 0)),
            lineage=lineage,
            thesis_id=thesis_id,
            metadata={
                "opportunity_quality": None,
                "freshness": _number(scores.get("freshness"), 0),
                "management_quality": _number(trade_plan.get("management_quality"), 0),
                "structural_reward_risk": _number(trade_plan.get("structural_reward_risk"), 0),
                "eligibility_policy_version": "M62-PH2-1.0",
                "trade_plan_certification": certification,
                "reference_market": reference_market,
                "m75_2_certification_required": True,
                "institutional_volume": volume,
                "forecast_evidence": forecast_evidence,
                "institutional_decision_intelligence": idi,
                "m76_2_trade_quality": _number(idi.get("overall_trade_quality"), 0),
                "m76_2_decision_readiness": _number(idi.get("decision_readiness"), 0),
                "m76_2_capital_priority": _number(idi.get("capital_priority"), 0),
                "m76_2_barrier_probability": barrier,
            },
        )
        return opportunity, thesis

    @staticmethod
    def _conviction(score: float, confidence: float) -> str:
        value = min(score, confidence)
        if value >= 85:
            return "VERY_HIGH"
        if value >= 75:
            return "HIGH"
        if value >= 65:
            return "MODERATE"
        return "LOW"


class InstitutionalOpportunityIngestionService:
    def __init__(
        self,
        session: Session,
        *,
        eligibility: StockOpportunityEligibilityService | None = None,
        adapter: StockOpportunityThesisAdapter | None = None,
        governance: OpportunityGovernancePolicy | None = None,
    ) -> None:
        self.session = session
        self.eligibility = eligibility or StockOpportunityEligibilityService()
        self.adapter = adapter or StockOpportunityThesisAdapter()
        self.repository = InstitutionalOpportunityRepository(session, governance)

    def latest_publication(self, publication_name: str = "current_stock_intelligence") -> StockScannerPublicationModel | None:
        return (
            self.session.query(StockScannerPublicationModel)
            .filter(StockScannerPublicationModel.publication_name == publication_name)
            .filter(StockScannerPublicationModel.status.in_(("READY", "DEGRADED")))
            .order_by(desc(StockScannerPublicationModel.snapshot_timestamp))
            .first()
        )

    def ingest(
        self,
        *,
        publication_name: str = "current_stock_intelligence",
        symbols: Iterable[str] | None = None,
        limit: int | None = None,
        actor: str = "m62-opportunity-ingestion",
    ) -> OpportunityIngestionResult:
        publication = self.latest_publication(publication_name)
        if publication is None:
            raise LookupError(f"Stock Intelligence publication not found: {publication_name}")
        query = self.session.query(StockScannerCandidateModel).filter(
            StockScannerCandidateModel.scanner_run_id == publication.scanner_run_id
        )
        symbol_values = tuple(sorted({str(item).strip().upper() for item in (symbols or ()) if str(item).strip()}))
        if symbol_values:
            query = query.filter(StockScannerCandidateModel.symbol.in_(symbol_values))
        query = query.order_by(desc(StockScannerCandidateModel.score), StockScannerCandidateModel.symbol)
        if limit is not None and limit > 0:
            query = query.limit(limit)
        candidates = query.all()

        resolution = _load_existing_opportunity_resolution(
            self.session,
            stock_scanner_run_id=str(publication.scanner_run_id),
            candidates=candidates,
        )
        if resolution.exact_symbol_mismatches:
            raise RuntimeError(
                "Exact current opportunity lineage has symbol mismatches for "
                + ", ".join(resolution.exact_symbol_mismatches)
            )
        if resolution.unsafe_logical_claims:
            raise RuntimeError(
                "Logical opportunity continuity is claimed by multiple current "
                "candidates: "
                + json.dumps(
                    {
                        key: list(value)
                        for key, value in resolution.unsafe_logical_claims.items()
                    },
                    sort_keys=True,
                )
            )

        discovered = 0
        validated = 0
        rejected = 0
        existing = 0
        refreshed = 0
        existing_rejected = 0
        ids: list[str] = []
        rejection_counts: dict[str, int] = {}
        now = datetime.now(timezone.utc)

        for candidate in candidates:
            payload = dict(candidate.payload_json or {})
            decision = self.eligibility.evaluate(payload, snapshot_timestamp=candidate.snapshot_timestamp, now=now)
            continuity_key = _candidate_continuity_key(payload, symbol=candidate.symbol)
            exact_row = resolution.exact_by_candidate.get(str(candidate.id))
            logical_row = resolution.logical_by_continuity.get(
                continuity_key
            )
            existing_row = exact_row or logical_row
            continuity_match = (
                "EXACT_CANDIDATE" if exact_row is not None
                else ("LOGICAL_REFRESH" if existing_row is not None else "NEW")
            )

            # Preserve completed exact source decisions and all of their
            # downstream lineage. Never revive or relink an older opportunity.
            if (
                exact_row is not None
                and str(exact_row.state)
                not in PRE_EXECUTION_CONTINUITY_STATES
            ):
                existing += 1
                if not decision.eligible:
                    rejected += 1
                    for reason in decision.reasons:
                        rejection_counts[reason] = (
                            rejection_counts.get(reason, 0) + 1
                        )
                continue

            if not decision.eligible:
                rejected += 1
                for reason in decision.reasons:
                    rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
                if existing_row is not None:
                    existing += 1
                    current = OpportunityState(existing_row.state)
                    if current in {OpportunityState.DISCOVERED, OpportunityState.VALIDATED}:
                        self.repository.transition(
                            existing_row.opportunity_id,
                            OpportunityState.REJECTED,
                            actor,
                            "Stock Intelligence candidate failed refreshed eligibility: " + ", ".join(decision.reasons),
                        )
                        existing_rejected += 1
                continue

            if existing_row is not None:
                existing += 1
                opportunity_id = existing_row.opportunity_id
                thesis_id = existing_row.thesis_id
            else:
                opportunity_id = f"m62-opp-{uuid4().hex}"
                thesis_id = f"m62-thesis-{uuid4().hex}"

            opportunity, thesis = self.adapter.adapt(
                candidate=candidate,
                publication=publication,
                opportunity_id=opportunity_id,
                thesis_id=thesis_id,
            )
            opportunity = _separate_source_and_contract_option_lineage(
                opportunity,
                existing_row,
            )
            idi_payload = dict(opportunity.metadata.get("institutional_decision_intelligence") or {})
            opportunity = replace(
                opportunity,
                metadata={
                    **opportunity.metadata,
                    "opportunity_quality": decision.opportunity_quality,
                    "eligibility_warnings": list(decision.warnings),
                    "m76_2_2_continuity_key": "|".join(continuity_key),
                    "m76_2_2_continuity_match": continuity_match,
                    "m68_2_1_12_exact_lineage_precedence": True,
                    "m68_2_1_12_logical_collision_prevented": bool(
                        exact_row is not None
                        and logical_row is not None
                        and str(exact_row.opportunity_id)
                        != str(logical_row.opportunity_id)
                    ),
                    "m76_2_2_source_decision_fingerprint": _stable_json_fingerprint(idi_payload) if idi_payload else None,
                    "m76_2_2_source_scanner_run_id": publication.scanner_run_id,
                    "m76_2_2_source_candidate_id": candidate.id,
                    "primary_timeframe": str(payload.get("primary_timeframe") or "1d"),
                    "m76_2_2_current_decision_snapshot": bool(idi_payload.get("version")),
                },
            )

            if existing_row is not None:
                existing_payload = dict(existing_row.payload_json or {})
                old_certification = dict((existing_payload.get("metadata") or {}).get("trade_plan_certification") or {})
                new_certification = dict(opportunity.metadata.get("trade_plan_certification") or {})
                old_fingerprint = str(old_certification.get("plan_fingerprint") or old_certification.get("source_plan_fingerprint") or "")
                new_fingerprint = str(new_certification.get("plan_fingerprint") or new_certification.get("source_plan_fingerprint") or "")
                source_plan_changed = bool(old_fingerprint and new_fingerprint and old_fingerprint != new_fingerprint)
                old_metadata = dict((existing_payload.get("metadata") or {}))
                opportunity = replace(
                    opportunity,
                    state=OpportunityState(existing_row.state),
                    version=existing_row.version,
                    created_at=existing_row.created_at,
                    updated_at=now.isoformat(),
                    metadata={
                        **opportunity.metadata,
                        "m75_2_2_source_plan_changed": source_plan_changed,
                        "previous_source_plan_fingerprint": old_fingerprint or None,
                        "source_plan_fingerprint": new_fingerprint or None,
                        "m76_2_2_previous_scanner_run_id": existing_row.stock_scanner_run_id,
                        "m76_2_2_previous_candidate_id": existing_row.stock_candidate_id,
                        "m76_2_2_previous_source_decision_fingerprint": old_metadata.get("m76_2_2_source_decision_fingerprint"),
                    },
                )
                self.repository.save_opportunity(opportunity, thesis)
                if source_plan_changed:
                    self.repository.reset_for_source_plan_change(
                        opportunity_id, actor=actor, old_fingerprint=old_fingerprint, new_fingerprint=new_fingerprint
                    )
                refreshed += 1
                validated += 1
                ids.append(opportunity_id)
                continue

            self.repository.save_opportunity(opportunity, thesis)
            self.repository.transition(
                opportunity_id,
                OpportunityState.VALIDATED,
                actor,
                "Stock Intelligence thesis passed Phase 2 eligibility",
            )
            discovered += 1
            validated += 1
            ids.append(opportunity_id)

        self.session.flush()
        return OpportunityIngestionResult(
            publication_name=publication.publication_name,
            stock_scanner_run_id=publication.scanner_run_id,
            requested=len(candidates),
            discovered=discovered,
            validated=validated,
            rejected=rejected,
            existing=existing,
            refreshed=refreshed,
            existing_rejected=existing_rejected,
            exact_current_lineage_rows=len(
                resolution.exact_by_candidate
            ),
            terminal_exact_preserved=len(
                resolution.terminal_exact_candidate_ids
            ),
            lineage_collisions_prevented=len(
                resolution.prevented_collision_candidate_ids
            ),
            unsafe_logical_contentions=len(
                resolution.unsafe_logical_claims
            ),
            opportunity_ids=tuple(ids),
            rejection_counts=rejection_counts,
        )
