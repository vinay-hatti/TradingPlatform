from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


@dataclass(frozen=True)
class UnderlyingOptionIntegrationPolicy:
    enabled: bool = False
    require_stock_intelligence: bool = True
    minimum_underlying_score: float = 55.0
    minimum_underlying_confidence: float = 45.0
    minimum_management_quality: float = 45.0
    minimum_structural_reward_risk: float = 1.20
    maximum_probability_adjustment: float = 0.12
    minimum_final_probability: float = 0.45
    minimum_edge_score: float = 35.0
    prefer_spreads_above_iv: float = 0.35
    prefer_long_premium_below_iv: float = 0.22


@dataclass
class UnderlyingOptionIntegrationProfile:
    available: bool
    allowed: bool
    symbol: str
    direction_aligned: bool
    raw_probability: float
    probability_adjustment: float
    adjusted_probability: float
    underlying_score: float
    underlying_confidence: float
    management_quality: float
    structural_reward_risk: float
    edge_score: float
    recommended_strategy: str
    recommended_entry_low: float | None = None
    recommended_entry_high: float | None = None
    underlying_stop: float | None = None
    underlying_targets: list[float] = field(default_factory=list)
    trailing_method: str = ""
    primary_category: str = ""
    structure: str = ""
    primary_timeframe: str = ""
    state_hash: str = ""
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


