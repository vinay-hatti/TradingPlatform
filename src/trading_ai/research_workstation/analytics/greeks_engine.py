from __future__ import annotations

from .greeks_profile import (
    GreeksExposureProfile,
    GreeksLegProfile,
)
from .payoff_profile import StrategyLegProfile


class GreeksAggregationEngine:
    @staticmethod
    def _sign(side: str) -> int:
        normalized = side.upper()
        if normalized in {"LONG", "BUY"}:
            return 1
        if normalized in {"SHORT", "SELL"}:
            return -1
        raise ValueError(f"Unsupported leg side: {side}")

    def aggregate(
        self,
        legs: tuple[StrategyLegProfile, ...],
    ) -> GreeksExposureProfile:
        leg_profiles = []
        total_delta = 0.0
        total_gamma = 0.0
        total_theta = 0.0
        total_vega = 0.0
        total_rho = 0.0

        for leg in legs:
            sign = self._sign(leg.side)
            scale = sign * leg.quantity * leg.multiplier

            delta_exposure = leg.delta * scale
            gamma_exposure = leg.gamma * scale
            theta_exposure = leg.theta * scale
            vega_exposure = leg.vega * scale
            rho_exposure = leg.rho * scale

            total_delta += delta_exposure
            total_gamma += gamma_exposure
            total_theta += theta_exposure
            total_vega += vega_exposure
            total_rho += rho_exposure

            leg_profiles.append(
                GreeksLegProfile(
                    symbol=leg.symbol,
                    option_type=leg.option_type.upper(),
                    side=leg.side.upper(),
                    quantity=leg.quantity,
                    multiplier=leg.multiplier,
                    strike=leg.strike,
                    expiration=leg.expiration,
                    delta=leg.delta,
                    gamma=leg.gamma,
                    theta=leg.theta,
                    vega=leg.vega,
                    rho=leg.rho,
                    delta_exposure=round(delta_exposure, 6),
                    gamma_exposure=round(gamma_exposure, 6),
                    theta_exposure=round(theta_exposure, 6),
                    vega_exposure=round(vega_exposure, 6),
                    rho_exposure=round(rho_exposure, 6),
                )
            )

        if total_delta > 20:
            delta_classification = "BULLISH"
        elif total_delta < -20:
            delta_classification = "BEARISH"
        else:
            delta_classification = "NEUTRAL"

        absolute_gamma = abs(total_gamma)
        gamma_risk = (
            "HIGH"
            if absolute_gamma >= 20
            else "MODERATE"
            if absolute_gamma >= 5
            else "LOW"
        )
        volatility_sensitivity = (
            "LONG_VOLATILITY"
            if total_vega > 5
            else "SHORT_VOLATILITY"
            if total_vega < -5
            else "NEUTRAL"
        )
        time_decay_sensitivity = (
            "POSITIVE_THETA"
            if total_theta > 1
            else "NEGATIVE_THETA"
            if total_theta < -1
            else "NEUTRAL"
        )

        return GreeksExposureProfile(
            total_delta=round(total_delta, 6),
            total_gamma=round(total_gamma, 6),
            total_theta=round(total_theta, 6),
            total_vega=round(total_vega, 6),
            total_rho=round(total_rho, 6),
            delta_classification=delta_classification,
            gamma_risk=gamma_risk,
            volatility_sensitivity=volatility_sensitivity,
            time_decay_sensitivity=time_decay_sensitivity,
            leg_count=len(legs),
            legs=tuple(leg_profiles),
        )
