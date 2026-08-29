from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _upper(value: Any) -> str:
    return str(value or "").strip().upper()


def _distance_pct(price: float | None, level: float | None) -> float | None:
    if price is None or level is None or not price:
        return None
    return 100.0 * (level - price) / price


@dataclass(frozen=True)
class InstitutionalVolumeResponseInterpretation:
    version: str
    classification: str
    directional_implication: str
    confidence: float
    raw_volume_signal: str
    raw_volume_regime: str
    participation_state: str
    breakout_state: str
    location_context: str
    price_response: str
    nearest_resistance: float | None
    resistance_distance_pct: float | None
    nearest_support: float | None
    support_distance_pct: float | None
    reason_codes: list[str]
    evidence: dict[str, Any]
    governance: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class InstitutionalVolumeResponseClassifier:
    """Read-only semantic hardening for already-persisted stock-intelligence evidence.

    This classifier does not participate in StockIntelligenceService generation,
    opportunity scoring, certification, allocation, or execution. It is applied only
    when candidate detail is read for presentation.
    """

    VERSION = "INSTITUTIONAL-VOLUME-RESPONSE-PRESENTATION-1.0"

    @staticmethod
    def _reference_price(payload: dict[str, Any]) -> float | None:
        plan = payload.get("trade_plan") or {}
        certification = plan.get("certification") or {}
        reference = plan.get("reference_market") or certification.get("reference_market") or {}
        value = reference.get("price")
        if value is not None:
            return _num(value)
        states = payload.get("timeframe_states") or {}
        primary = payload.get("primary_timeframe") or "1d"
        state = states.get(primary) or states.get("1d") or {}
        value = state.get("close")
        return _num(value) if value is not None else None

    @staticmethod
    def _levels(payload: dict[str, Any], key: str) -> list[float]:
        out: list[float] = []
        for row in payload.get(key) or []:
            if not isinstance(row, dict):
                continue
            value = row.get("price")
            if value is None:
                continue
            v = _num(value)
            if v > 0:
                out.append(v)
        return sorted(set(out))

    @staticmethod
    def _nearest_levels(payload: dict[str, Any], price: float | None) -> tuple[float | None, float | None]:
        if price is None:
            return None, None
        resistance = [v for v in InstitutionalVolumeResponseClassifier._levels(payload, "resistance_levels") if v >= price]
        support = [v for v in InstitutionalVolumeResponseClassifier._levels(payload, "support_levels") if v <= price]
        return (min(resistance) if resistance else None, max(support) if support else None)

    def classify(self, payload: dict[str, Any]) -> dict[str, Any]:
        volume = payload.get("institutional_volume") or {}
        evidence = volume.get("evidence") or {}
        participation = payload.get("participation") or {}
        breakout = payload.get("breakout") or {}

        raw_signal = _upper(volume.get("signal") or "UNAVAILABLE")
        regime = _upper(volume.get("regime") or "UNAVAILABLE")
        participation_state = _upper(participation.get("state") or "NEUTRAL")
        breakout_state = _upper(breakout.get("state") or "NONE")

        rv1 = _num(volume.get("relative_volume_1d"))
        persistence = _num(volume.get("persistence_score"))
        absorption = _num(volume.get("absorption_score"))
        accumulation = _num(volume.get("accumulation_score"), 50.0)
        distribution = _num(volume.get("distribution_score"), 50.0)
        breakout_confirm = _num(volume.get("breakout_confirmation_score"))
        breakdown_confirm = _num(volume.get("breakdown_confirmation_score"))
        clv = _num(volume.get("close_location_value"))
        price_change = _num(evidence.get("price_change_1d"))
        range_ratio = _num(evidence.get("range_ratio_vs_20d_median"), 1.0)
        signed_flow = _num(evidence.get("signed_volume_flow_20d"))
        cmf20 = _num(evidence.get("cmf_20d"))
        climactic = bool(evidence.get("climactic_volume"))
        absorption_side = _upper(evidence.get("absorption_side") or "NONE")

        price = self._reference_price(payload)
        nearest_resistance, nearest_support = self._nearest_levels(payload, price)
        res_dist = _distance_pct(price, nearest_resistance)
        sup_dist = None if price is None or nearest_support is None else 100.0 * (price - nearest_support) / price
        near_resistance = res_dist is not None and 0.0 <= res_dist <= 1.0
        near_support = sup_dist is not None and 0.0 <= sup_dist <= 1.0

        reasons: list[str] = []
        classification = "INCONCLUSIVE"
        implication = "NEUTRAL"
        confidence = 45.0

        if near_resistance:
            location = "AT_OR_NEAR_RESISTANCE"
            reasons.append("NEAR_RESISTANCE_LE_1PCT")
        elif near_support:
            location = "AT_OR_NEAR_SUPPORT"
            reasons.append("NEAR_SUPPORT_LE_1PCT")
        else:
            location = "MID_STRUCTURE"

        if clv >= 0.45:
            close_response = "STRONG_CLOSE"
            reasons.append("CLOSE_IN_UPPER_RANGE")
        elif clv <= -0.45:
            close_response = "WEAK_CLOSE"
            reasons.append("CLOSE_IN_LOWER_RANGE")
        else:
            close_response = "BALANCED_CLOSE"

        if range_ratio <= 1.05 and rv1 >= 1.5:
            reasons.append("HIGH_VOLUME_CONSTRAINED_RANGE")
        if climactic:
            reasons.append("CLIMACTIC_VOLUME")
        if persistence >= 70:
            reasons.append("PERSISTENT_VOLUME")
        if accumulation >= distribution + 8:
            reasons.append("ACCUMULATION_DOMINANT")
        elif distribution >= accumulation + 8:
            reasons.append("DISTRIBUTION_DOMINANT")

        # Highest-priority acceptance/rejection states.
        if breakout_state in {"BREAKOUT_CONFIRMED", "BREAKOUT_CONTINUATION"} and breakout_confirm >= 70 and clv >= 0.25:
            classification = "BREAKOUT_ACCEPTANCE"
            implication = "BULLISH_CONFIRMATION"
            confidence = min(95.0, 70.0 + (breakout_confirm - 70.0) * 0.35 + max(0.0, clv) * 10.0)
            reasons += ["BREAKOUT_STATE_CONFIRMED", "VOLUME_CONFIRMS_BREAKOUT"]
            price_response = "PRICE_ACCEPTED_ABOVE_RESISTANCE"

        elif breakout_state == "FAILED_BREAKOUT" or (
            near_resistance and climactic and clv <= -0.35 and price_change <= 0.005
        ):
            classification = "BREAKOUT_REJECTION"
            implication = "BEARISH_WARNING"
            confidence = min(95.0, 68.0 + abs(clv) * 18.0 + min(12.0, max(0.0, rv1 - 2.5) * 3.0))
            reasons += ["FAILED_OR_REJECTED_ADVANCE"]
            price_response = "HIGH_VOLUME_FAILED_TO_HOLD_ADVANCE"

        elif near_resistance and climactic and distribution >= accumulation and clv < 0:
            classification = "DISTRIBUTION_AT_RESISTANCE"
            implication = "BEARISH_WARNING"
            confidence = min(92.0, 65.0 + (distribution - accumulation) * 0.25 + abs(clv) * 12.0)
            reasons += ["SUPPLY_DOMINANT_AT_RESISTANCE"]
            price_response = "SUPPLY_EMERGING_NEAR_RESISTANCE"

        elif near_resistance and raw_signal == "SELLING_ABSORPTION" and participation_state in {"ACCUMULATION", "RE_ACCUMULATION"}:
            classification = "SELLING_ABSORPTION_AT_RESISTANCE"
            implication = "CONSTRUCTIVE_AWAITING_BREAKOUT_CONFIRMATION"
            confidence = min(88.0, 60.0 + absorption * 0.18 + max(0.0, persistence - 60.0) * 0.10)
            reasons += ["SELLING_PRESSURE_ABSORBED", "ACCUMULATION_CONTEXT"]
            price_response = "SUPPLY_ABSORBED_BUT_RESISTANCE_NOT_YET_CLEARED"

        elif raw_signal == "SELLING_ABSORPTION" and range_ratio <= 1.05 and price_change >= -0.005:
            classification = "CONSTRUCTIVE_SELLING_ABSORPTION"
            implication = "BULLISH_LEAN"
            confidence = min(86.0, 58.0 + absorption * 0.20 + max(0.0, persistence - 50.0) * 0.08)
            reasons += ["SELLING_PRESSURE_WITH_LIMITED_DOWNSIDE_RESPONSE"]
            price_response = "SELLING_PRESSURE_NOT_PRODUCING_MATERIAL_DECLINE"

        elif raw_signal == "BUYING_ABSORPTION" and near_resistance and clv <= 0.25:
            classification = "BUYING_EXHAUSTION_AT_RESISTANCE"
            implication = "BEARISH_CAUTION"
            confidence = min(86.0, 58.0 + absorption * 0.18 + max(0.0, rv1 - 1.5) * 3.0)
            reasons += ["BUYING_EFFORT_WITH_LIMITED_UPSIDE_PROGRESS"]
            price_response = "BUYING_PRESSURE_NOT_CLEARING_RESISTANCE"

        elif near_support and climactic and clv >= 0.25 and price_change >= -0.01:
            classification = "SELLING_EXHAUSTION_AT_SUPPORT"
            implication = "BULLISH_REVERSAL_WATCH"
            confidence = min(88.0, 62.0 + max(0.0, rv1 - 2.5) * 3.0 + clv * 10.0)
            reasons += ["CLIMACTIC_SELLING_REJECTED_NEAR_SUPPORT"]
            price_response = "LOWER_PRICES_REJECTED_ON_EXTREME_VOLUME"

        elif raw_signal == "ACCUMULATION_CONFIRMED" or (
            participation_state in {"ACCUMULATION", "RE_ACCUMULATION"} and accumulation >= distribution + 8
        ):
            classification = "ACCUMULATION_CONFIRMED"
            implication = "BULLISH"
            confidence = min(90.0, 60.0 + max(0.0, accumulation - 60.0) * 0.45)
            reasons += ["POSITIVE_FLOW_PERSISTENCE"]
            price_response = "CONSTRUCTIVE_ACCUMULATION"

        elif raw_signal == "DISTRIBUTION_CONFIRMED" or (
            participation_state in {"DISTRIBUTION", "RE_DISTRIBUTION"} and distribution >= accumulation + 8
        ):
            classification = "DISTRIBUTION_CONFIRMED"
            implication = "BEARISH"
            confidence = min(90.0, 60.0 + max(0.0, distribution - 60.0) * 0.45)
            reasons += ["NEGATIVE_FLOW_PERSISTENCE"]
            price_response = "PERSISTENT_DISTRIBUTION"

        elif climactic:
            classification = "CLIMACTIC_VOLUME_INCONCLUSIVE"
            implication = "CAUTION"
            confidence = 60.0
            reasons += ["EXTREME_VOLUME_WITHOUT_CLEAR_PRICE_RESPONSE"]
            price_response = close_response

        else:
            classification = "INCONCLUSIVE"
            implication = "NEUTRAL"
            confidence = 45.0
            reasons += ["NO_DOMINANT_RESPONSE_CLASS"]
            price_response = close_response

        if signed_flow > 0.20:
            reasons.append("POSITIVE_SIGNED_FLOW_20D")
        elif signed_flow < -0.20:
            reasons.append("NEGATIVE_SIGNED_FLOW_20D")
        if cmf20 > 0.10:
            reasons.append("POSITIVE_CMF_20D")
        elif cmf20 < -0.10:
            reasons.append("NEGATIVE_CMF_20D")

        result = InstitutionalVolumeResponseInterpretation(
            version=self.VERSION,
            classification=classification,
            directional_implication=implication,
            confidence=round(max(0.0, min(100.0, confidence)), 1),
            raw_volume_signal=raw_signal,
            raw_volume_regime=regime,
            participation_state=participation_state,
            breakout_state=breakout_state,
            location_context=location,
            price_response=price_response,
            nearest_resistance=nearest_resistance,
            resistance_distance_pct=None if res_dist is None else round(res_dist, 3),
            nearest_support=nearest_support,
            support_distance_pct=None if sup_dist is None else round(sup_dist, 3),
            reason_codes=list(dict.fromkeys(reasons)),
            evidence={
                "reference_price": price,
                "relative_volume_1d": rv1,
                "persistence_score": persistence,
                "absorption_score": absorption,
                "absorption_side": absorption_side,
                "accumulation_score": accumulation,
                "distribution_score": distribution,
                "breakout_confirmation_score": breakout_confirm,
                "breakdown_confirmation_score": breakdown_confirm,
                "close_location_value": clv,
                "price_change_1d": price_change,
                "range_ratio_vs_20d_median": range_ratio,
                "signed_volume_flow_20d": signed_flow,
                "cmf_20d": cmf20,
                "climactic_volume": climactic,
            },
            governance={
                "presentation_only": True,
                "stored_candidate_payload_mutation": False,
                "stock_intelligence_score_effect": False,
                "ranking_effect": False,
                "trade_plan_certification_effect": False,
                "m64_allocation_effect": False,
                "execution_effect": False,
            },
        )
        return result.as_dict()
