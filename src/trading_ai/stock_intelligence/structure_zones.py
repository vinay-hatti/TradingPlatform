from __future__ import annotations

from dataclasses import asdict, replace
from math import log1p
from typing import Iterable

from .profile import InstitutionalStructureZone, PriceLevel, PriceZone, StockIntelligenceProfile

_TIMEFRAME_PRIORITY = {
    "1mo": 70, "1w": 60, "1d": 50, "4h": 40, "2h": 35,
    "1h": 30, "30m": 20, "15m": 15, "5m": 10, "1m": 5,
}
_DEALER_COMPONENTS = {"PUT_WALL", "CALL_WALL", "GAMMA_FLIP"}


def _unique(values: Iterable[str]) -> list[str]:
    cleaned = {str(value).strip() for value in values if str(value).strip()}
    return sorted(cleaned, key=lambda value: (-_TIMEFRAME_PRIORITY.get(value, 0), value))


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


class InstitutionalStructureZoneEngine:
    """Build prioritized institutional structure zones from all structural evidence.

    Raw support/resistance and supply/demand objects remain available for auditability.
    This engine clusters them with dealer walls and gamma flip, then adds an actionable
    hierarchy, price-relative state, distance, and relevance so every downstream
    consumer uses one authoritative structure model.
    """

    def build(self, profile: StockIntelligenceProfile) -> list[InstitutionalStructureZone]:
        close = self._close(profile)
        atr = self._atr(profile)
        primitives: list[dict] = []

        for level in profile.support_levels:
            primitives.append(self._from_level(level, "SUPPORT", atr))
        for level in profile.resistance_levels:
            primitives.append(self._from_level(level, "RESISTANCE", atr))
        for zone in profile.demand_zones:
            primitives.append(self._from_price_zone(zone, "SUPPORT"))
        for zone in profile.supply_zones:
            primitives.append(self._from_price_zone(zone, "RESISTANCE"))

        context_evidence = dict(getattr(profile.context, "evidence", {}) or {})
        dealer_levels = dict(context_evidence.get("dealer_levels") or {})
        dealer_context = {
            "positioning": str(getattr(profile.context, "dealer_positioning", "UNKNOWN") or "UNKNOWN"),
            "gamma_regime": str(getattr(profile.context, "gamma_regime", "UNKNOWN") or "UNKNOWN"),
            "confidence_score": float(dealer_levels.get("confidence_score") or 50.0),
        }
        put_wall = dealer_levels.get("primary_put_wall")
        call_wall = dealer_levels.get("primary_call_wall")
        gamma_flip = dealer_levels.get("gamma_flip")
        dealer_confidence = dealer_context["confidence_score"]

        if self._positive(put_wall):
            primitives.append(self._dealer_primitive("SUPPORT", float(put_wall), "PUT_WALL", atr, dealer_confidence, dealer_context))
        if self._positive(call_wall):
            primitives.append(self._dealer_primitive("RESISTANCE", float(call_wall), "CALL_WALL", atr, dealer_confidence, dealer_context))
        if self._positive(gamma_flip):
            side = "SUPPORT" if float(gamma_flip) <= close else "RESISTANCE"
            primitives.append(self._dealer_primitive(side, float(gamma_flip), "GAMMA_FLIP", atr, dealer_confidence * 0.85, dealer_context))

        zones: list[InstitutionalStructureZone] = []
        for side in ("SUPPORT", "RESISTANCE"):
            items = sorted((item for item in primitives if item["zone_type"] == side), key=lambda item: item["center"])
            clusters: list[list[dict]] = []
            for item in items:
                match = next((cluster for cluster in clusters if self._overlaps_cluster(item, cluster, close, atr)), None)
                if match is None:
                    clusters.append([item])
                else:
                    match.append(item)
            built = [self._build_cluster(side, cluster, close, atr) for cluster in clusters]
            built.sort(key=lambda zone: (abs(zone.representative_price - close), -zone.relevance_score, -zone.strength))
            zones.extend(built[:5])

        zones = self._apply_hierarchy(zones, close)
        zones.sort(key=lambda zone: (
            self._hierarchy_rank(zone.hierarchy),
            0 if zone.zone_type == "SUPPORT" else 1,
            abs(zone.distance_pct),
            -zone.relevance_score,
        ))
        return zones

    @staticmethod
    def _close(profile: StockIntelligenceProfile) -> float:
        state = profile.timeframe_states.get(profile.primary_timeframe)
        if state is None and profile.timeframe_states:
            state = next(iter(profile.timeframe_states.values()))
        return float(getattr(state, "close", 0.0) or 0.0)

    @staticmethod
    def _atr(profile: StockIntelligenceProfile) -> float:
        state = profile.timeframe_states.get(profile.primary_timeframe)
        if state is None and profile.timeframe_states:
            state = next(iter(profile.timeframe_states.values()))
        atr = float(getattr(state, "atr", 0.0) or 0.0)
        close = float(getattr(state, "close", 0.0) or 0.0)
        return max(atr, close * 0.005, 0.01)

    @staticmethod
    def _positive(value) -> bool:
        try:
            return float(value) > 0
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _from_level(level: PriceLevel, side: str, atr: float) -> dict:
        half_width = max(atr * 0.10, level.price * 0.0006)
        return {
            "zone_type": side,
            "lower": max(0.01, level.price - half_width),
            "upper": level.price + half_width,
            "center": level.price,
            "strength": float(level.strength),
            "confluence": float(level.confluence_score),
            "touch_count": int(level.touch_count),
            "holding_probability": float(level.holding_probability),
            "break_probability": float(level.break_probability),
            "timeframes": list(level.contributing_timeframes or [level.timeframe]),
            "component": "PRICE_LEVEL",
            "freshness": "STRUCTURAL",
            "payload": asdict(level),
            "dealer_context": {},
        }

    @staticmethod
    def _from_price_zone(zone: PriceZone, side: str) -> dict:
        center = (float(zone.lower_bound) + float(zone.upper_bound)) / 2.0
        freshness_bonus = {"FRESH": 12, "TESTED": 5, "STRUCTURAL": 2, "STALE": -12}.get(str(zone.freshness).upper(), 0)
        return {
            "zone_type": side,
            "lower": float(zone.lower_bound),
            "upper": float(zone.upper_bound),
            "center": center,
            "strength": _clamp(float(zone.strength) + freshness_bonus),
            "confluence": float(zone.strength),
            "touch_count": int(zone.test_count),
            "holding_probability": _clamp(45 + float(zone.strength) * 0.45, 5, 95) / 100.0,
            "break_probability": _clamp(55 - float(zone.strength) * 0.45, 5, 95) / 100.0,
            "timeframes": list(zone.contributing_timeframes or [zone.timeframe]),
            "component": "DEMAND_ZONE" if side == "SUPPORT" else "SUPPLY_ZONE",
            "freshness": str(zone.freshness),
            "payload": asdict(zone),
            "dealer_context": {},
        }

    @staticmethod
    def _dealer_primitive(side: str, price: float, component: str, atr: float, confidence: float, context: dict) -> dict:
        half_width = max(atr * 0.12, price * 0.0008)
        strength = _clamp(45 + confidence * 0.45)
        dealer_context = {
            **context,
            "wall_type": component,
            "wall_price": price,
            "confidence_score": round(confidence, 2),
        }
        return {
            "zone_type": side,
            "lower": max(0.01, price - half_width),
            "upper": price + half_width,
            "center": price,
            "strength": strength,
            "confluence": 35.0,
            "touch_count": 0,
            "holding_probability": _clamp(45 + confidence * 0.35, 5, 95) / 100.0,
            "break_probability": _clamp(55 - confidence * 0.35, 5, 95) / 100.0,
            "timeframes": ["dealer"],
            "component": component,
            "freshness": "CURRENT",
            "payload": {"price": price, "confidence": confidence},
            "dealer_context": dealer_context,
        }

    @staticmethod
    def _overlaps_cluster(item: dict, cluster: list[dict], close: float, atr: float) -> bool:
        lower = min(value["lower"] for value in cluster)
        upper = max(value["upper"] for value in cluster)
        tolerance = max(atr * 0.45, close * 0.004)
        return item["lower"] <= upper + tolerance and item["upper"] >= lower - tolerance

    @staticmethod
    def _build_cluster(side: str, cluster: list[dict], close: float, atr: float) -> InstitutionalStructureZone:
        weights = [max(1.0, item["strength"]) for item in cluster]
        total_weight = sum(weights)
        representative = sum(item["center"] * weight for item, weight in zip(cluster, weights)) / total_weight
        original_lower = min(item["lower"] for item in cluster)
        original_upper = max(item["upper"] for item in cluster)
        lower, upper = original_lower, original_upper
        max_width = max(atr * 0.80, close * 0.008)
        if upper - lower > max_width:
            lower = representative - max_width / 2.0
            upper = representative + max_width / 2.0

        components = sorted({item["component"] for item in cluster})
        timeframes = _unique(tf for item in cluster for tf in item["timeframes"] if tf != "dealer")
        primary = timeframes[0] if timeframes else "dealer"
        touch_count = sum(item["touch_count"] for item in cluster)
        freshness_values = {str(item["freshness"]).upper() for item in cluster}
        freshness = "FRESH" if {"FRESH", "CURRENT"} & freshness_values else "TESTED" if "TESTED" in freshness_values else "STRUCTURAL"

        avg_strength = sum(item["strength"] for item in cluster) / len(cluster)
        freshness_score = {"FRESH": 10.0, "TESTED": 3.0, "STRUCTURAL": 0.0}.get(freshness, -8.0)
        strength = _clamp(avg_strength * 0.72 + min(16.0, log1p(touch_count) * 4.0) + freshness_score + min(10.0, (len(cluster) - 1) * 2.5))

        component_diversity = len(components)
        timeframe_diversity = len(timeframes)
        dealer_bonus = 10.0 if _DEALER_COMPONENTS.intersection(components) else 0.0
        confluence = _clamp(18.0 + component_diversity * 14.0 + timeframe_diversity * 11.0 + dealer_bonus + min(12.0, len(cluster) * 2.0))

        source_holding = sum(item["holding_probability"] for item in cluster) / len(cluster) * 100.0
        holding = _clamp(source_holding * 0.55 + strength * 0.25 + confluence * 0.20, 5, 95)
        distance_pct = InstitutionalStructureZoneEngine._distance_pct(side, lower, upper, close)
        distance_score = _clamp(100.0 - abs(distance_pct) * 9.0)
        relevance = _clamp(strength * 0.30 + confluence * 0.30 + holding * 0.20 + distance_score * 0.20)
        status = InstitutionalStructureZoneEngine._status(side, lower, upper, close)
        dealer_context = next((dict(item["dealer_context"]) for item in cluster if item.get("dealer_context")), {})

        evidence = {
            "component_count": len(cluster),
            "components": components,
            "raw_lower_bound": original_lower,
            "raw_upper_bound": original_upper,
            "distance_from_close_pct": distance_pct,
            "members": [item["payload"] for item in cluster],
            "strength_definition": "reaction quality, touches, recency, and source strength",
            "confluence_definition": "independent component, timeframe, and dealer-source diversity",
        }
        return InstitutionalStructureZone(
            zone_type=side,
            lower_bound=round(max(0.01, lower), 4),
            upper_bound=round(upper, 4),
            representative_price=round(representative, 4),
            strength=round(strength, 2),
            confluence_score=round(confluence, 2),
            holding_probability=round(holding / 100.0, 4),
            break_probability=round(1.0 - holding / 100.0, 4),
            primary_timeframe=primary,
            contributing_timeframes=timeframes,
            components=components,
            touch_count=touch_count,
            freshness=freshness,
            status=status,
            distance_pct=round(distance_pct, 4),
            relevance_score=round(relevance, 2),
            dealer_context=dealer_context,
            evidence=evidence,
        )

    @staticmethod
    def _distance_pct(side: str, lower: float, upper: float, close: float) -> float:
        if not close or lower <= close <= upper:
            return 0.0
        boundary = upper if side == "SUPPORT" else lower
        return (boundary - close) / close * 100.0

    @staticmethod
    def _status(side: str, lower: float, upper: float, close: float) -> str:
        if lower <= close <= upper:
            return "ACTIVE"
        if side == "SUPPORT":
            return "BELOW_PRICE" if close > upper else "BROKEN"
        return "OVERHEAD" if close < lower else "BROKEN"

    @staticmethod
    def _hierarchy_rank(value: str) -> int:
        return {
            "PRIMARY_STRUCTURE": 0,
            "SECONDARY_STRUCTURE": 1,
            "MAJOR_STRUCTURE": 2,
            "DEALER_STRUCTURE": 3,
            "HISTORICAL_STRUCTURE": 4,
        }.get(value, 9)

    @staticmethod
    def _apply_hierarchy(zones: list[InstitutionalStructureZone], close: float) -> list[InstitutionalStructureZone]:
        result: list[InstitutionalStructureZone] = []
        for side in ("SUPPORT", "RESISTANCE"):
            side_zones = [zone for zone in zones if zone.zone_type == side]
            dealer = [zone for zone in side_zones if _DEALER_COMPONENTS.intersection(zone.components)]
            nondealer = [zone for zone in side_zones if zone not in dealer]
            actionable = sorted(
                (zone for zone in nondealer if zone.status in {"ACTIVE", "BELOW_PRICE", "OVERHEAD"}),
                key=lambda zone: (abs(zone.distance_pct), -zone.relevance_score),
            )
            primary = actionable[0] if actionable else None
            secondary = actionable[1] if len(actionable) > 1 else None
            for zone in side_zones:
                hierarchy = "HISTORICAL_STRUCTURE"
                if zone is primary:
                    hierarchy = "PRIMARY_STRUCTURE"
                elif zone is secondary:
                    hierarchy = "SECONDARY_STRUCTURE"
                elif "1mo" in zone.contributing_timeframes or zone.primary_timeframe == "1mo":
                    hierarchy = "MAJOR_STRUCTURE"
                elif zone in dealer:
                    hierarchy = "DEALER_STRUCTURE"
                result.append(replace(zone, hierarchy=hierarchy))
        return result
