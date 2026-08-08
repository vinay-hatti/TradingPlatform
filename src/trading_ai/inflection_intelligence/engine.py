from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import sqrt
from statistics import mean, pstdev
from typing import Iterable


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def pct_change(a: float, b: float) -> float:
    return 0.0 if not a else (b / a - 1.0) * 100.0


@dataclass(frozen=True)
class Bar:
    close: float
    high: float
    low: float
    volume: float


class InstitutionalInflectionEngine:
    WEIGHTS = {
        "trend": 0.20,
        "structure": 0.18,
        "dealer": 0.16,
        "volatility": 0.14,
        "participation": 0.14,
        "breadth": 0.10,
        "liquidity": 0.08,
    }

    def evaluate(self, symbol: str, bars: Iterable[Bar], *, candidate_payload: dict | None = None,
                 dealer_payload: dict | None = None, breadth_score: float = 50.0,
                 timeframe: str = "1d") -> dict:
        series = list(bars)
        if len(series) < 25:
            raise ValueError(f"At least 25 bars are required for {symbol}")
        candidate_payload = candidate_payload or {}
        dealer_payload = dealer_payload or {}
        closes = [b.close for b in series]
        highs = [b.high for b in series]
        lows = [b.low for b in series]
        volumes = [max(0.0, b.volume) for b in series]
        returns = [pct_change(closes[i - 1], closes[i]) for i in range(1, len(closes))]

        fast = mean(closes[-5:]); medium = mean(closes[-10:]); slow = mean(closes[-20:])
        momentum_5 = pct_change(closes[-6], closes[-1])
        momentum_20 = pct_change(closes[-21], closes[-1])
        acceleration = momentum_5 - momentum_20 / 4.0
        trend_direction = 1 if fast > medium > slow else -1 if fast < medium < slow else 0
        trend_score = clamp(50 + trend_direction * 22 + acceleration * 3.0)

        recent_high = max(highs[-20:-1]); recent_low = min(lows[-20:-1]); last = closes[-1]
        range_width = max(recent_high - recent_low, abs(last) * 0.005)
        breakout_proximity = (last - recent_low) / range_width
        compression_now = pstdev(returns[-5:]) if len(returns) >= 5 else 0.0
        compression_old = pstdev(returns[-20:-5]) if len(returns) >= 20 else compression_now
        compression_ratio = compression_now / compression_old if compression_old > 1e-9 else 1.0
        structure_score = clamp(45 + 35 * breakout_proximity + (12 if compression_ratio < 0.75 else -8 if compression_ratio > 1.4 else 0))

        iv = float(candidate_payload.get("implied_volatility") or candidate_payload.get("iv") or 0.0)
        rv = pstdev(returns[-20:]) * sqrt(252) / 100.0 if len(returns) >= 20 else 0.0
        vol_divergence = (rv - iv) * 100.0 if iv else 0.0
        volatility_score = clamp(50 + (1.0 - compression_ratio) * 30 + vol_divergence * 0.8)

        avg_volume = mean(volumes[-20:]) or 1.0
        recent_volume = mean(volumes[-3:])
        volume_ratio = recent_volume / avg_volume
        signed_pressure = momentum_5 * volume_ratio
        participation_score = clamp(50 + signed_pressure * 3.0 + (volume_ratio - 1.0) * 20)

        spread_pct = float(candidate_payload.get("spread_pct") or candidate_payload.get("bid_ask_spread_pct") or 0.05)
        liquidity_score = clamp(80 - spread_pct * 200 + (volume_ratio - 1.0) * 10)

        gamma = float(dealer_payload.get("gamma_score") or dealer_payload.get("gex_score") or 50.0)
        wall_migration = float(dealer_payload.get("wall_migration_score") or dealer_payload.get("migration_score") or 50.0)
        hedge_pressure = float(dealer_payload.get("hedge_pressure_score") or 50.0)
        dealer_score = clamp(mean([gamma, wall_migration, hedge_pressure]))

        components = {
            "trend": trend_score,
            "structure": structure_score,
            "dealer": dealer_score,
            "volatility": volatility_score,
            "participation": participation_score,
            "breadth": clamp(breadth_score),
            "liquidity": liquidity_score,
        }
        composite = sum(components[k] * w for k, w in self.WEIGHTS.items())
        bullish_evidence = sum(v >= 60 for v in components.values())
        bearish_evidence = sum(v <= 40 for v in components.values())
        direction = "BULLISH" if trend_direction >= 0 and bullish_evidence >= bearish_evidence else "BEARISH"

        if composite >= 82:
            state = "EARLY_BREAKOUT" if direction == "BULLISH" else "EARLY_BREAKDOWN"
            horizon = (1, 5)
        elif composite >= 70:
            state = "REVERSAL_SETUP" if abs(momentum_20) > 4 and acceleration * momentum_20 < 0 else "TREND_CONTINUATION"
            horizon = (3, 10)
        elif composite <= 38:
            state = "TREND_EXHAUSTION" if trend_direction else "LIQUIDITY_TRAP_RISK"
            horizon = (1, 7)
        else:
            state = "TRANSITION_WATCH"
            horizon = (5, 15)

        agreement = 1.0 - pstdev(list(components.values())) / 50.0
        confidence = clamp(composite * 0.65 + clamp(agreement * 100) * 0.35)
        evidence = [f"{k}:{v:.1f}" for k, v in sorted(components.items(), key=lambda kv: kv[1], reverse=True)[:4]]
        conflicts = [f"{k}:{v:.1f}" for k, v in components.items() if (direction == "BULLISH" and v < 45) or (direction == "BEARISH" and v > 55)]
        invalidation = {
            "price_below": round(recent_low, 4) if direction == "BULLISH" else None,
            "price_above": round(recent_high, 4) if direction == "BEARISH" else None,
            "confidence_below": 55.0,
        }
        raw = f"{symbol}|{timeframe}|{direction}|{state}|{composite:.6f}|{components}"
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "direction": direction,
            "transition_state": state,
            "inflection_score": round(composite, 4),
            "confidence": round(confidence, 4),
            "velocity": round(momentum_5, 4),
            "acceleration": round(acceleration, 4),
            "horizon_min_sessions": horizon[0],
            "horizon_max_sessions": horizon[1],
            "components": {k: round(v, 4) for k, v in components.items()},
            "evidence": evidence,
            "conflicting_evidence": conflicts,
            "invalidation": invalidation,
            "diagnostics": {
                "momentum_5": momentum_5,
                "momentum_20": momentum_20,
                "compression_ratio": compression_ratio,
                "volume_ratio": volume_ratio,
                "realized_volatility_20d": rv,
                "implied_volatility": iv,
                "breakout_proximity": breakout_proximity,
            },
            "state_hash": sha256(raw.encode()).hexdigest(),
        }
