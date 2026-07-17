from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import uuid

from .portfolio_greeks_policy import PortfolioGreeksMonitoringPolicy
from .portfolio_greeks_profile import (
    PortfolioGreeksRiskState,
    RealTimePositionGreeks,
    UnderlyingGreeksExposure,
)


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _direction(side: str, quantity: float) -> float:
    if quantity < 0 or side.upper() == "SHORT":
        return -1.0
    return 1.0


class PortfolioGreeksEngine:
    def __init__(
        self,
        policy: PortfolioGreeksMonitoringPolicy | None = None,
    ) -> None:
        self.policy = policy or PortfolioGreeksMonitoringPolicy()
        self.policy.validate()

    def is_stale(
        self,
        profile: RealTimePositionGreeks,
        *,
        as_of: datetime,
    ) -> bool:
        age = (as_of - _parse_timestamp(profile.timestamp)).total_seconds()
        return age > self.policy.maximum_greeks_age_seconds

    def aggregate(
        self,
        *,
        account_id: str,
        snapshot_id: str | None,
        current_equity: float,
        greeks: tuple[RealTimePositionGreeks, ...],
        as_of: datetime | None = None,
        missing_greeks_count: int = 0,
    ) -> PortfolioGreeksRiskState:
        now = as_of or datetime.now(timezone.utc)
        totals = defaultdict(float)
        by_underlying = defaultdict(lambda: defaultdict(float))

        for item in greeks:
            scale = (
                _direction(item.side, item.quantity)
                * abs(float(item.quantity))
                * max(int(item.multiplier or 1), 1)
            )
            for name in ("delta", "gamma", "vega", "theta", "rho"):
                contribution = float(getattr(item, name)) * scale
                totals[name] += contribution
                by_underlying[item.underlying_symbol][name] += contribution

        exposures = tuple(
            UnderlyingGreeksExposure(
                underlying_symbol=symbol,
                delta=round(values["delta"], 6),
                gamma=round(values["gamma"], 6),
                vega=round(values["vega"], 6),
                theta=round(values["theta"], 6),
                rho=round(values["rho"], 6),
                scenario_loss=0.0,
            )
            for symbol, values in sorted(by_underlying.items())
        )

        stale_count = sum(
            self.is_stale(item, as_of=now) for item in greeks
        )
        return PortfolioGreeksRiskState(
            account_id=account_id,
            snapshot_id=snapshot_id or f"greeks-{uuid.uuid4().hex}",
            delta=round(totals["delta"], 6),
            gamma=round(totals["gamma"], 6),
            vega=round(totals["vega"], 6),
            theta=round(totals["theta"], 6),
            rho=round(totals["rho"], 6),
            worst_scenario_id=None,
            worst_scenario_loss=0.0,
            worst_scenario_loss_pct_of_equity=(
                0.0 if current_equity > 0 else None
            ),
            by_underlying=exposures,
            stale_greeks_count=stale_count,
            missing_greeks_count=missing_greeks_count,
            created_at=now.isoformat(),
        )
