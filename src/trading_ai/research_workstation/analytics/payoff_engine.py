from __future__ import annotations

from math import isfinite
from typing import Iterable

from .greeks_engine import GreeksAggregationEngine
from .payoff_profile import (
    PayoffAnalysisProfile,
    PayoffPointProfile,
    StrategyLegProfile,
)
from .risk_visualization_profile import (
    RiskClassificationProfile,
    VisualizationSeriesProfile,
)


class PayoffAnalysisEngine:
    def __init__(
        self,
        greeks_engine: GreeksAggregationEngine | None = None,
    ):
        self.greeks_engine = greeks_engine or GreeksAggregationEngine()

    @staticmethod
    def _sign(side: str) -> int:
        normalized = side.upper()
        if normalized in {"LONG", "BUY"}:
            return 1
        if normalized in {"SHORT", "SELL"}:
            return -1
        raise ValueError(f"Unsupported leg side: {side}")

    def _leg_payoff(
        self,
        leg: StrategyLegProfile,
        underlying_at_expiry: float,
    ) -> float:
        option_type = leg.option_type.upper()
        if option_type == "CALL":
            intrinsic = max(0.0, underlying_at_expiry - leg.strike)
        elif option_type == "PUT":
            intrinsic = max(0.0, leg.strike - underlying_at_expiry)
        else:
            raise ValueError(
                f"Unsupported option type: {leg.option_type}"
            )

        sign = self._sign(leg.side)
        return (
            sign
            * (intrinsic - leg.premium)
            * leg.quantity
            * leg.multiplier
        )

    def _portfolio_payoff(
        self,
        legs: tuple[StrategyLegProfile, ...],
        underlying_at_expiry: float,
    ) -> float:
        return sum(
            self._leg_payoff(leg, underlying_at_expiry)
            for leg in legs
        )

    @staticmethod
    def _breakevens(
        points: tuple[PayoffPointProfile, ...],
    ) -> tuple[float, ...]:
        breakevens: list[float] = []
        for left, right in zip(points, points[1:]):
            if left.profit_loss == 0:
                breakevens.append(left.underlying_price)
                continue
            if left.profit_loss * right.profit_loss < 0:
                x1, y1 = left.underlying_price, left.profit_loss
                x2, y2 = right.underlying_price, right.profit_loss
                crossing = x1 + (0 - y1) * (x2 - x1) / (y2 - y1)
                breakevens.append(round(crossing, 6))
        if points and points[-1].profit_loss == 0:
            breakevens.append(points[-1].underlying_price)

        deduped = []
        for value in breakevens:
            if not deduped or abs(value - deduped[-1]) > 1e-6:
                deduped.append(value)
        return tuple(deduped)

    @staticmethod
    def _risk_classification(
        greeks,
        maximum_loss: float | None,
        net_credit_debit: float,
        underlying_price: float,
        legs: tuple[StrategyLegProfile, ...],
    ) -> RiskClassificationProfile:
        short_leg_count = sum(
            1 for leg in legs if leg.side.upper() in {"SHORT", "SELL"}
        )
        naked_short = short_leg_count > 0 and len(legs) == 1

        assignment_risk = (
            "HIGH"
            if naked_short
            else "MODERATE"
            if short_leg_count > 0
            else "LOW"
        )

        if maximum_loss is None:
            capital_efficiency = "UNDEFINED"
        elif maximum_loss <= max(1.0, underlying_price * 25.0):
            capital_efficiency = "HIGH"
        else:
            capital_efficiency = "MODERATE"

        concentration_risk = (
            "HIGH"
            if abs(net_credit_debit) > underlying_price * 50.0
            else "MODERATE"
            if abs(net_credit_debit) > underlying_price * 20.0
            else "LOW"
        )

        return RiskClassificationProfile(
            directional_exposure=greeks.delta_classification,
            gamma_risk=greeks.gamma_risk,
            volatility_sensitivity=greeks.volatility_sensitivity,
            time_decay_sensitivity=greeks.time_decay_sensitivity,
            assignment_risk=assignment_risk,
            capital_efficiency=capital_efficiency,
            concentration_risk=concentration_risk,
        )

    def analyze(
        self,
        *,
        strategy_name: str,
        underlying_price: float,
        legs: Iterable[StrategyLegProfile],
        minimum_price: float | None = None,
        maximum_price: float | None = None,
        steps: int = 121,
        probability_weights: Iterable[float] | None = None,
    ) -> PayoffAnalysisProfile:
        normalized_legs = tuple(legs)
        if not normalized_legs:
            raise ValueError("At least one strategy leg is required.")
        if steps < 3:
            raise ValueError("Payoff analysis requires at least 3 points.")

        lower = (
            max(0.01, underlying_price * 0.5)
            if minimum_price is None
            else minimum_price
        )
        upper = (
            underlying_price * 1.5
            if maximum_price is None
            else maximum_price
        )
        if upper <= lower:
            raise ValueError("Maximum price must exceed minimum price.")

        increment = (upper - lower) / (steps - 1)
        payoff_points = tuple(
            PayoffPointProfile(
                underlying_price=round(lower + increment * index, 6),
                profit_loss=round(
                    self._portfolio_payoff(
                        normalized_legs,
                        lower + increment * index,
                    ),
                    6,
                ),
            )
            for index in range(steps)
        )

        observed_max = max(point.profit_loss for point in payoff_points)
        observed_min = min(point.profit_loss for point in payoff_points)

        left_slope = (
            payoff_points[1].profit_loss
            - payoff_points[0].profit_loss
        )
        right_slope = (
            payoff_points[-1].profit_loss
            - payoff_points[-2].profit_loss
        )

        maximum_profit = (
            None
            if right_slope > 0 or left_slope < 0
            else observed_max
        )
        maximum_loss = (
            None
            if right_slope < 0 or left_slope > 0
            else abs(observed_min)
        )

        net_credit_debit = round(
            sum(
                -self._sign(leg.side)
                * leg.premium
                * leg.quantity
                * leg.multiplier
                for leg in normalized_legs
            ),
            6,
        )

        breakevens = self._breakevens(payoff_points)
        if maximum_loss and maximum_loss > 0:
            return_on_risk = (
                (maximum_profit or observed_max) / maximum_loss
            )
            reward_risk_ratio = return_on_risk
        else:
            return_on_risk = 0.0
            reward_risk_ratio = 0.0

        if probability_weights is None:
            weights = [1.0 / len(payoff_points)] * len(payoff_points)
        else:
            weights = list(probability_weights)
            if len(weights) != len(payoff_points):
                raise ValueError(
                    "Probability weights must match payoff points."
                )
            total_weight = sum(weights)
            if total_weight <= 0:
                raise ValueError(
                    "Probability weights must have positive total."
                )
            weights = [weight / total_weight for weight in weights]

        probability_adjusted = sum(
            point.profit_loss * weight
            for point, weight in zip(payoff_points, weights)
        )
        risk_denominator = maximum_loss or max(
            1.0,
            abs(observed_min),
        )
        risk_adjusted_return = probability_adjusted / risk_denominator

        greeks = self.greeks_engine.aggregate(normalized_legs)
        risk = self._risk_classification(
            greeks,
            maximum_loss,
            net_credit_debit,
            underlying_price,
            normalized_legs,
        )

        price_pnl_series = VisualizationSeriesProfile(
            name="price_to_profit_loss",
            x_label="Underlying Price",
            y_label="Profit / Loss",
            points=tuple(
                (
                    point.underlying_price,
                    point.profit_loss,
                )
                for point in payoff_points
            ),
        )

        delta_series = VisualizationSeriesProfile(
            name="underlying_to_delta",
            x_label="Underlying Price",
            y_label="Delta Exposure",
            points=tuple(
                (
                    point.underlying_price,
                    greeks.total_delta,
                )
                for point in payoff_points
            ),
        )
        gamma_series = VisualizationSeriesProfile(
            name="underlying_to_gamma",
            x_label="Underlying Price",
            y_label="Gamma Exposure",
            points=tuple(
                (
                    point.underlying_price,
                    greeks.total_gamma,
                )
                for point in payoff_points
            ),
        )
        theta_series = VisualizationSeriesProfile(
            name="underlying_to_theta",
            x_label="Underlying Price",
            y_label="Theta Exposure",
            points=tuple(
                (
                    point.underlying_price,
                    greeks.total_theta,
                )
                for point in payoff_points
            ),
        )
        vega_series = VisualizationSeriesProfile(
            name="underlying_to_vega",
            x_label="Underlying Price",
            y_label="Vega Exposure",
            points=tuple(
                (
                    point.underlying_price,
                    greeks.total_vega,
                )
                for point in payoff_points
            ),
        )

        warnings = []
        if maximum_profit is None:
            warnings.append("Maximum profit is theoretically unbounded")
        if maximum_loss is None:
            warnings.append("Maximum loss is theoretically unbounded")
        if not all(
            isfinite(point.profit_loss) for point in payoff_points
        ):
            warnings.append("Non-finite payoff values detected")
        if risk.assignment_risk == "HIGH":
            warnings.append("Naked short option assignment risk is high")

        return PayoffAnalysisProfile(
            strategy_name=strategy_name,
            underlying_price=underlying_price,
            net_credit_debit=net_credit_debit,
            maximum_profit=(
                None
                if maximum_profit is None
                else round(maximum_profit, 6)
            ),
            maximum_loss=(
                None
                if maximum_loss is None
                else round(maximum_loss, 6)
            ),
            breakeven_points=breakevens,
            return_on_risk=round(return_on_risk, 6),
            reward_risk_ratio=round(reward_risk_ratio, 6),
            probability_adjusted_expected_payoff=round(
                probability_adjusted,
                6,
            ),
            risk_adjusted_expected_return=round(
                risk_adjusted_return,
                6,
            ),
            payoff_points=payoff_points,
            greeks=greeks,
            risk_classification=risk,
            visualization_series=(
                price_pnl_series,
                delta_series,
                gamma_series,
                theta_series,
                vega_series,
            ),
            warnings=tuple(warnings),
            metadata={
                "source": "M34_PHASE2_STEP3_PAYOFF_ANALYTICS",
                "point_count": len(payoff_points),
            },
        )
