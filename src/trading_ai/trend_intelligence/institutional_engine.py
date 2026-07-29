from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .institutional_contracts import InstitutionalTrendSnapshot
from .institutional_policy import InstitutionalTrendPolicy


def _clip(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return float(np.clip(float(value), low, high))


def _safe(value: float, default: float = 0.0) -> float:
    return float(value) if np.isfinite(value) else float(default)


class InstitutionalTrendEngine:
    """Database-input institutional participation and leadership analytics.

    The engine intentionally uses price and volume proxies. It does not claim to
    identify actual beneficial owners or private institutional order flow.
    """

    def __init__(self, policy: InstitutionalTrendPolicy | None = None) -> None:
        self.policy = policy or InstitutionalTrendPolicy()

    def calculate(
        self,
        symbol: str,
        prices: pd.DataFrame,
        benchmark: pd.DataFrame | None = None,
        breadth_confirmation_score: float = 50.0,
        cross_asset_confirmation_score: float = 50.0,
    ) -> InstitutionalTrendSnapshot:
        frame = prices.copy()
        frame.columns = [str(c).lower() for c in frame.columns]
        required = {"close", "volume"}
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(f"Missing required price columns: {sorted(missing)}")
        frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
        frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")
        frame = frame.dropna(subset=["close", "volume"]).sort_index()
        if len(frame) < self.policy.minimum_history_rows:
            raise ValueError(
                f"Institutional trend analysis requires {self.policy.minimum_history_rows} rows; received {len(frame)}."
            )

        close = frame["close"].astype(float)
        volume = frame["volume"].astype(float).clip(lower=0.0)
        ret = close.pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
        dollar_volume = close * volume

        vol_mean20 = volume.rolling(self.policy.volume_window).mean()
        rvol = _safe(volume.iloc[-1] / max(_safe(vol_mean20.iloc[-1]), 1.0), 1.0)
        volume_slope = _safe(
            volume.tail(20).mean() / max(volume.tail(60).mean(), 1.0) - 1.0
        )
        volume_trend_score = _clip(50.0 + 140.0 * volume_slope)

        positive_volume = _safe(volume[ret > 0].tail(20).mean(), 0.0)
        negative_volume = _safe(volume[ret < 0].tail(20).mean(), 0.0)
        directional_volume_ratio = (positive_volume + 1.0) / (negative_volume + 1.0)
        accumulation_score = _clip(50.0 + 35.0 * np.log(directional_volume_ratio))

        signed_flow = np.sign(ret) * dollar_volume
        flow20 = _safe(signed_flow.tail(20).sum())
        gross20 = max(_safe(dollar_volume.tail(20).sum()), 1.0)
        flow_pressure = flow20 / gross20
        price_volume_confirmation = _clip(50.0 + 180.0 * flow_pressure)

        volume_thrust = _clip(50.0 + 35.0 * (rvol - 1.0) + 100.0 * _safe(ret.tail(5).sum()))
        distribution_risk = _clip(
            50.0
            + 180.0 * max(0.0, -flow_pressure)
            + 20.0 * max(0.0, rvol - 1.25) * float(ret.iloc[-1] < 0)
        )

        return20 = _safe(close.iloc[-1] / close.iloc[-21] - 1.0)
        return60 = _safe(close.iloc[-1] / close.iloc[-61] - 1.0)
        benchmark20 = 0.0
        benchmark60 = 0.0
        warnings: list[str] = []
        if benchmark is not None and not benchmark.empty:
            b = benchmark.copy()
            b.columns = [str(c).lower() for c in b.columns]
            b["close"] = pd.to_numeric(b["close"], errors="coerce")
            b = b.dropna(subset=["close"]).sort_index()
            if len(b) >= 61:
                benchmark20 = _safe(b["close"].iloc[-1] / b["close"].iloc[-21] - 1.0)
                benchmark60 = _safe(b["close"].iloc[-1] / b["close"].iloc[-61] - 1.0)
            else:
                warnings.append("BENCHMARK_HISTORY_INSUFFICIENT")
        else:
            warnings.append("BENCHMARK_UNAVAILABLE")

        rel20 = 100.0 * (return20 - benchmark20)
        rel60 = 100.0 * (return60 - benchmark60)
        leadership_score = _clip(50.0 + 3.0 * rel20 + 1.2 * rel60)

        rolling_rel = close.pct_change(20)
        if benchmark is not None and not benchmark.empty and len(benchmark) >= 21:
            bclose = pd.to_numeric(benchmark["close"], errors="coerce")
            aligned = pd.concat([rolling_rel.rename("s"), bclose.pct_change(20).rename("b")], axis=1).dropna()
            persistence = float((aligned.tail(self.policy.persistence_window)["s"] > aligned.tail(self.policy.persistence_window)["b"]).mean()) if not aligned.empty else 0.5
        else:
            persistence = float((rolling_rel.tail(self.policy.persistence_window) > 0).mean())
        leadership_persistence = _clip(100.0 * persistence)

        participation_score = _clip(
            0.24 * volume_trend_score
            + 0.22 * volume_thrust
            + 0.28 * price_volume_confirmation
            + 0.26 * accumulation_score
        )
        participation_confidence = _clip(
            45.0 + min(30.0, len(frame) / 10.0) + min(25.0, abs(participation_score - 50.0) * 0.5)
        )
        conviction = _clip(
            0.45 * participation_score
            + 0.35 * leadership_score
            + 0.20 * leadership_persistence
            - 0.25 * max(0.0, distribution_risk - 50.0)
        )

        breadth = _clip(breadth_confirmation_score)
        cross_asset = _clip(cross_asset_confirmation_score)
        trend_quality = _clip(
            0.30 * participation_score
            + 0.25 * leadership_score
            + 0.15 * leadership_persistence
            + 0.15 * breadth
            + 0.15 * cross_asset
            - 0.20 * max(0.0, distribution_risk - 50.0)
        )

        recent_quality = _clip(
            0.45 * price_volume_confirmation + 0.30 * volume_trend_score + 0.25 * leadership_score
        )
        earlier_ret = _safe(close.iloc[-21] / close.iloc[-41] - 1.0)
        momentum_decay = max(0.0, earlier_ret - return20)
        deterioration = _clip(
            distribution_risk * 0.45
            + (100.0 - recent_quality) * 0.35
            + min(20.0, momentum_decay * 200.0)
        )

        participation_state = "ACCUMULATION" if participation_score >= 65 else "DISTRIBUTION" if participation_score <= 35 else "MIXED"
        leadership_state = "LEADER" if leadership_score >= 65 else "LAGGARD" if leadership_score <= 35 else "NEUTRAL"
        deterioration_state = "HIGH_RISK" if deterioration >= 70 else "WATCH" if deterioration >= 55 else "STABLE"

        as_of = frame.index[-1]
        as_of_date = pd.Timestamp(as_of).date().isoformat()
        return InstitutionalTrendSnapshot(
            symbol=str(symbol).upper(),
            as_of_date=as_of_date,
            snapshot_timestamp=datetime.now(timezone.utc),
            participation_score=round(participation_score, 4),
            participation_grade=self.policy.grade(participation_score),
            participation_confidence=round(participation_confidence, 4),
            institutional_conviction_score=round(conviction, 4),
            relative_volume_20d=round(rvol, 6),
            volume_trend_score=round(volume_trend_score, 4),
            volume_thrust_score=round(volume_thrust, 4),
            price_volume_confirmation_score=round(price_volume_confirmation, 4),
            accumulation_distribution_score=round(accumulation_score, 4),
            distribution_risk_score=round(distribution_risk, 4),
            leadership_score=round(leadership_score, 4),
            leadership_grade=self.policy.grade(leadership_score),
            market_relative_strength_20d=round(rel20, 6),
            market_relative_strength_60d=round(rel60, 6),
            leadership_persistence_score=round(leadership_persistence, 4),
            breadth_confirmation_score=round(breadth, 4),
            cross_asset_confirmation_score=round(cross_asset, 4),
            trend_quality_score=round(trend_quality, 4),
            deterioration_risk_score=round(deterioration, 4),
            participation_state=participation_state,
            leadership_state=leadership_state,
            deterioration_state=deterioration_state,
            warnings=warnings,
            metadata={
                "history_rows": int(len(frame)),
                "benchmark_symbol": "SPY",
                "analytics_basis": "persisted_ohlcv_proxy",
                "institutional_identity_claimed": False,
            },
        )
