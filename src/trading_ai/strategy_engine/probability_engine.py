import math

import numpy as np

from trading_ai.strategy_engine.expected_value_engine import (
    ExpectedValueEngine,
)
from trading_ai.strategy_engine.probability_policy import (
    ProbabilityPolicy,
)
from trading_ai.strategy_engine.probability_profile import (
    ProbabilityProfile,
)
from trading_ai.strategy_engine.strategy_payoff_engine import (
    StrategyPayoffEngine,
)
from trading_ai.strategy_engine.terminal_price_model import (
    TerminalPriceModel,
)


class ProbabilityEngine:
    """
    Monte Carlo probability and expected-value engine.

    The engine evaluates the strategy's expiration PnL at every
    simulated terminal underlying price.
    """

    def __init__(
        self,
        policy: ProbabilityPolicy | None = None,
        terminal_price_model: TerminalPriceModel | None = None,
        payoff_engine: StrategyPayoffEngine | None = None,
        expected_value_engine: ExpectedValueEngine | None = None,
    ):
        self.policy = policy or ProbabilityPolicy()
        self.policy.validate()

        self.terminal_price_model = (
            terminal_price_model
            or TerminalPriceModel(self.policy)
        )

        self.payoff_engine = (
            payoff_engine
            or StrategyPayoffEngine()
        )

        self.expected_value_engine = (
            expected_value_engine
            or ExpectedValueEngine()
        )

    def analyze(
        self,
        structure,
        volatility: float,
        horizon_days: int,
        simulation_count: int | None = None,
        random_seed: int | None = None,
        maximum_profit: float | None = None,
        maximum_loss: float | None = None,
        capital_required: float | None = None,
        profit_target_dollars: float | None = None,
        stop_loss_dollars: float | None = None,
        include_touch_probabilities: bool = True,
    ) -> ProbabilityProfile:
        count = int(
            simulation_count
            if simulation_count is not None
            else self.policy.simulation_count
        )

        seed = int(
            random_seed
            if random_seed is not None
            else self.policy.random_seed
        )

        sigma = self._normalize_volatility(
            volatility
        )

        payoff_profile = self.payoff_engine.analyze(
            structure
        )

        warnings = list(
            payoff_profile.warnings
        )

        if not payoff_profile.valid:
            return self._invalid_profile(
                structure=structure,
                volatility=sigma,
                horizon_days=horizon_days,
                simulation_count=count,
                random_seed=seed,
                warnings=warnings
                + payoff_profile.notes,
            )

        if structure.is_multi_expiration:
            warnings.append(
                "Multi-expiration strategies require mark-to-model "
                "simulation and are not evaluated by expiration intrinsic PnL"
            )

            return self._invalid_profile(
                structure=structure,
                volatility=sigma,
                horizon_days=horizon_days,
                simulation_count=count,
                random_seed=seed,
                warnings=warnings,
            )

        terminal_prices = (
            self.terminal_price_model
            .simulate_terminal_prices(
                underlying_price=(
                    structure.underlying_price
                ),
                volatility=sigma,
                horizon_days=horizon_days,
                simulation_count=count,
                random_seed=seed,
            )
        )

        pnl_values = self._pnl_array(
            structure=structure,
            terminal_prices=terminal_prices,
        )

        profitable_mask = pnl_values > (
            self.policy.breakeven_tolerance_dollars
        )

        losing_mask = pnl_values < -(
            self.policy.breakeven_tolerance_dollars
        )

        breakeven_mask = ~(
            profitable_mask | losing_mask
        )

        probability_of_profit = float(
            np.mean(profitable_mask)
        )

        probability_of_loss = float(
            np.mean(losing_mask)
        )

        probability_of_breakeven = float(
            np.mean(breakeven_mask)
        )

        effective_max_profit = (
            float(maximum_profit)
            if maximum_profit is not None
            else payoff_profile.maximum_profit
        )

        effective_max_loss = (
            float(maximum_loss)
            if maximum_loss is not None
            else payoff_profile.maximum_loss
        )

        effective_capital = (
            float(capital_required)
            if capital_required is not None
            else payoff_profile.capital_required
        )

        probability_of_max_profit = (
            self._probability_near_maximum(
                pnl_values=pnl_values,
                maximum_value=effective_max_profit,
            )
        )

        probability_of_max_loss = (
            self._probability_near_minimum(
                pnl_values=pnl_values,
                maximum_loss=effective_max_loss,
            )
        )

        lower_breakeven, upper_breakeven = (
            self._breakeven_bounds(
                payoff_profile.break_even_points
            )
        )

        probability_below_lower = (
            float(
                np.mean(
                    terminal_prices
                    < lower_breakeven
                )
            )
            if lower_breakeven is not None
            else None
        )

        probability_above_upper = (
            float(
                np.mean(
                    terminal_prices
                    > upper_breakeven
                )
            )
            if upper_breakeven is not None
            else None
        )

        probability_inside = None

        if (
            lower_breakeven is not None
            and upper_breakeven is not None
            and lower_breakeven < upper_breakeven
        ):
            probability_inside = float(
                np.mean(
                    (
                        terminal_prices
                        >= lower_breakeven
                    )
                    & (
                        terminal_prices
                        <= upper_breakeven
                    )
                )
            )

        if profit_target_dollars is None:
            profit_target_dollars = (
                float(effective_max_profit)
                * self.policy
                .profit_target_pct_of_max_profit
                if effective_max_profit is not None
                and effective_max_profit > 0
                else None
            )

        if stop_loss_dollars is None:
            stop_loss_dollars = (
                float(effective_max_loss)
                * self.policy
                .stop_loss_pct_of_max_loss
                if effective_max_loss is not None
                and effective_max_loss > 0
                else None
            )

        probability_profit_target = (
            float(
                np.mean(
                    pnl_values
                    >= profit_target_dollars
                )
            )
            if profit_target_dollars is not None
            else None
        )

        probability_stop_loss = (
            float(
                np.mean(
                    pnl_values
                    <= -stop_loss_dollars
                )
            )
            if stop_loss_dollars is not None
            else None
        )

        probability_touch_upper = None
        probability_touch_lower = None

        if include_touch_probabilities and (
            upper_breakeven is not None
            or lower_breakeven is not None
        ):
            paths = (
                self.terminal_price_model
                .simulate_paths(
                    underlying_price=(
                        structure.underlying_price
                    ),
                    volatility=sigma,
                    horizon_days=horizon_days,
                    simulation_count=count,
                    random_seed=seed,
                )
            )

            if upper_breakeven is not None:
                probability_touch_upper = float(
                    np.mean(
                        np.max(paths, axis=1)
                        >= upper_breakeven
                    )
                )

            if lower_breakeven is not None:
                probability_touch_lower = float(
                    np.mean(
                        np.min(paths, axis=1)
                        <= lower_breakeven
                    )
                )

        expected_values = (
            self.expected_value_engine.calculate(
                pnl_values=pnl_values,
                capital_required=effective_capital,
                maximum_loss=(
                    effective_max_loss or 0.0
                ),
            )
        )

        confidence_score = self._confidence_score(
            simulation_count=count,
            volatility=sigma,
            payoff_profile=payoff_profile,
        )

        return ProbabilityProfile(
            symbol=structure.symbol,
            strategy=structure.strategy,
            underlying_price=round(
                structure.underlying_price,
                4,
            ),
            horizon_days=int(horizon_days),
            volatility=round(sigma, 4),
            risk_free_rate=round(
                self.policy.risk_free_rate,
                4,
            ),
            dividend_yield=round(
                self.policy.dividend_yield,
                4,
            ),
            simulation_count=count,
            random_seed=seed,
            probability_of_profit=round(
                probability_of_profit,
                4,
            ),
            probability_of_loss=round(
                probability_of_loss,
                4,
            ),
            probability_of_breakeven=round(
                probability_of_breakeven,
                4,
            ),
            probability_of_max_profit=(
                round(
                    probability_of_max_profit,
                    4,
                )
                if probability_of_max_profit
                is not None
                else None
            ),
            probability_of_max_loss=(
                round(
                    probability_of_max_loss,
                    4,
                )
                if probability_of_max_loss
                is not None
                else None
            ),
            probability_above_upper_breakeven=(
                round(
                    probability_above_upper,
                    4,
                )
                if probability_above_upper
                is not None
                else None
            ),
            probability_below_lower_breakeven=(
                round(
                    probability_below_lower,
                    4,
                )
                if probability_below_lower
                is not None
                else None
            ),
            probability_inside_breakevens=(
                round(
                    probability_inside,
                    4,
                )
                if probability_inside
                is not None
                else None
            ),
            probability_touch_upper=(
                round(
                    probability_touch_upper,
                    4,
                )
                if probability_touch_upper
                is not None
                else None
            ),
            probability_touch_lower=(
                round(
                    probability_touch_lower,
                    4,
                )
                if probability_touch_lower
                is not None
                else None
            ),
            probability_profit_target=(
                round(
                    probability_profit_target,
                    4,
                )
                if probability_profit_target
                is not None
                else None
            ),
            probability_stop_loss=(
                round(
                    probability_stop_loss,
                    4,
                )
                if probability_stop_loss
                is not None
                else None
            ),
            expected_value=round(
                expected_values[
                    "expected_value"
                ],
                2,
            ),
            expected_value_per_contract=round(
                expected_values[
                    "expected_value"
                ]
                / max(
                    structure.contracts,
                    1,
                ),
                2,
            ),
            expected_return_on_capital=round(
                expected_values[
                    "expected_return_on_capital"
                ],
                4,
            ),
            expected_return_on_risk=round(
                expected_values[
                    "expected_return_on_risk"
                ],
                4,
            ),
            average_profit=round(
                expected_values[
                    "average_profit"
                ],
                2,
            ),
            average_loss=round(
                expected_values[
                    "average_loss"
                ],
                2,
            ),
            median_pnl=round(
                expected_values[
                    "median_pnl"
                ],
                2,
            ),
            pnl_standard_deviation=round(
                expected_values[
                    "pnl_standard_deviation"
                ],
                2,
            ),
            value_at_risk_95=round(
                expected_values[
                    "value_at_risk_95"
                ],
                2,
            ),
            conditional_value_at_risk_95=round(
                expected_values[
                    "conditional_value_at_risk_95"
                ],
                2,
            ),
            best_simulated_pnl=round(
                float(np.max(pnl_values)),
                2,
            ),
            worst_simulated_pnl=round(
                float(np.min(pnl_values)),
                2,
            ),
            expected_terminal_price=round(
                float(
                    np.mean(
                        terminal_prices
                    )
                ),
                4,
            ),
            median_terminal_price=round(
                float(
                    np.median(
                        terminal_prices
                    )
                ),
                4,
            ),
            terminal_price_stddev=round(
                float(
                    np.std(
                        terminal_prices
                    )
                ),
                4,
            ),
            lower_terminal_price_5pct=round(
                float(
                    np.percentile(
                        terminal_prices,
                        5,
                    )
                ),
                4,
            ),
            upper_terminal_price_95pct=round(
                float(
                    np.percentile(
                        terminal_prices,
                        95,
                    )
                ),
                4,
            ),
            confidence_score=round(
                confidence_score,
                2,
            ),
            confidence_grade=self._grade(
                confidence_score
            ),
            method="MONTE_CARLO_GBM_EXPIRATION_PAYOFF",
            valid=True,
            warnings=warnings,
            metadata={
                "break_even_points":
                    payoff_profile.break_even_points,
                "maximum_profit":
                    effective_max_profit,
                "maximum_loss":
                    effective_max_loss,
                "capital_required":
                    effective_capital,
                "profit_target_dollars":
                    profit_target_dollars,
                "stop_loss_dollars":
                    stop_loss_dollars,
            },
        )

    def _pnl_array(
        self,
        structure,
        terminal_prices,
    ) -> np.ndarray:
        total_pnl_per_share = np.zeros(
            len(terminal_prices),
            dtype=float,
        )

        for leg in structure.legs:
            strike = float(leg.strike)

            if leg.option_type == "CALL":
                intrinsic = np.maximum(
                    terminal_prices - strike,
                    0.0,
                )
            else:
                intrinsic = np.maximum(
                    strike - terminal_prices,
                    0.0,
                )

            leg_value = (
                leg.sign
                * intrinsic
                * leg.quantity
            )

            total_pnl_per_share += (
                leg_value
                + leg.cash_flow_per_share
            )

        return (
            total_pnl_per_share
            * 100.0
            * structure.contracts
        )

    def _probability_near_maximum(
        self,
        pnl_values,
        maximum_value,
    ):
        if maximum_value is None:
            return None

        maximum_value = float(
            maximum_value
        )

        if maximum_value <= 0:
            return None

        tolerance = max(
            maximum_value
            * self.policy
            .max_profit_tolerance_pct,
            0.01,
        )

        return float(
            np.mean(
                pnl_values
                >= maximum_value - tolerance
            )
        )

    def _probability_near_minimum(
        self,
        pnl_values,
        maximum_loss,
    ):
        if maximum_loss is None:
            return None

        maximum_loss = float(
            maximum_loss
        )

        if maximum_loss <= 0:
            return None

        tolerance = max(
            maximum_loss
            * self.policy
            .max_loss_tolerance_pct,
            0.01,
        )

        return float(
            np.mean(
                pnl_values
                <= -maximum_loss + tolerance
            )
        )

    def _breakeven_bounds(
        self,
        break_even_points,
    ):
        values = sorted(
            float(value)
            for value in (
                break_even_points or []
            )
        )

        if not values:
            return None, None

        if len(values) == 1:
            return values[0], values[0]

        return values[0], values[-1]

    def _confidence_score(
        self,
        simulation_count,
        volatility,
        payoff_profile,
    ):
        score = 50.0

        if simulation_count >= 100000:
            score += 25.0
        elif simulation_count >= 50000:
            score += 20.0
        elif simulation_count >= 10000:
            score += 12.0
        else:
            score += 5.0

        if 0.05 <= volatility <= 1.00:
            score += 15.0
        else:
            score += 5.0

        if payoff_profile.break_even_points:
            score += 5.0

        if payoff_profile.maximum_loss is not None:
            score += 5.0

        return max(
            0.0,
            min(100.0, score),
        )

    def _grade(
        self,
        score,
    ):
        if score >= 90:
            return "A+"

        if score >= 85:
            return "A"

        if score >= 80:
            return "A-"

        if score >= 75:
            return "B+"

        if score >= 70:
            return "B"

        if score >= 60:
            return "C"

        if score >= 45:
            return "D"

        return "F"

    def _normalize_volatility(
        self,
        value,
    ):
        volatility = float(
            value or 0.0
        )

        if volatility > 3.0:
            volatility /= 100.0

        return volatility

    def _invalid_profile(
        self,
        structure,
        volatility,
        horizon_days,
        simulation_count,
        random_seed,
        warnings,
    ):
        return ProbabilityProfile(
            symbol=structure.symbol,
            strategy=structure.strategy,
            underlying_price=(
                structure.underlying_price
            ),
            horizon_days=int(
                horizon_days
            ),
            volatility=volatility,
            risk_free_rate=(
                self.policy.risk_free_rate
            ),
            dividend_yield=(
                self.policy.dividend_yield
            ),
            simulation_count=(
                simulation_count
            ),
            random_seed=random_seed,
            probability_of_profit=0.0,
            probability_of_loss=0.0,
            probability_of_breakeven=0.0,
            probability_of_max_profit=None,
            probability_of_max_loss=None,
            probability_above_upper_breakeven=None,
            probability_below_lower_breakeven=None,
            probability_inside_breakevens=None,
            probability_touch_upper=None,
            probability_touch_lower=None,
            probability_profit_target=None,
            probability_stop_loss=None,
            expected_value=0.0,
            expected_value_per_contract=0.0,
            expected_return_on_capital=0.0,
            expected_return_on_risk=0.0,
            average_profit=0.0,
            average_loss=0.0,
            median_pnl=0.0,
            pnl_standard_deviation=0.0,
            value_at_risk_95=0.0,
            conditional_value_at_risk_95=0.0,
            best_simulated_pnl=0.0,
            worst_simulated_pnl=0.0,
            expected_terminal_price=0.0,
            median_terminal_price=0.0,
            terminal_price_stddev=0.0,
            lower_terminal_price_5pct=0.0,
            upper_terminal_price_95pct=0.0,
            confidence_score=0.0,
            confidence_grade="F",
            method="UNAVAILABLE",
            valid=False,
            warnings=warnings,
            metadata={},
        )
