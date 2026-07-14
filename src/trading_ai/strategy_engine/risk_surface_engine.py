import math

from trading_ai.strategy_engine.delta_gamma_engine import DeltaGammaEngine
from trading_ai.strategy_engine.risk_attribution_engine import RiskAttributionEngine
from trading_ai.strategy_engine.risk_surface_policy import RiskSurfacePolicy
from trading_ai.strategy_engine.risk_surface_profile import (
    RiskSurfacePoint,
    RiskSurfaceProfile,
)


class RiskSurfaceEngine:
    """Build institutional price/IV/time sensitivity surfaces."""

    def __init__(self, policy=None, approximation_engine=None, attribution_engine=None):
        self.policy = policy or RiskSurfacePolicy()
        self.policy.validate()
        self.approximation_engine = approximation_engine or DeltaGammaEngine()
        self.attribution_engine = attribution_engine or RiskAttributionEngine()

    def analyze(
        self,
        symbol,
        strategy,
        underlying_price,
        implied_volatility,
        days_to_expiration,
        capital_required,
        initial_capital,
        net_delta,
        net_gamma,
        net_vega,
        net_theta,
        net_rho=0.0,
        contract_multiplier=100.0,
    ):
        underlying_price = float(underlying_price)
        implied_volatility = float(implied_volatility)
        capital_required = max(float(capital_required), 0.0)
        initial_capital = max(float(initial_capital), 0.0)

        if underlying_price <= 0.0 or initial_capital <= 0.0:
            return self._invalid(symbol, strategy, underlying_price, implied_volatility,
                                 days_to_expiration, capital_required, initial_capital,
                                 net_delta, net_gamma, net_vega, net_theta, net_rho)

        points = []
        for price_shock in self.policy.price_shocks_pct:
            for vol_shock in self.policy.volatility_shocks:
                for time_offset in self.policy.time_offsets_days:
                    effective_time = min(int(time_offset), max(int(days_to_expiration), 0))
                    result = self.approximation_engine.approximate(
                        underlying_price=underlying_price,
                        price_shock_pct=price_shock,
                        volatility_shock=vol_shock,
                        time_offset_days=effective_time,
                        net_delta=net_delta,
                        net_gamma=net_gamma,
                        net_vega=net_vega,
                        net_theta=net_theta,
                        net_rho=net_rho if self.policy.include_rho else 0.0,
                        contract_multiplier=contract_multiplier,
                    )
                    points.append(RiskSurfacePoint(
                        price_shock_pct=float(price_shock),
                        volatility_shock=float(vol_shock),
                        time_offset_days=effective_time,
                        shocked_underlying_price=underlying_price * (1.0 + price_shock),
                        shocked_implied_volatility=max(0.0, implied_volatility + vol_shock),
                        **result,
                    ))

        worst = min(points, key=lambda point: point.approximated_pnl)
        best = max(points, key=lambda point: point.approximated_pnl)
        base_candidates = [
            point for point in points
            if point.price_shock_pct == 0.0
            and point.volatility_shock == 0.0
            and point.time_offset_days == 0
        ]
        base = base_candidates[0] if base_candidates else points[0]

        max_loss_pct = abs(min(worst.approximated_pnl, 0.0)) / initial_capital
        max_gain_pct = max(best.approximated_pnl, 0.0) / initial_capital
        gamma_loss = max(
            (abs(min(point.gamma_component, 0.0)) for point in points), default=0.0
        ) / initial_capital
        vega_loss = max(
            (abs(min(point.vega_component, 0.0)) for point in points), default=0.0
        ) / initial_capital
        theta_loss = max(
            (abs(min(point.theta_component, 0.0)) for point in points), default=0.0
        ) / initial_capital

        gamma_score = self._factor_score(gamma_loss, self.policy.maximum_gamma_loss_pct_of_capital)
        vega_score = self._factor_score(vega_loss, self.policy.maximum_vega_loss_pct_of_capital)
        theta_score = self._factor_score(theta_loss, self.policy.maximum_theta_loss_pct_of_capital)
        nonlinear_score = self._nonlinear_score(points)
        surface_score = max(0.0, min(100.0,
            0.40 * self._factor_score(max_loss_pct, self.policy.maximum_loss_pct_of_capital)
            + 0.20 * gamma_score
            + 0.15 * vega_score
            + 0.10 * theta_score
            + 0.15 * nonlinear_score
        ))

        severity = self._severity(max_loss_pct)
        grade = self._grade(surface_score)
        rejections = []
        warnings = []
        if severity == "CRITICAL" and self.policy.reject_critical_surface_risk:
            rejections.append("CRITICAL_RISK_SURFACE_LOSS")
        if surface_score < self.policy.minimum_surface_score:
            if self.policy.reject_below_minimum_score:
                rejections.append("RISK_SURFACE_SCORE_BELOW_MINIMUM")
            else:
                warnings.append("RISK_SURFACE_SCORE_BELOW_PREFERRED_MINIMUM")
        if gamma_loss > self.policy.maximum_gamma_loss_pct_of_capital:
            warnings.append("GAMMA_SHOCK_LIMIT_EXCEEDED")
        if vega_loss > self.policy.maximum_vega_loss_pct_of_capital:
            warnings.append("VEGA_SHOCK_LIMIT_EXCEEDED")
        if theta_loss > self.policy.maximum_theta_loss_pct_of_capital:
            warnings.append("THETA_DECAY_LIMIT_EXCEEDED")

        return RiskSurfaceProfile(
            symbol=str(symbol), strategy=str(strategy), underlying_price=underlying_price,
            implied_volatility=implied_volatility, days_to_expiration=int(days_to_expiration),
            capital_required=capital_required, initial_capital=initial_capital,
            net_delta=float(net_delta), net_gamma=float(net_gamma), net_vega=float(net_vega),
            net_theta=float(net_theta), net_rho=float(net_rho), point_count=len(points),
            worst_case_pnl=float(worst.approximated_pnl), best_case_pnl=float(best.approximated_pnl),
            base_case_pnl=float(base.approximated_pnl), maximum_loss_pct_of_capital=max_loss_pct,
            maximum_gain_pct_of_capital=max_gain_pct, worst_price_shock_pct=worst.price_shock_pct,
            worst_volatility_shock=worst.volatility_shock,
            worst_time_offset_days=worst.time_offset_days,
            delta_gamma_error_estimate=self._approximation_error(points),
            nonlinear_exposure_score=nonlinear_score, gamma_risk_score=gamma_score,
            vega_risk_score=vega_score, theta_risk_score=theta_score,
            surface_score=surface_score, surface_grade=grade, risk_severity=severity,
            allowed=not rejections, valid=True, points=points,
            attributions=self.attribution_engine.attribute(worst),
            rejection_reasons=rejections, warnings=warnings,
            metadata={"engine": "DELTA_GAMMA_TAYLOR", "surface_dimensions": [
                len(self.policy.price_shocks_pct), len(self.policy.volatility_shocks),
                len(self.policy.time_offsets_days)]},
        )

    def _invalid(self, symbol, strategy, underlying_price, implied_volatility,
                 days_to_expiration, capital_required, initial_capital,
                 net_delta, net_gamma, net_vega, net_theta, net_rho):
        return RiskSurfaceProfile(
            symbol=str(symbol), strategy=str(strategy), underlying_price=float(underlying_price),
            implied_volatility=float(implied_volatility), days_to_expiration=int(days_to_expiration),
            capital_required=float(capital_required), initial_capital=float(initial_capital),
            net_delta=float(net_delta), net_gamma=float(net_gamma), net_vega=float(net_vega),
            net_theta=float(net_theta), net_rho=float(net_rho), point_count=0,
            worst_case_pnl=0.0, best_case_pnl=0.0, base_case_pnl=0.0,
            maximum_loss_pct_of_capital=0.0, maximum_gain_pct_of_capital=0.0,
            worst_price_shock_pct=0.0, worst_volatility_shock=0.0,
            worst_time_offset_days=0, delta_gamma_error_estimate=0.0,
            nonlinear_exposure_score=0.0, gamma_risk_score=0.0,
            vega_risk_score=0.0, theta_risk_score=0.0, surface_score=0.0,
            surface_grade="F", risk_severity="UNKNOWN", allowed=False, valid=False,
            rejection_reasons=["INVALID_RISK_SURFACE_INPUT"],
        )

    def _factor_score(self, value, limit):
        if limit <= 0.0:
            return 100.0 if value <= 0.0 else 0.0
        return max(0.0, min(100.0, 100.0 * (1.0 - value / limit)))

    def _nonlinear_score(self, points):
        total = sum(abs(point.approximated_pnl) for point in points)
        gamma = sum(abs(point.gamma_component) for point in points)
        ratio = gamma / total if total else 0.0
        return max(0.0, min(100.0, 100.0 * (1.0 - ratio)))

    def _approximation_error(self, points):
        values = [abs(point.gamma_component) for point in points]
        denominator = max((abs(point.approximated_pnl) for point in points), default=0.0)
        return max(values, default=0.0) / denominator if denominator else 0.0

    def _severity(self, loss_pct):
        if loss_pct >= self.policy.critical_loss_pct_of_capital:
            return "CRITICAL"
        if loss_pct >= self.policy.severe_loss_pct_of_capital:
            return "SEVERE"
        if loss_pct >= self.policy.maximum_loss_pct_of_capital:
            return "MODERATE"
        return "LOW"

    def _grade(self, score):
        if score >= 90.0: return "A"
        if score >= 80.0: return "B"
        if score >= 70.0: return "C"
        if score >= 60.0: return "D"
        return "F"