class UnderlyingOptionIntegrationService:
    """Governed adapter from persisted stock intelligence to option candidates.

    The service is intentionally side-effect free. It does not select or rebuild an
    option contract; it enriches and governs a contract already selected by the
    Polygon-backed option scanner.
    """

    def __init__(self, policy: UnderlyingOptionIntegrationPolicy | None = None):
        self.policy = policy or UnderlyingOptionIntegrationPolicy()

    def evaluate(
        self,
        *,
        symbol: str,
        signal: str,
        raw_probability: float | None,
        option_volatility: float,
        option_liquidity_score: float,
        option_contract_identity: str,
        stock_payload: Mapping[str, Any] | None,
    ) -> UnderlyingOptionIntegrationProfile:
        signal = str(signal or "").upper()
        bullish = signal in {"CALL", "BUY_CALL", "BULLISH"}
        expected_direction = "BULLISH" if bullish else "BEARISH"
        raw_probability = _clamp(_number(raw_probability, 0.50), 0.0, 1.0)

        if not stock_payload:
            reasons = ["STOCK_INTELLIGENCE_UNAVAILABLE"] if self.policy.require_stock_intelligence else []
            return UnderlyingOptionIntegrationProfile(
                available=False,
                allowed=not reasons,
                symbol=symbol,
                direction_aligned=False,
                raw_probability=raw_probability,
                probability_adjustment=0.0,
                adjusted_probability=raw_probability,
                underlying_score=0.0,
                underlying_confidence=0.0,
                management_quality=0.0,
                structural_reward_risk=0.0,
                edge_score=0.0,
                recommended_strategy="LONG_CALL" if bullish else "LONG_PUT",
                rejection_reasons=reasons,
                warnings=[] if reasons else ["Stock Intelligence unavailable; neutral integration applied"],
            )

        payload = _mapping(stock_payload)
        scores = _mapping(payload.get("scores"))
        plan = _mapping(payload.get("trade_plan"))
        entry = _mapping(plan.get("entry"))
        stop = _mapping(plan.get("stop"))
        targets_profile = _mapping(plan.get("targets"))
        trailing = _mapping(plan.get("trailing"))
        context = _mapping(payload.get("context"))
        breakout = _mapping(payload.get("breakout"))
        participation = _mapping(payload.get("participation"))

        direction = str(payload.get("direction", "NEUTRAL")).upper()
        direction_aligned = expected_direction in direction
        underlying_score = _number(scores.get("overall"), 0.0)
        confidence = _number(scores.get("confidence"), _number(payload.get("confidence"), 0.0))
        management_quality = _number(plan.get("management_quality"), 0.0)
        structural_rr = _number(plan.get("structural_reward_risk"), 0.0)
        alignment = _number(payload.get("alignment_score"), 50.0)
        context_adjustment = _number(context.get("adjustment"), 0.0)
        failure_probability = _number(breakout.get("failure_probability"), 50.0)
        deterioration = _number(participation.get("deterioration_risk"), 50.0)

        score_component = (underlying_score - 50.0) / 500.0
        alignment_component = (alignment - 50.0) / 600.0
        confidence_component = (confidence - 50.0) / 1000.0
        context_component = context_adjustment / 500.0
        management_component = (management_quality - 50.0) / 1000.0
        risk_component = -max(0.0, failure_probability - 50.0) / 1000.0
        deterioration_component = -max(0.0, deterioration - 50.0) / 1200.0
        direction_component = 0.025 if direction_aligned else -0.10

        adjustment = sum(
            (
                score_component,
                alignment_component,
                confidence_component,
                context_component,
                management_component,
                risk_component,
                deterioration_component,
                direction_component,
            )
        )
        adjustment = _clamp(
            adjustment,
            -self.policy.maximum_probability_adjustment,
            self.policy.maximum_probability_adjustment,
        )
        # Directional conflict is a hard thesis conflict, not a weak soft feature.
        # It must never result in a positive probability adjustment even when
        # the stock profile is otherwise high quality.
        if not direction_aligned:
            adjustment = min(adjustment, -0.06)
        adjusted_probability = _clamp(raw_probability + adjustment, 0.01, 0.99)

        volatility = max(0.0, _number(option_volatility))
        structure = str(payload.get("structure", "")).upper()
        category = str(scores.get("primary_category", "")).upper()
        if volatility >= self.policy.prefer_spreads_above_iv:
            recommended_strategy = "BULL_CALL_SPREAD" if bullish else "BEAR_PUT_SPREAD"
        elif volatility <= self.policy.prefer_long_premium_below_iv and structure in {
            "TRENDING", "EARLY_TREND", "EXPANSION"
        }:
            recommended_strategy = "LONG_CALL" if bullish else "LONG_PUT"
        elif category in {"BREAKOUT", "BREAKDOWN", "TREND_CONTINUATION"}:
            recommended_strategy = "LONG_CALL" if bullish else "LONG_PUT"
        else:
            recommended_strategy = "BULL_CALL_SPREAD" if bullish else "BEAR_PUT_SPREAD"

        targets = []
        for target in targets_profile.get("targets") or []:
            price = _number(_mapping(target).get("price"), 0.0)
            if price > 0:
                targets.append(price)

        entry_low = _number(entry.get("zone_low"), 0.0) or None
        entry_high = _number(entry.get("zone_high"), 0.0) or None
        recommended_stop = _number(stop.get("recommended_stop"), 0.0) or None
        trailing_method = str(trailing.get("method", "") or "")

        rejection_reasons: list[str] = []
        warnings: list[str] = []
        if not option_contract_identity:
            rejection_reasons.append("OPTION_CONTRACT_IDENTITY_MISSING")
        if not direction_aligned:
            rejection_reasons.append("UNDERLYING_DIRECTION_CONFLICT")
        if underlying_score < self.policy.minimum_underlying_score:
            rejection_reasons.append("UNDERLYING_SCORE_BELOW_MINIMUM")
        if confidence < self.policy.minimum_underlying_confidence:
            rejection_reasons.append("UNDERLYING_CONFIDENCE_BELOW_MINIMUM")
        if management_quality < self.policy.minimum_management_quality:
            rejection_reasons.append("MANAGEMENT_QUALITY_BELOW_MINIMUM")
        if structural_rr < self.policy.minimum_structural_reward_risk:
            rejection_reasons.append("STRUCTURAL_REWARD_RISK_BELOW_MINIMUM")
        if adjusted_probability < self.policy.minimum_final_probability:
            rejection_reasons.append("ADJUSTED_PROBABILITY_BELOW_MINIMUM")
        if recommended_stop is None:
            rejection_reasons.append("UNDERLYING_STRUCTURAL_STOP_MISSING")
        if not targets:
            rejection_reasons.append("UNDERLYING_TARGETS_MISSING")

        liquidity = _clamp(_number(option_liquidity_score), 0.0, 100.0)
        rr_multiplier = _clamp(structural_rr / 2.0, 0.4, 1.5)
        edge_score = _clamp(
            adjusted_probability * 100.0 * 0.55
            + underlying_score * 0.20
            + management_quality * 0.10
            + liquidity * 0.10
            + rr_multiplier * 100.0 * 0.05,
            0.0,
            100.0,
        )
        if edge_score < self.policy.minimum_edge_score:
            rejection_reasons.append("FINAL_EDGE_SCORE_BELOW_MINIMUM")

        if failure_probability > 60:
            warnings.append("Underlying breakout/breakdown failure risk is elevated")
        if deterioration > 60:
            warnings.append("Institutional participation deterioration risk is elevated")
        if context_adjustment < 0:
            warnings.append("External market/dealer context reduces the underlying thesis")

        evidence = [
            f"Underlying {direction} versus option thesis {expected_direction}",
            f"Underlying score {underlying_score:.2f}, confidence {confidence:.2f}",
            f"Timeframe alignment {alignment:.2f}",
            f"Management quality {management_quality:.2f}, structural R/R {structural_rr:.2f}",
            f"Probability adjustment {adjustment:+.4f}",
        ]

        return UnderlyingOptionIntegrationProfile(
            available=True,
            allowed=not rejection_reasons,
            symbol=symbol,
            direction_aligned=direction_aligned,
            raw_probability=round(raw_probability, 6),
            probability_adjustment=round(adjustment, 6),
            adjusted_probability=round(adjusted_probability, 6),
            underlying_score=round(underlying_score, 2),
            underlying_confidence=round(confidence, 2),
            management_quality=round(management_quality, 2),
            structural_reward_risk=round(structural_rr, 2),
            edge_score=round(edge_score, 2),
            recommended_strategy=recommended_strategy,
            recommended_entry_low=entry_low,
            recommended_entry_high=entry_high,
            underlying_stop=recommended_stop,
            underlying_targets=targets[:3],
            trailing_method=trailing_method,
            primary_category=category,
            structure=structure,
            primary_timeframe=str(payload.get("primary_timeframe", "")),
            state_hash=str(payload.get("state_hash", "")),
            warnings=warnings,
            rejection_reasons=sorted(set(rejection_reasons)),
            evidence=evidence,
        )


class StockIntelligenceOptionProvider:
    """Loads the latest published stock-intelligence candidate for a symbol."""

    def __init__(self, session, publication_name: str = "current_stock_intelligence"):
        self.session = session
        self.publication_name = publication_name

    def get(self, symbol: str) -> dict | None:
        from sqlalchemy import desc
        from .models import StockScannerCandidateModel, StockScannerPublicationModel

        publication = (
            self.session.query(StockScannerPublicationModel)
            .filter(StockScannerPublicationModel.publication_name == self.publication_name)
            .order_by(desc(StockScannerPublicationModel.snapshot_timestamp))
            .first()
        )
        if publication is None:
            return None
        row = (
            self.session.query(StockScannerCandidateModel)
            .filter(StockScannerCandidateModel.scanner_run_id == publication.scanner_run_id)
            .filter(StockScannerCandidateModel.symbol == str(symbol).upper())
            .order_by(desc(StockScannerCandidateModel.score))
            .first()
        )
        return dict(row.payload_json or {}) if row is not None else None
