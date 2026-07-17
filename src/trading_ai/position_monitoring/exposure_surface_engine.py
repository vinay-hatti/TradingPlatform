from __future__ import annotations

from collections import defaultdict

from .portfolio_greeks_policy import PortfolioGreeksMonitoringPolicy
from .portfolio_greeks_profile import (
    GreeksExposureSurfacePoint,
    RealTimePositionGreeks,
    UnderlyingGreeksExposure,
)


def _direction(side: str, quantity: float) -> float:
    if quantity < 0 or side.upper() == "SHORT":
        return -1.0
    return 1.0


class GreeksExposureSurfaceEngine:
    def __init__(
        self,
        policy: PortfolioGreeksMonitoringPolicy | None = None,
    ) -> None:
        self.policy = policy or PortfolioGreeksMonitoringPolicy()
        self.policy.validate()

    def build(
        self,
        greeks: tuple[RealTimePositionGreeks, ...],
    ) -> tuple[
        tuple[GreeksExposureSurfacePoint, ...],
        tuple[UnderlyingGreeksExposure, ...],
    ]:
        grouped: dict[str, list[RealTimePositionGreeks]] = defaultdict(list)
        for item in greeks:
            grouped[item.underlying_symbol].append(item)

        all_points = []
        underlying_exposures = []

        for symbol, items in sorted(grouped.items()):
            points = []
            for underlying_shock in self.policy.scenario_underlying_shocks_pct:
                for volatility_shock in self.policy.scenario_volatility_shocks:
                    for days in self.policy.scenario_time_decay_days:
                        delta_pnl = 0.0
                        gamma_pnl = 0.0
                        vega_pnl = 0.0
                        theta_pnl = 0.0

                        for item in items:
                            scale = (
                                _direction(item.side, item.quantity)
                                * abs(float(item.quantity))
                                * max(int(item.multiplier or 1), 1)
                            )
                            d_s = (
                                float(item.underlying_price)
                                * float(underlying_shock)
                            )
                            delta_pnl += scale * float(item.delta) * d_s
                            gamma_pnl += (
                                scale
                                * 0.5
                                * float(item.gamma)
                                * d_s
                                * d_s
                            )
                            vega_pnl += (
                                scale
                                * float(item.vega)
                                * float(volatility_shock)
                            )
                            theta_pnl += (
                                scale * float(item.theta) * float(days)
                            )

                        projected = (
                            delta_pnl
                            + gamma_pnl
                            + vega_pnl
                            + theta_pnl
                        )
                        surface_id = (
                            f"{symbol}|U{underlying_shock:+.4f}|"
                            f"V{volatility_shock:+.4f}|T{days}"
                        )
                        point = GreeksExposureSurfacePoint(
                            surface_id=surface_id,
                            underlying_symbol=symbol,
                            underlying_shock_pct=underlying_shock,
                            volatility_shock=volatility_shock,
                            time_decay_days=days,
                            projected_pnl=round(projected, 6),
                            projected_loss=round(max(0.0, -projected), 6),
                            delta_pnl=round(delta_pnl, 6),
                            gamma_pnl=round(gamma_pnl, 6),
                            vega_pnl=round(vega_pnl, 6),
                            theta_pnl=round(theta_pnl, 6),
                        )
                        points.append(point)
                        all_points.append(point)

                        if len(all_points) > self.policy.maximum_surface_points:
                            raise ValueError(
                                "Maximum exposure-surface point count exceeded"
                            )

            delta = gamma = vega = theta = rho = 0.0
            for item in items:
                scale = (
                    _direction(item.side, item.quantity)
                    * abs(float(item.quantity))
                    * max(int(item.multiplier or 1), 1)
                )
                delta += scale * item.delta
                gamma += scale * item.gamma
                vega += scale * item.vega
                theta += scale * item.theta
                rho += scale * item.rho

            underlying_exposures.append(
                UnderlyingGreeksExposure(
                    underlying_symbol=symbol,
                    delta=round(delta, 6),
                    gamma=round(gamma, 6),
                    vega=round(vega, 6),
                    theta=round(theta, 6),
                    rho=round(rho, 6),
                    scenario_loss=max(
                        (point.projected_loss for point in points),
                        default=0.0,
                    ),
                    surface_points=tuple(points),
                )
            )

        return tuple(all_points), tuple(underlying_exposures)
