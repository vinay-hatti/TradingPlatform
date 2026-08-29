from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from math import copysign, sqrt
from statistics import mean, pstdev
from typing import Iterable


POLICY_VERSION = "M68.2.1-POINT-IN-TIME-BREADTH-INFLECTION-1.0"


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def signed_clamp(value: float) -> float:
    return clamp(value, -100.0, 100.0)


def pct_change(a: float, b: float) -> float:
    return 0.0 if not a else (b / a - 1.0) * 100.0


def _number(value: object, default: float | None = None) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _normalized_probability(value: object) -> float | None:
    result = _number(value)
    if result is None:
        return None
    return clamp(result / 100.0 if result > 1.0 else result, 0.0, 1.0)


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        allow_nan=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


@dataclass(frozen=True)
class Bar:
    close: float
    high: float
    low: float
    volume: float
    as_of: str | None = None


class InstitutionalInflectionEngine:
    """Deterministic, directionally symmetric institutional inflection engine.

    ``directional_score`` is signed (-100 bearish to +100 bullish).
    ``signal_strength`` is direction-neutral (0 to 100). Confidence measures
    input quality and component agreement; it is not a bullishness proxy.
    """

    DIRECTIONAL_WEIGHTS = {
        "trend": 0.25,
        "structure": 0.23,
        "dealer": 0.18,
        "participation": 0.15,
        "breadth": 0.11,
        "volatility": 0.08,
    }
    NEUTRAL_DEADBAND = 15.0
    ACCELERATION_MATERIALITY = 0.75
    THRESHOLDS = {
        "high_conviction": 80.0,
        "actionable": 70.0,
        "watch": 60.0,
    }

    @staticmethod
    def _dealer_direction(dealer_payload: dict) -> tuple[float, bool]:
        direct = _number(dealer_payload.get("directional_score"))
        if direct is not None:
            return signed_clamp(direct), True

        bull = _normalized_probability(dealer_payload.get("bull_probability"))
        bear = _normalized_probability(dealer_payload.get("bear_probability"))
        if bull is not None and bear is not None:
            return signed_clamp((bull - bear) * 100.0), True

        legacy = [
            _number(dealer_payload.get("gamma_score")),
            _number(
                dealer_payload.get("wall_migration_score"),
                _number(dealer_payload.get("migration_score")),
            ),
            _number(dealer_payload.get("hedge_pressure_score")),
        ]
        populated = [value for value in legacy if value is not None]
        if populated:
            return signed_clamp((mean(populated) - 50.0) * 2.0), True
        return 0.0, False

    @staticmethod
    def _input_quality(
        *,
        build_mode: str,
        dealer_available: bool,
        implied_volatility_available: bool,
        option_spread_available: bool,
        breadth_available: bool,
        dealer_quality: float | None,
    ) -> tuple[float, list[str]]:
        checks = {
            "underlying_history": (True, 45.0),
            "breadth": (breadth_available, 10.0),
            "dealer": (dealer_available, 20.0),
            "implied_volatility": (implied_volatility_available, 15.0),
            "option_liquidity": (option_spread_available, 10.0),
        }
        if build_mode == "UNDERLYING_PRIMARY":
            # Options-derived inputs are optional evidence during the primary
            # build and must never be represented as current.
            checks["underlying_history"] = (True, 65.0)
            checks["dealer"] = (dealer_available, 10.0)
            checks["implied_volatility"] = (True, 5.0)
            checks["option_liquidity"] = (True, 5.0)
        total = sum(weight for _, weight in checks.values()) or 1.0
        earned = sum(weight for available, weight in checks.values() if available)
        quality = earned / total * 100.0
        if dealer_available and dealer_quality is not None:
            quality = quality * 0.90 + clamp(dealer_quality) * 0.10
        missing = [name for name, (available, _) in checks.items() if not available]
        return clamp(quality), missing

    def evaluate(
        self,
        symbol: str,
        bars: Iterable[Bar],
        *,
        candidate_payload: dict | None = None,
        dealer_payload: dict | None = None,
        breadth_score: float | None = None,
        timeframe: str = "1d",
        build_mode: str = "MANUAL",
    ) -> dict:
        series = list(bars)
        if len(series) < 25:
            raise ValueError(f"At least 25 {timeframe} bars are required for {symbol}")
        if timeframe not in {"1d", "1w", "1mo"}:
            raise ValueError(f"Unsupported Inflection timeframe: {timeframe}")

        candidate_payload = candidate_payload or {}
        dealer_payload = dealer_payload or {}
        closes = [float(bar.close) for bar in series]
        highs = [float(bar.high) for bar in series]
        lows = [float(bar.low) for bar in series]
        volumes = [max(0.0, float(bar.volume)) for bar in series]
        if any(value <= 0 for value in closes):
            raise ValueError(f"Non-positive close encountered for {symbol}")
        returns = [
            pct_change(closes[index - 1], closes[index])
            for index in range(1, len(closes))
        ]

        fast = mean(closes[-5:])
        medium = mean(closes[-10:])
        slow = mean(closes[-20:])
        momentum_5 = pct_change(closes[-6], closes[-1])
        momentum_20 = pct_change(closes[-21], closes[-1])
        normalized_momentum_20 = momentum_20 / 4.0
        acceleration = momentum_5 - normalized_momentum_20
        trend_order = 1 if fast > medium > slow else -1 if fast < medium < slow else 0
        trend_directional = signed_clamp(
            trend_order * 55.0 + momentum_20 * 1.8 + acceleration * 7.0
        )

        recent_high = max(highs[-20:-1])
        recent_low = min(lows[-20:-1])
        last = closes[-1]
        average_range = mean(
            max(0.0, high - low)
            for high, low in zip(highs[-20:], lows[-20:])
        )
        range_width = max(recent_high - recent_low, abs(last) * 0.005)
        range_position = ((last - recent_low) / range_width) * 2.0 - 1.0
        structure_directional = signed_clamp(range_position * 72.0)

        compression_now = pstdev(returns[-5:]) if len(returns) >= 5 else 0.0
        compression_old = (
            pstdev(returns[-20:-5]) if len(returns) >= 20 else compression_now
        )
        compression_ratio = (
            compression_now / compression_old if compression_old > 1e-9 else 1.0
        )

        iv = _number(
            candidate_payload.get("implied_volatility"),
            _number(candidate_payload.get("iv")),
        )
        implied_volatility_available = iv is not None and iv > 0
        realized_volatility = pstdev(returns[-20:]) * sqrt(252) / 100.0
        volatility_divergence = (
            (realized_volatility - float(iv)) * 100.0
            if implied_volatility_available
            else None
        )
        volatility_magnitude = clamp(
            abs(1.0 - compression_ratio) * 45.0
            + (
                abs(volatility_divergence) * 1.5
                if volatility_divergence is not None
                else 0.0
            )
        )
        price_sign = (
            1.0
            if momentum_5 > 0.10
            else -1.0
            if momentum_5 < -0.10
            else float(trend_order)
        )
        volatility_directional = signed_clamp(price_sign * volatility_magnitude)

        average_volume = mean(volumes[-20:]) or 1.0
        recent_volume = mean(volumes[-3:])
        volume_ratio = recent_volume / average_volume
        participation_directional = signed_clamp(
            momentum_5 * 9.0
            + copysign(abs(volume_ratio - 1.0) * 28.0, momentum_5)
            if abs(momentum_5) > 0.05
            else 0.0
        )

        breadth_available = breadth_score is not None
        breadth = clamp(float(breadth_score)) if breadth_available else 50.0
        breadth_directional = (
            signed_clamp((breadth - 50.0) * 2.0) if breadth_available else 0.0
        )
        dealer_directional, dealer_available = self._dealer_direction(dealer_payload)

        spread = _number(
            candidate_payload.get("spread_pct"),
            _number(candidate_payload.get("bid_ask_spread_pct")),
        )
        option_spread_available = spread is not None and spread >= 0
        liquidity_quality = (
            clamp(100.0 - float(spread) * 2.0)
            if option_spread_available
            else 50.0
        )

        components = {
            "trend": trend_directional,
            "structure": structure_directional,
            "dealer": dealer_directional,
            "volatility": volatility_directional,
            "participation": participation_directional,
            "breadth": breadth_directional,
        }
        availability = {
            "trend": True,
            "structure": True,
            "dealer": dealer_available,
            "volatility": True,
            "participation": True,
            "breadth": breadth_available,
            "implied_volatility": implied_volatility_available,
            "option_liquidity": option_spread_available,
        }
        available_weights = {
            name: weight
            for name, weight in self.DIRECTIONAL_WEIGHTS.items()
            if availability.get(name, False)
        }
        # M68.2.1 intentionally does not renormalize around missing evidence.
        # Every configured component keeps its fixed policy weight. Missing
        # evidence contributes zero and forces an abstention below, preventing
        # the remaining components from being silently amplified.
        directional_score = signed_clamp(
            sum(
                components[name] * weight
                for name, weight in self.DIRECTIONAL_WEIGHTS.items()
                if availability.get(name, False)
            )
        )
        direction = (
            "BULLISH"
            if directional_score >= self.NEUTRAL_DEADBAND
            else "BEARISH"
            if directional_score <= -self.NEUTRAL_DEADBAND
            else "NEUTRAL"
        )

        mean_component_magnitude = (
            sum(
                abs(components[name]) * weight
                for name, weight in self.DIRECTIONAL_WEIGHTS.items()
                if availability.get(name, False)
            )
        )
        change_score = clamp(
            abs(acceleration) * 12.0
            + max(0.0, abs(range_position) - 0.85) * 55.0
            + abs(volume_ratio - 1.0) * 24.0
            + abs(compression_ratio - 1.0) * 20.0
        )
        signal_strength = clamp(
            10.0
            + abs(directional_score) * 0.55
            + mean_component_magnitude * 0.30
            + change_score * 0.15
        )

        dealer_quality = _number(
            dealer_payload.get("confidence_score"),
            _number(dealer_payload.get("quote_coverage_pct")),
        )
        input_quality, missing_inputs = self._input_quality(
            build_mode=build_mode,
            dealer_available=dealer_available,
            implied_volatility_available=implied_volatility_available,
            option_spread_available=option_spread_available,
            breadth_available=breadth_available,
            dealer_quality=dealer_quality,
        )
        direction_sign = (
            1.0 if direction == "BULLISH" else -1.0 if direction == "BEARISH" else 0.0
        )
        material = [
            (name, available_weights[name])
            for name in available_weights
            if abs(components[name]) >= 10.0
        ]
        material_weight = sum(weight for _, weight in material)
        agreement = (
            100.0
            * sum(
                weight
                for name, weight in material
                if components[name] * direction_sign > 0
            )
            / material_weight
            if material_weight and direction_sign
            else 50.0
        )
        confidence = clamp(input_quality * 0.60 + agreement * 0.40)

        breakout_buffer = max(average_range * 0.10, abs(last) * 0.0005)
        material_acceleration = abs(acceleration) >= self.ACCELERATION_MATERIALITY
        if direction == "BULLISH" and last > recent_high + breakout_buffer:
            transition_state = "EARLY_BREAKOUT"
            horizon = (1, 5)
        elif direction == "BEARISH" and last < recent_low - breakout_buffer:
            transition_state = "EARLY_BREAKDOWN"
            horizon = (1, 5)
        elif (
            direction == "BULLISH"
            and momentum_20 < -2.0
            and acceleration >= self.ACCELERATION_MATERIALITY
        ) or (
            direction == "BEARISH"
            and momentum_20 > 2.0
            and acceleration <= -self.ACCELERATION_MATERIALITY
        ):
            transition_state = "REVERSAL_SETUP"
            horizon = (3, 10)
        elif (
            direction == "BULLISH"
            and momentum_20 > 0
            and acceleration <= -self.ACCELERATION_MATERIALITY
        ) or (
            direction == "BEARISH"
            and momentum_20 < 0
            and acceleration >= self.ACCELERATION_MATERIALITY
        ):
            transition_state = "TREND_EXHAUSTION"
            horizon = (1, 7)
        elif (
            direction != "NEUTRAL"
            and trend_order == int(direction_sign)
            and abs(directional_score) >= 30.0
        ):
            transition_state = "TREND_CONTINUATION"
            horizon = (3, 10)
        else:
            transition_state = "TRANSITION_WATCH"
            horizon = (5, 15)

        missing_required = (
            not breadth_available
            or (
                build_mode == "OPTIONS_ENRICHMENT"
                and (
                    not dealer_available
                    or not implied_volatility_available
                    or not option_spread_available
                )
            )
        )
        if direction == "NEUTRAL" or confidence < 55.0 or missing_required:
            disposition = "ABSTAIN"
        elif signal_strength >= self.THRESHOLDS["high_conviction"]:
            disposition = "HIGH_CONVICTION"
        elif signal_strength >= self.THRESHOLDS["actionable"]:
            disposition = "ACTIONABLE"
        elif signal_strength >= self.THRESHOLDS["watch"]:
            disposition = "WATCH"
        else:
            disposition = "DEVELOPING"

        ordered_evidence = sorted(
            (
                (name, value)
                for name, value in components.items()
                if availability.get(name, False)
            ),
            key=lambda item: abs(item[1]),
            reverse=True,
        )
        evidence = [
            f"{name}:{value:+.1f} ({'bullish' if value > 0 else 'bearish' if value < 0 else 'neutral'})"
            for name, value in ordered_evidence[:4]
            if direction_sign == 0 or value * direction_sign >= 0
        ]
        conflicts = [
            f"{name}:{value:+.1f} conflicts with {direction.lower()} direction"
            for name, value in ordered_evidence
            if direction_sign and value * direction_sign < -10.0
        ]
        invalidation = {
            "price_below": round(recent_low, 4) if direction == "BULLISH" else None,
            "price_above": round(recent_high, 4) if direction == "BEARISH" else None,
            "directional_score_inside_deadband": self.NEUTRAL_DEADBAND,
            "confidence_below": 55.0,
        }

        input_contract = {
            "policy_version": POLICY_VERSION,
            "symbol": symbol,
            "timeframe": timeframe,
            "build_mode": build_mode,
            "bars": [
                [
                    bar.as_of,
                    round(bar.close, 8),
                    round(bar.high, 8),
                    round(bar.low, 8),
                    round(bar.volume, 4),
                ]
                for bar in series
            ],
            "breadth_score": breadth_score,
            "dealer_payload": dealer_payload,
            "implied_volatility": iv,
            "spread_pct": spread,
        }
        input_fingerprint = _canonical_hash(input_contract)
        semantic_contract = {
            "policy_version": POLICY_VERSION,
            "symbol": symbol,
            "timeframe": timeframe,
            "direction": direction,
            "transition_state": transition_state,
            "disposition": disposition,
            "strength_band": int(signal_strength // 5) * 5,
            "confidence_band": int(confidence // 5) * 5,
        }
        semantic_state_hash = _canonical_hash(semantic_contract)

        result = {
            "policy_version": POLICY_VERSION,
            "symbol": symbol,
            "timeframe": timeframe,
            "build_mode": build_mode,
            "direction": direction,
            "directional_score": round(directional_score, 4),
            "signal_strength": round(signal_strength, 4),
            # Backward-compatible alias. M68.2 consumers must use the named
            # directional/strength fields rather than infer semantics.
            "inflection_score": round(signal_strength, 4),
            "confidence": round(confidence, 4),
            "input_quality": round(input_quality, 4),
            "disposition": disposition,
            "transition_state": transition_state,
            "velocity": round(momentum_5, 4),
            "acceleration": round(acceleration, 4),
            "horizon_min_sessions": horizon[0],
            "horizon_max_sessions": horizon[1],
            "components": {
                name: round(value, 4) for name, value in components.items()
            },
            "component_decomposition": {
                name: {
                    "raw_score": round(components[name], 4),
                    "configured_weight": weight,
                    "available": bool(availability.get(name, False)),
                    "weighted_contribution": round(
                        components[name] * weight
                        if availability.get(name, False) else 0.0,
                        4,
                    ),
                }
                for name, weight in self.DIRECTIONAL_WEIGHTS.items()
            },
            "weight_contract": {
                "policy": "FIXED_NO_RENORMALIZATION",
                "configured_weight_total": round(
                    sum(self.DIRECTIONAL_WEIGHTS.values()), 8
                ),
                "available_weight_total": round(
                    sum(available_weights.values()), 8
                ),
            },
            "component_availability": availability,
            "evidence": evidence,
            "conflicting_evidence": conflicts,
            "missing_inputs": missing_inputs,
            "invalidation": invalidation,
            "diagnostics": {
                "momentum_5": round(momentum_5, 8),
                "momentum_20": round(momentum_20, 8),
                "compression_ratio": round(compression_ratio, 8),
                "volume_ratio": round(volume_ratio, 8),
                "realized_volatility_20d": round(realized_volatility, 8),
                "implied_volatility": (
                    None if iv is None else round(float(iv), 8)
                ),
                "volatility_divergence": (
                    None
                    if volatility_divergence is None
                    else round(volatility_divergence, 8)
                ),
                "range_position": round(range_position, 8),
                "liquidity_quality": round(liquidity_quality, 4),
                "agreement": round(agreement, 4),
                "material_acceleration": material_acceleration,
            },
            "input_fingerprint": input_fingerprint,
            "semantic_state_hash": semantic_state_hash,
            "thresholds": dict(self.THRESHOLDS),
        }
        result["state_hash"] = _canonical_hash(result)
        return result
