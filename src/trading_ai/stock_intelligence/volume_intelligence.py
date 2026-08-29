from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from statistics import mean, pstdev
from typing import Any

from .multi_timeframe import _rows


@dataclass
class InstitutionalVolumeProfile:
    regime: str = "UNAVAILABLE"
    signal: str = "UNAVAILABLE"
    institutional_participation_score: float = 50.0
    accumulation_score: float = 50.0
    distribution_score: float = 50.0
    absorption_score: float = 0.0
    breakout_confirmation_score: float = 0.0
    breakdown_confirmation_score: float = 0.0
    dry_up_score: float = 0.0
    persistence_score: float = 0.0
    relative_volume_1d: float = 0.0
    relative_volume_5d: float = 0.0
    relative_volume_20d: float = 0.0
    volume_zscore_20d: float = 0.0
    volume_percentile_60d: float = 0.0
    up_down_volume_ratio_20d: float = 1.0
    close_location_value: float = 0.0
    evidence: dict[str, Any] = field(default_factory=dict)


def _clip(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def _safe_mean(values: list[float]) -> float:
    return mean(values) if values else 0.0


class InstitutionalVolumeIntelligenceEngine:
    """Price/volume interpretation for institutional participation and breakout quality.

    The engine deliberately uses only persisted OHLCV bars so it is deterministic during
    Stock Intelligence publication. Live execution remains the responsibility of Polygon
    preflight and is not mixed into this generation-time model.
    """

    VERSION = "M76-INSTITUTIONAL-VOLUME-1.0"

    def analyze(self, data, *, breakout_state: str = "NONE", structure: str = "SIDEWAYS") -> InstitutionalVolumeProfile:
        rows = _rows(data)
        if len(rows) < 20:
            return InstitutionalVolumeProfile(evidence={"warning": "insufficient history", "version": self.VERSION})

        rows = rows[-250:]
        volumes = [max(0.0, float(row.get("volume", 0) or 0)) for row in rows]
        closes = [float(row["close"]) for row in rows]
        highs = [float(row["high"]) for row in rows]
        lows = [float(row["low"]) for row in rows]
        opens = [float(row.get("open", row["close"])) for row in rows]

        avg20 = _safe_mean(volumes[-21:-1]) or _safe_mean(volumes[-20:])
        avg60 = _safe_mean(volumes[-61:-1]) or avg20
        avg5 = _safe_mean(volumes[-5:])
        rv1 = volumes[-1] / avg20 if avg20 else 0.0
        rv5 = avg5 / avg20 if avg20 else 0.0
        rv20 = _safe_mean(volumes[-20:]) / avg60 if avg60 else 0.0

        hist20 = volumes[-21:-1] if len(volumes) >= 21 else volumes[-20:]
        sd20 = pstdev(hist20) if len(hist20) > 1 else 0.0
        z20 = (volumes[-1] - _safe_mean(hist20)) / sd20 if sd20 > 0 else 0.0
        hist60 = volumes[-60:]
        percentile60 = 100.0 * sum(v <= volumes[-1] for v in hist60) / max(1, len(hist60))

        up_volume = down_volume = 0.0
        signed_flow = 0.0
        for idx in range(max(1, len(rows) - 20), len(rows)):
            v = volumes[idx]
            if closes[idx] > closes[idx - 1]:
                up_volume += v
                signed_flow += v
            elif closes[idx] < closes[idx - 1]:
                down_volume += v
                signed_flow -= v
        up_down_ratio = up_volume / max(1.0, down_volume)
        signed_flow_norm = signed_flow / max(1.0, up_volume + down_volume)

        money_flow = []
        for h, l, c, v in zip(highs[-20:], lows[-20:], closes[-20:], volumes[-20:]):
            multiplier = ((2.0 * c - h - l) / (h - l)) if h != l else 0.0
            money_flow.append(multiplier * v)
        cmf20 = sum(money_flow) / max(1.0, sum(volumes[-20:]))

        range_now = max(1e-9, highs[-1] - lows[-1])
        clv = ((closes[-1] - lows[-1]) - (highs[-1] - closes[-1])) / range_now
        median_range = sorted(max(1e-9, h - l) for h, l in zip(highs[-20:], lows[-20:]))[len(highs[-20:]) // 2]
        range_ratio = range_now / max(1e-9, median_range)
        price_change = (closes[-1] / closes[-2] - 1.0) if len(closes) > 1 and closes[-2] else 0.0
        price_return20 = closes[-1] / closes[-20] - 1.0 if closes[-20] else 0.0

        # Persistent elevated volume matters more than a single isolated spike.
        elevated_count10 = sum(1 for v in volumes[-10:] if avg20 and v >= avg20 * 1.25)
        persistence = _clip(elevated_count10 * 10.0 + max(0.0, rv20 - 1.0) * 35.0)

        # Volume dry-up is constructive during compression / accumulation and can precede expansion.
        dry_ratio = avg5 / avg20 if avg20 else 1.0
        dry_up = _clip((1.0 - dry_ratio) * 160.0) if dry_ratio < 1.0 else 0.0
        if structure not in {"SIDEWAYS", "COMPRESSION", "EARLY_TREND", "MATURE_TREND"}:
            dry_up *= 0.65

        flow_score = _clip(50.0 + signed_flow_norm * 45.0 + cmf20 * 55.0)
        accumulation = _clip(flow_score + max(0.0, price_return20) * 120.0 + persistence * 0.18)
        distribution = _clip((100.0 - flow_score) + max(0.0, -price_return20) * 120.0 + persistence * 0.18)

        # High volume with relatively constrained range and directional close suggests absorption.
        absorption = 0.0
        absorption_side = "NONE"
        if rv1 >= 1.5 and range_ratio <= 1.05:
            absorption = _clip(45.0 + (rv1 - 1.5) * 22.0 + abs(clv) * 28.0)
            absorption_side = "BUYING" if clv >= 0.25 else "SELLING" if clv <= -0.25 else "BALANCED"
            if absorption_side == "BUYING":
                accumulation = _clip(accumulation + absorption * 0.20)
            elif absorption_side == "SELLING":
                distribution = _clip(distribution + absorption * 0.20)

        breakout_confirm = 0.0
        breakdown_confirm = 0.0
        if "BREAKOUT" in str(breakout_state):
            breakout_confirm = _clip(35.0 + max(0.0, rv1 - 0.8) * 30.0 + max(0.0, clv) * 20.0 + persistence * 0.20)
        if "BREAKDOWN" in str(breakout_state):
            breakdown_confirm = _clip(35.0 + max(0.0, rv1 - 0.8) * 30.0 + max(0.0, -clv) * 20.0 + persistence * 0.20)

        participation = _clip(
            0.32 * max(accumulation, distribution)
            + 0.24 * _clip(50.0 + (rv1 - 1.0) * 35.0)
            + 0.20 * persistence
            + 0.14 * max(breakout_confirm, breakdown_confirm)
            + 0.10 * absorption
        )

        climactic = rv1 >= 2.5 and percentile60 >= 90.0
        if climactic:
            regime = "CLIMACTIC"
        elif persistence >= 70 and max(accumulation, distribution) >= 65:
            regime = "PERSISTENT_ACCUMULATION" if accumulation >= distribution else "PERSISTENT_DISTRIBUTION"
        elif rv1 >= 1.5:
            regime = "EXPANSION"
        elif dry_up >= 60:
            regime = "DRY_UP"
        elif rv1 <= 0.75:
            regime = "QUIET"
        else:
            regime = "NORMAL"

        if breakout_confirm >= 70:
            signal = "BREAKOUT_EXPANSION"
        elif breakdown_confirm >= 70:
            signal = "BREAKDOWN_EXPANSION"
        elif absorption >= 65 and absorption_side == "BUYING":
            signal = "BUYING_ABSORPTION"
        elif absorption >= 65 and absorption_side == "SELLING":
            signal = "SELLING_ABSORPTION"
        elif accumulation >= 68 and accumulation >= distribution + 8:
            signal = "ACCUMULATION_CONFIRMED"
        elif distribution >= 68 and distribution >= accumulation + 8:
            signal = "DISTRIBUTION_CONFIRMED"
        elif dry_up >= 60:
            signal = "VOLUME_DRY_UP"
        else:
            signal = "NEUTRAL"

        return InstitutionalVolumeProfile(
            regime=regime,
            signal=signal,
            institutional_participation_score=round(participation, 2),
            accumulation_score=round(accumulation, 2),
            distribution_score=round(distribution, 2),
            absorption_score=round(absorption, 2),
            breakout_confirmation_score=round(breakout_confirm, 2),
            breakdown_confirmation_score=round(breakdown_confirm, 2),
            dry_up_score=round(dry_up, 2),
            persistence_score=round(persistence, 2),
            relative_volume_1d=round(rv1, 3),
            relative_volume_5d=round(rv5, 3),
            relative_volume_20d=round(rv20, 3),
            volume_zscore_20d=round(z20, 3),
            volume_percentile_60d=round(percentile60, 2),
            up_down_volume_ratio_20d=round(up_down_ratio, 3),
            close_location_value=round(clv, 3),
            evidence={
                "version": self.VERSION,
                "average_volume_20d": round(avg20, 2),
                "average_volume_60d": round(avg60, 2),
                "volume_1d": round(volumes[-1], 2),
                "elevated_volume_sessions_10d": elevated_count10,
                "dry_up_ratio_5d_vs_20d": round(dry_ratio, 4),
                "cmf_20d": round(cmf20, 4),
                "signed_volume_flow_20d": round(signed_flow_norm, 4),
                "price_return_20d": round(price_return20, 4),
                "price_change_1d": round(price_change, 4),
                "range_ratio_vs_20d_median": round(range_ratio, 4),
                "absorption_side": absorption_side,
                "climactic_volume": climactic,
            },
        )
