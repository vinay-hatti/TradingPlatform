from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import date, datetime, timezone
from typing import Any, Iterable

from sqlalchemy import text

try:
    from trading_ai.database import SessionLocal
except ImportError:  # backward-compatible package layout
    from trading_ai.database.session import SessionLocal


@dataclass(frozen=True)
class TrendPlatformPolicy:
    maximum_age_days: int = 3
    forecast_horizon_days: int = 10
    scanner_adjustment_cap: float = 2.0
    decision_adjustment_cap: float = 2.0
    portfolio_risk_cap: float = 1.0


@dataclass(frozen=True)
class TrendPlatformContext:
    symbol: str
    status: str
    as_of_date: str | None
    snapshot_timestamp: str | None
    base: dict[str, Any]
    transition: dict[str, Any]
    forecast: dict[str, Any]
    institutional: dict[str, Any]
    scanner_adjustment: float
    decision_adjustment: float
    portfolio_risk_adjustment: float
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["warnings"] = list(self.warnings)
        return value


class TrendPlatformIntegrationService:
    """Single governed reader and scoring adapter for Milestone 52 snapshots."""

    def __init__(self, session_factory=SessionLocal, policy: TrendPlatformPolicy | None = None) -> None:
        self.session_factory = session_factory
        self.policy = policy or TrendPlatformPolicy()

    @staticmethod
    def _decode(value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        return json.loads(value)

    @staticmethod
    def _clip(value: float, cap: float) -> float:
        return round(max(-cap, min(cap, float(value))), 4)

    @staticmethod
    def _as_date(value: Any) -> date | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value)[:10])

    def _latest_payload(self, session, table: str, symbol: str, *, horizon_days: int | None = None) -> dict[str, Any]:
        horizon_clause = " AND horizon_days=:horizon_days" if horizon_days is not None else ""
        row = session.execute(
            text(
                f"""
                SELECT payload_json, as_of_date, snapshot_timestamp
                FROM {table}
                WHERE symbol=:symbol {horizon_clause}
                ORDER BY snapshot_timestamp DESC
                LIMIT 1
                """
            ),
            {"symbol": symbol, **({"horizon_days": horizon_days} if horizon_days is not None else {})},
        ).mappings().first()
        if not row:
            return {}
        payload = self._decode(row["payload_json"])
        payload.setdefault("as_of_date", row["as_of_date"].isoformat() if row["as_of_date"] else None)
        payload.setdefault("snapshot_timestamp", row["snapshot_timestamp"].isoformat() if row["snapshot_timestamp"] else None)
        return payload

    def context(self, symbol: str, reference_date: date | None = None) -> TrendPlatformContext:
        symbol = str(symbol).strip().upper()
        reference_date = reference_date or date.today()
        warnings: list[str] = []
        with self.session_factory() as session:
            base = self._latest_payload(session, "stock_trend_snapshot", symbol)
            transition = self._latest_payload(session, "stock_trend_transition_snapshot", symbol)
            forecast = self._latest_payload(
                session, "stock_trend_forecast_snapshot", symbol,
                horizon_days=self.policy.forecast_horizon_days,
            )
            institutional = self._latest_payload(session, "stock_institutional_trend_snapshot", symbol)

        payloads = {"base": base, "transition": transition, "forecast": forecast, "institutional": institutional}
        for name, payload in payloads.items():
            if not payload:
                warnings.append(f"MISSING_{name.upper()}_TREND_CONTEXT")
                continue
            as_of = self._as_date(payload.get("as_of_date"))
            if as_of is None or max(0, (reference_date - as_of).days) > self.policy.maximum_age_days:
                warnings.append(f"STALE_{name.upper()}_TREND_CONTEXT")

        base_adj = float(base.get("trend_score_adjustment", base.get("score_adjustment", 0.0)) or 0.0)
        transition_adj = float(transition.get("transition_score_adjustment", 0.0) or 0.0)
        forecast_adj = float(forecast.get("forecast_score_adjustment", 0.0) or 0.0)
        participation = float(institutional.get("participation_score", 50.0) or 50.0)
        leadership = float(institutional.get("leadership_score", 50.0) or 50.0)
        quality = float(institutional.get("trend_quality_score", 50.0) or 50.0)
        deterioration = float(institutional.get("deterioration_risk_score", 50.0) or 50.0)

        institutional_adj = ((participation - 50.0) + (leadership - 50.0) + (quality - 50.0) - (deterioration - 50.0)) / 100.0
        raw = base_adj * 0.30 + transition_adj * 0.20 + forecast_adj * 0.25 + institutional_adj * 0.25
        if warnings:
            raw *= 0.50

        scanner_adjustment = self._clip(raw, self.policy.scanner_adjustment_cap)
        decision_adjustment = self._clip(raw, self.policy.decision_adjustment_cap)
        portfolio_risk_adjustment = self._clip(-deterioration / 100.0 + quality / 100.0, self.policy.portfolio_risk_cap)

        dated = [p for p in payloads.values() if p.get("as_of_date")]
        as_of_date = min((str(p["as_of_date"])[:10] for p in dated), default=None)
        timestamps = [str(p.get("snapshot_timestamp")) for p in payloads.values() if p.get("snapshot_timestamp")]
        status = "READY" if not warnings else "DEGRADED"
        return TrendPlatformContext(
            symbol=symbol,
            status=status,
            as_of_date=as_of_date,
            snapshot_timestamp=min(timestamps) if timestamps else None,
            base=base,
            transition=transition,
            forecast=forecast,
            institutional=institutional,
            scanner_adjustment=scanner_adjustment,
            decision_adjustment=decision_adjustment,
            portfolio_risk_adjustment=portfolio_risk_adjustment,
            warnings=tuple(warnings),
        )

    def market_overview(self, symbols: Iterable[str], reference_date: date | None = None) -> dict[str, Any]:
        contexts = [self.context(symbol, reference_date=reference_date) for symbol in symbols]
        ready = [c for c in contexts if c.status == "READY"]
        bullish = sum(1 for c in contexts if c.scanner_adjustment > 0.25)
        bearish = sum(1 for c in contexts if c.scanner_adjustment < -0.25)
        neutral = len(contexts) - bullish - bearish
        values = lambda attr: [float(getattr(c, attr)) for c in contexts]
        avg = lambda xs: round(sum(xs) / len(xs), 4) if xs else 0.0
        transition_distribution: dict[str, int] = {}
        for context in contexts:
            state = str(context.transition.get("transition_state", "UNAVAILABLE"))
            transition_distribution[state] = transition_distribution.get(state, 0) + 1
        return {
            "status": "READY" if len(ready) == len(contexts) else "DEGRADED",
            "snapshot_timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol_count": len(contexts),
            "ready_symbol_count": len(ready),
            "bullish_trend_breadth_pct": round(100.0 * bullish / len(contexts), 2) if contexts else 0.0,
            "bearish_trend_breadth_pct": round(100.0 * bearish / len(contexts), 2) if contexts else 0.0,
            "neutral_trend_breadth_pct": round(100.0 * neutral / len(contexts), 2) if contexts else 0.0,
            "average_scanner_adjustment": avg(values("scanner_adjustment")),
            "average_decision_adjustment": avg(values("decision_adjustment")),
            "average_portfolio_risk_adjustment": avg(values("portfolio_risk_adjustment")),
            "transition_state_distribution": transition_distribution,
            "warnings": sorted({warning for context in contexts for warning in context.warnings}),
        }
