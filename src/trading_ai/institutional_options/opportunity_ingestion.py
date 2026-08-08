from __future__ import annotations

from dataclasses import dataclass, field, replace
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
    opportunity_ids: tuple[str, ...] = ()
    rejection_counts: dict[str, int] = field(default_factory=dict)


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
        quality = min(100.0, max(0.0,
            score * 0.35 + confidence * 0.25 + management_quality * 0.20 +
            min(100.0, structural_rr * 25.0) * 0.10 + alignment * 0.10
        ))
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
        participation = payload.get("participation") or {}
        breakout = payload.get("breakout") or {}
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
        if context.get("relative_strength_grade"):
            evidence.append(f"Relative strength: {context.get('relative_strength_grade')}")
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

        candidate_ids = [item.id for item in candidates]
        existing_rows = []
        if candidate_ids:
            existing_rows = (
                self.session.query(InstitutionalOpportunityModel)
                .filter(InstitutionalOpportunityModel.stock_scanner_run_id == publication.scanner_run_id)
                .filter(InstitutionalOpportunityModel.stock_candidate_id.in_(candidate_ids))
                .all()
            )
        existing_by_candidate = {row.stock_candidate_id: row for row in existing_rows}

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
            existing_row = existing_by_candidate.get(candidate.id)

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
            opportunity = replace(
                opportunity,
                metadata={
                    **opportunity.metadata,
                    "opportunity_quality": decision.opportunity_quality,
                    "eligibility_warnings": list(decision.warnings),
                },
            )

            if existing_row is not None:
                opportunity = replace(
                    opportunity,
                    state=OpportunityState(existing_row.state),
                    version=existing_row.version,
                    created_at=existing_row.created_at,
                    updated_at=now.isoformat(),
                )
                self.repository.save_opportunity(opportunity, thesis)
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
            opportunity_ids=tuple(ids),
            rejection_counts=rejection_counts,
        )
