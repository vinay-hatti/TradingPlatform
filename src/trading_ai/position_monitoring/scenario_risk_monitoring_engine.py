from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from .exposure_surface_engine import GreeksExposureSurfaceEngine
from .portfolio_greeks_engine import PortfolioGreeksEngine
from .portfolio_greeks_policy import PortfolioGreeksMonitoringPolicy
from .portfolio_greeks_profile import (
    PortfolioGreeksCheck,
    PortfolioGreeksDecision,
    RealTimePositionGreeks,
)


class ScenarioRiskMonitoringEngine:
    def __init__(
        self,
        policy: PortfolioGreeksMonitoringPolicy | None = None,
    ) -> None:
        self.policy = policy or PortfolioGreeksMonitoringPolicy()
        self.policy.validate()
        self.greeks_engine = PortfolioGreeksEngine(self.policy)
        self.surface_engine = GreeksExposureSurfaceEngine(self.policy)

    @staticmethod
    def _grade(score: float) -> tuple[str, str]:
        if score >= 95:
            return "A", "LOW"
        if score >= 85:
            return "B", "MODERATE"
        if score >= 70:
            return "C", "SEVERE"
        return "F", "CRITICAL"

    def evaluate(
        self,
        *,
        account_id: str,
        snapshot_id: str | None,
        current_equity: float,
        option_position_ids: tuple[str, ...],
        greeks: tuple[RealTimePositionGreeks, ...],
        as_of: datetime | None = None,
    ) -> PortfolioGreeksDecision:
        now = as_of or datetime.now(timezone.utc)
        checks: list[PortfolioGreeksCheck] = []

        def add(
            name: str,
            passed: bool,
            message: str,
            *,
            required: bool = True,
            metadata: dict[str, Any] | None = None,
        ) -> None:
            checks.append(
                PortfolioGreeksCheck(
                    name=name,
                    passed=bool(passed),
                    required=required,
                    score=100.0 if passed else 0.0,
                    severity="LOW" if passed else "CRITICAL",
                    message=message,
                    metadata=metadata or {},
                )
            )

        greek_ids = {item.position_id for item in greeks}
        missing_ids = tuple(
            item for item in option_position_ids if item not in greek_ids
        )
        add(
            "greeks_coverage",
            not missing_ids
            or not self.policy.require_greeks_for_option_positions,
            "All option positions have real-time Greeks.",
            required=self.policy.require_greeks_for_option_positions,
            metadata={"missing_position_ids": missing_ids},
        )

        stale_ids = tuple(
            item.position_id
            for item in greeks
            if self.greeks_engine.is_stale(item, as_of=now)
        )
        add(
            "greeks_freshness",
            not stale_ids or not self.policy.reject_stale_greeks,
            "All position Greeks are fresh.",
            required=self.policy.reject_stale_greeks,
            metadata={"stale_position_ids": stale_ids},
        )

        missing_prices = tuple(
            item.position_id
            for item in greeks
            if item.underlying_price <= 0
        )
        add(
            "underlying_prices",
            not missing_prices or not self.policy.require_underlying_prices,
            "All Greek profiles have valid underlying prices.",
            required=self.policy.require_underlying_prices,
            metadata={"missing_price_position_ids": missing_prices},
        )

        required = [check for check in checks if check.required]
        initial_failed = [check for check in required if not check.passed]
        state = None

        if not initial_failed or not self.policy.fail_closed:
            state = self.greeks_engine.aggregate(
                account_id=account_id,
                snapshot_id=snapshot_id,
                current_equity=current_equity,
                greeks=greeks,
                as_of=now,
                missing_greeks_count=len(missing_ids),
            )
            surface_points, by_underlying = self.surface_engine.build(greeks)
            worst = max(
                surface_points,
                key=lambda point: point.projected_loss,
                default=None,
            )
            worst_loss = worst.projected_loss if worst else 0.0
            worst_pct = (
                worst_loss / current_equity
                if current_equity > 0
                else None
            )
            state = replace(
                state,
                worst_scenario_id=worst.surface_id if worst else None,
                worst_scenario_loss=round(worst_loss, 6),
                worst_scenario_loss_pct_of_equity=worst_pct,
                by_underlying=by_underlying,
                surface_points=surface_points,
            )

            add(
                "absolute_delta",
                abs(state.delta) <= self.policy.maximum_absolute_delta,
                "Portfolio absolute delta is within policy.",
            )
            add(
                "absolute_gamma",
                abs(state.gamma) <= self.policy.maximum_absolute_gamma,
                "Portfolio absolute gamma is within policy.",
            )
            add(
                "absolute_vega",
                abs(state.vega) <= self.policy.maximum_absolute_vega,
                "Portfolio absolute vega is within policy.",
            )
            add(
                "absolute_theta",
                abs(state.theta) <= self.policy.maximum_absolute_theta,
                "Portfolio absolute theta is within policy.",
            )
            add(
                "absolute_rho",
                abs(state.rho) <= self.policy.maximum_absolute_rho,
                "Portfolio absolute rho is within policy.",
            )
            add(
                "maximum_scenario_loss",
                worst_loss <= self.policy.maximum_scenario_loss,
                "Worst portfolio scenario loss is within policy.",
            )
            add(
                "scenario_loss_pct_equity",
                worst_pct is not None
                and worst_pct
                <= self.policy.maximum_scenario_loss_pct_of_equity,
                "Worst scenario loss percentage is within policy.",
            )

            for exposure in by_underlying:
                add(
                    f"underlying_delta:{exposure.underlying_symbol}",
                    abs(exposure.delta)
                    <= self.policy.maximum_underlying_delta,
                    "Underlying delta is within policy.",
                )
                add(
                    f"underlying_gamma:{exposure.underlying_symbol}",
                    abs(exposure.gamma)
                    <= self.policy.maximum_underlying_gamma,
                    "Underlying gamma is within policy.",
                )
                add(
                    f"underlying_vega:{exposure.underlying_symbol}",
                    abs(exposure.vega)
                    <= self.policy.maximum_underlying_vega,
                    "Underlying vega is within policy.",
                )
                add(
                    f"underlying_scenario_loss:{exposure.underlying_symbol}",
                    exposure.scenario_loss
                    <= self.policy.maximum_underlying_scenario_loss,
                    "Underlying scenario loss is within policy.",
                )

        required = [check for check in checks if check.required]
        failed = [check for check in required if not check.passed]
        score = (
            sum(check.score for check in required) / len(required)
            if required
            else 100.0
        )
        allowed = (
            not failed
            and score >= self.policy.minimum_monitoring_score
            and state is not None
        )
        if not self.policy.fail_closed:
            allowed = (
                score >= self.policy.minimum_monitoring_score
                and state is not None
            )

        grade, severity = self._grade(score)
        return PortfolioGreeksDecision(
            valid=True,
            allowed=allowed,
            account_id=account_id,
            snapshot_id=(
                state.snapshot_id
                if state is not None
                else snapshot_id or "UNAVAILABLE"
            ),
            score=round(score, 2),
            grade=grade,
            severity=severity,
            recommendation="PUBLISH" if allowed else "BREACH",
            risk_state=state,
            checks=tuple(checks),
            warnings=tuple(
                f"STALE_GREEKS:{position_id}"
                for position_id in stale_ids
            ),
            rejection_reasons=tuple(
                check.name.upper() for check in failed
            ),
            metadata={
                "missing_position_ids": missing_ids,
                "stale_position_ids": stale_ids,
                "missing_price_position_ids": missing_prices,
            },
        )
