import math

from trading_ai.strategy_engine.multi_strategy_validator import (
    MultiStrategyValidator,
)
from trading_ai.strategy_engine.strategy_catalog import (
    StrategyCatalog,
)
from trading_ai.strategy_engine.strategy_payoff_profile import (
    StrategyPayoffProfile,
)
from trading_ai.strategy_engine.strategy_structure import (
    StrategyStructure,
)


class StrategyPayoffEngine:
    def __init__(
        self,
        price_steps: int = 401,
        price_range_pct: float = 0.75,
    ):
        self.price_steps = max(
            int(price_steps or 401),
            51,
        )

        self.price_range_pct = max(
            float(price_range_pct or 0.75),
            0.10,
        )

        self.validator = MultiStrategyValidator()

    def analyze(
        self,
        structure: StrategyStructure,
        estimated_leg_values: dict | None = None,
        expected_profit: float | None = None,
    ) -> StrategyPayoffProfile:
        validation = self.validator.validate(
            structure
        )

        warnings = list(
            validation.warnings
        )

        if not validation.valid:
            return StrategyPayoffProfile(
                symbol=structure.symbol,
                strategy=structure.strategy,
                valuation_mode="INVALID",
                net_debit=round(
                    structure.net_debit_per_share
                    * 100.0
                    * structure.contracts,
                    2,
                ),
                net_credit=round(
                    structure.net_credit_per_share
                    * 100.0
                    * structure.contracts,
                    2,
                ),
                maximum_profit=None,
                maximum_loss=None,
                break_even_points=[],
                risk_reward_ratio=None,
                return_on_risk_pct=None,
                profit_at_current_price=0.0,
                best_price_tested=0.0,
                worst_price_tested=0.0,
                best_profit_tested=0.0,
                worst_loss_tested=0.0,
                net_delta=structure.net_delta,
                net_gamma=structure.net_gamma,
                net_theta=structure.net_theta,
                net_vega=structure.net_vega,
                net_rho=structure.net_rho,
                unlimited_profit=False,
                unlimited_loss=False,
                defined_risk=False,
                capital_required=0.0,
                expected_profit=0.0,
                expected_return_pct=0.0,
                payoff_points=[],
                valid=False,
                warnings=warnings,
                notes=validation.errors,
            )

        if structure.is_multi_expiration:
            return self._analyze_multi_expiration(
                structure=structure,
                estimated_leg_values=(
                    estimated_leg_values
                ),
                expected_profit=expected_profit,
                warnings=warnings,
            )

        return self._analyze_same_expiry(
            structure=structure,
            expected_profit=expected_profit,
            warnings=warnings,
        )

    def pnl_at_price(
        self,
        structure: StrategyStructure,
        underlying_price: float,
    ) -> float:
        pnl_per_share = sum(
            leg.expiration_pnl_per_share(
                underlying_price
            )
            for leg in structure.legs
        )

        return (
            pnl_per_share
            * 100.0
            * structure.contracts
        )

    def _analyze_same_expiry(
        self,
        structure,
        expected_profit,
        warnings,
    ):
        price_grid = self._price_grid(
            structure
        )

        payoff_points = [
            {
                "underlying_price": round(
                    price,
                    4,
                ),
                "pnl": round(
                    self.pnl_at_price(
                        structure,
                        price,
                    ),
                    2,
                ),
            }
            for price in price_grid
        ]

        pnl_values = [
            point["pnl"]
            for point in payoff_points
        ]

        best_index = max(
            range(len(pnl_values)),
            key=lambda index: pnl_values[index],
        )

        worst_index = min(
            range(len(pnl_values)),
            key=lambda index: pnl_values[index],
        )

        best_profit_tested = pnl_values[
            best_index
        ]

        worst_loss_tested = pnl_values[
            worst_index
        ]

        maximum_profit, unlimited_profit = (
            self._maximum_profit(
                structure
            )
        )

        maximum_loss, unlimited_loss = (
            self._maximum_loss(
                structure
            )
        )

        break_even_points = self._break_evens(
            payoff_points
        )

        capital_required = self._capital_required(
            structure=structure,
            maximum_loss=maximum_loss,
        )

        expected_profit_value = (
            float(expected_profit)
            if expected_profit is not None
            else self._default_expected_profit(
                maximum_profit=maximum_profit,
                maximum_loss=maximum_loss,
            )
        )

        expected_return_pct = (
            expected_profit_value
            / capital_required
            if capital_required > 0
            else 0.0
        )

        risk_reward_ratio = (
            maximum_profit / maximum_loss
            if (
                maximum_profit is not None
                and maximum_loss is not None
                and maximum_loss > 0
            )
            else None
        )

        return_on_risk_pct = (
            maximum_profit / maximum_loss * 100.0
            if (
                maximum_profit is not None
                and maximum_loss is not None
                and maximum_loss > 0
            )
            else None
        )

        profit_at_current = self.pnl_at_price(
            structure,
            structure.underlying_price,
        )

        return StrategyPayoffProfile(
            symbol=structure.symbol,
            strategy=structure.strategy,
            valuation_mode="EXPIRATION_INTRINSIC",
            net_debit=round(
                structure.net_debit_per_share
                * 100.0
                * structure.contracts,
                2,
            ),
            net_credit=round(
                structure.net_credit_per_share
                * 100.0
                * structure.contracts,
                2,
            ),
            maximum_profit=(
                round(maximum_profit, 2)
                if maximum_profit is not None
                else None
            ),
            maximum_loss=(
                round(maximum_loss, 2)
                if maximum_loss is not None
                else None
            ),
            break_even_points=[
                round(value, 4)
                for value in break_even_points
            ],
            risk_reward_ratio=(
                round(risk_reward_ratio, 4)
                if risk_reward_ratio is not None
                else None
            ),
            return_on_risk_pct=(
                round(return_on_risk_pct, 2)
                if return_on_risk_pct is not None
                else None
            ),
            profit_at_current_price=round(
                profit_at_current,
                2,
            ),
            best_price_tested=round(
                payoff_points[
                    best_index
                ]["underlying_price"],
                4,
            ),
            worst_price_tested=round(
                payoff_points[
                    worst_index
                ]["underlying_price"],
                4,
            ),
            best_profit_tested=round(
                best_profit_tested,
                2,
            ),
            worst_loss_tested=round(
                worst_loss_tested,
                2,
            ),
            net_delta=round(
                structure.net_delta,
                4,
            ),
            net_gamma=round(
                structure.net_gamma,
                5,
            ),
            net_theta=round(
                structure.net_theta,
                4,
            ),
            net_vega=round(
                structure.net_vega,
                4,
            ),
            net_rho=round(
                structure.net_rho,
                4,
            ),
            unlimited_profit=unlimited_profit,
            unlimited_loss=unlimited_loss,
            defined_risk=not unlimited_loss,
            capital_required=round(
                capital_required,
                2,
            ),
            expected_profit=round(
                expected_profit_value,
                2,
            ),
            expected_return_pct=round(
                expected_return_pct,
                4,
            ),
            payoff_points=payoff_points,
            valid=True,
            warnings=warnings,
            notes=[],
        )

    def _analyze_multi_expiration(
        self,
        structure,
        estimated_leg_values,
        expected_profit,
        warnings,
    ):
        notes = [
            "Calendar and diagonal strategies cannot be "
            "valued accurately using final intrinsic value "
            "for all legs at one common date.",
        ]

        if not estimated_leg_values:
            warnings.append(
                "Estimated future leg values were not supplied"
            )

            notes.append(
                "Provide estimated_leg_values keyed by option_symbol "
                "to calculate mark-to-model PnL."
            )

            net_debit = (
                structure.net_debit_per_share
                * 100.0
                * structure.contracts
            )

            return StrategyPayoffProfile(
                symbol=structure.symbol,
                strategy=structure.strategy,
                valuation_mode="MULTI_EXPIRATION_UNVALUED",
                net_debit=round(net_debit, 2),
                net_credit=round(
                    structure.net_credit_per_share
                    * 100.0
                    * structure.contracts,
                    2,
                ),
                maximum_profit=None,
                maximum_loss=round(
                    net_debit,
                    2,
                ),
                break_even_points=[],
                risk_reward_ratio=None,
                return_on_risk_pct=None,
                profit_at_current_price=0.0,
                best_price_tested=0.0,
                worst_price_tested=0.0,
                best_profit_tested=0.0,
                worst_loss_tested=0.0,
                net_delta=structure.net_delta,
                net_gamma=structure.net_gamma,
                net_theta=structure.net_theta,
                net_vega=structure.net_vega,
                net_rho=structure.net_rho,
                unlimited_profit=False,
                unlimited_loss=False,
                defined_risk=True,
                capital_required=round(
                    net_debit,
                    2,
                ),
                expected_profit=0.0,
                expected_return_pct=0.0,
                payoff_points=[],
                valid=True,
                warnings=warnings,
                notes=notes,
            )

        mark_value_per_share = 0.0

        for leg in structure.legs:
            key = (
                leg.option_symbol
                or self._synthetic_leg_key(
                    leg
                )
            )

            future_value = float(
                estimated_leg_values.get(
                    key,
                    0.0,
                )
                or 0.0
            )

            mark_value_per_share += (
                leg.sign
                * future_value
                * leg.quantity
            )

        pnl_per_share = (
            mark_value_per_share
            + structure.net_cash_flow_per_share
        )

        pnl_dollars = (
            pnl_per_share
            * 100.0
            * structure.contracts
        )

        capital_required = (
            structure.net_debit_per_share
            * 100.0
            * structure.contracts
        )

        expected_profit_value = (
            float(expected_profit)
            if expected_profit is not None
            else pnl_dollars
        )

        expected_return_pct = (
            expected_profit_value
            / capital_required
            if capital_required > 0
            else 0.0
        )

        notes.append(
            "Multi-expiration result uses supplied "
            "mark-to-model future option values."
        )

        return StrategyPayoffProfile(
            symbol=structure.symbol,
            strategy=structure.strategy,
            valuation_mode="MARK_TO_MODEL",
            net_debit=round(
                capital_required,
                2,
            ),
            net_credit=round(
                structure.net_credit_per_share
                * 100.0
                * structure.contracts,
                2,
            ),
            maximum_profit=None,
            maximum_loss=round(
                capital_required,
                2,
            ),
            break_even_points=[],
            risk_reward_ratio=None,
            return_on_risk_pct=None,
            profit_at_current_price=round(
                pnl_dollars,
                2,
            ),
            best_price_tested=0.0,
            worst_price_tested=0.0,
            best_profit_tested=round(
                pnl_dollars,
                2,
            ),
            worst_loss_tested=round(
                min(pnl_dollars, 0.0),
                2,
            ),
            net_delta=round(
                structure.net_delta,
                4,
            ),
            net_gamma=round(
                structure.net_gamma,
                5,
            ),
            net_theta=round(
                structure.net_theta,
                4,
            ),
            net_vega=round(
                structure.net_vega,
                4,
            ),
            net_rho=round(
                structure.net_rho,
                4,
            ),
            unlimited_profit=False,
            unlimited_loss=False,
            defined_risk=True,
            capital_required=round(
                capital_required,
                2,
            ),
            expected_profit=round(
                expected_profit_value,
                2,
            ),
            expected_return_pct=round(
                expected_return_pct,
                4,
            ),
            payoff_points=[],
            valid=True,
            warnings=warnings,
            notes=notes,
        )

    def _maximum_profit(
        self,
        structure,
    ):
        strategy = structure.strategy
        multiplier = (
            100.0
            * structure.contracts
        )

        debit = structure.net_debit_per_share
        credit = structure.net_credit_per_share

        if strategy in {
            "LONG_CALL",
            "LONG_STRADDLE",
            "LONG_STRANGLE",
        }:
            return None, True

        if strategy == "LONG_PUT":
            strike = structure.legs[0].strike

            return (
                max(
                    strike - debit,
                    0.0,
                )
                * multiplier,
                False,
            )

        if strategy in {
            "BULL_CALL_SPREAD",
            "BEAR_PUT_SPREAD",
        }:
            width = (
                max(structure.strikes)
                - min(structure.strikes)
            )

            return (
                max(
                    width - debit,
                    0.0,
                )
                * multiplier,
                False,
            )

        if strategy in {
            "BULL_PUT_SPREAD",
            "BEAR_CALL_SPREAD",
            "IRON_CONDOR",
            "IRON_BUTTERFLY",
        }:
            return (
                credit * multiplier,
                False,
            )

        return None, False

    def _maximum_loss(
        self,
        structure,
    ):
        strategy = structure.strategy
        multiplier = (
            100.0
            * structure.contracts
        )

        debit = structure.net_debit_per_share
        credit = structure.net_credit_per_share

        if strategy in {
            "LONG_CALL",
            "LONG_PUT",
            "LONG_STRADDLE",
            "LONG_STRANGLE",
        }:
            return (
                debit * multiplier,
                False,
            )

        if strategy in {
            "BULL_CALL_SPREAD",
            "BEAR_PUT_SPREAD",
        }:
            return (
                debit * multiplier,
                False,
            )

        if strategy in {
            "BULL_PUT_SPREAD",
            "BEAR_CALL_SPREAD",
        }:
            width = (
                max(structure.strikes)
                - min(structure.strikes)
            )

            return (
                max(
                    width - credit,
                    0.0,
                )
                * multiplier,
                False,
            )

        if strategy in {
            "IRON_CONDOR",
            "IRON_BUTTERFLY",
        }:
            puts = sorted(
                [
                    leg.strike
                    for leg in structure.legs
                    if leg.option_type == "PUT"
                ]
            )

            calls = sorted(
                [
                    leg.strike
                    for leg in structure.legs
                    if leg.option_type == "CALL"
                ]
            )

            put_width = (
                puts[-1] - puts[0]
                if len(puts) >= 2
                else 0.0
            )

            call_width = (
                calls[-1] - calls[0]
                if len(calls) >= 2
                else 0.0
            )

            width = max(
                put_width,
                call_width,
            )

            return (
                max(
                    width - credit,
                    0.0,
                )
                * multiplier,
                False,
            )

        return None, False

    def _break_evens(
        self,
        payoff_points,
    ):
        break_evens = []

        for left, right in zip(
            payoff_points,
            payoff_points[1:],
        ):
            left_pnl = left["pnl"]
            right_pnl = right["pnl"]

            if left_pnl == 0:
                break_evens.append(
                    left["underlying_price"]
                )

                continue

            if left_pnl * right_pnl < 0:
                left_price = left[
                    "underlying_price"
                ]

                right_price = right[
                    "underlying_price"
                ]

                ratio = (
                    abs(left_pnl)
                    / (
                        abs(left_pnl)
                        + abs(right_pnl)
                    )
                )

                break_even = (
                    left_price
                    + (
                        right_price
                        - left_price
                    )
                    * ratio
                )

                break_evens.append(
                    break_even
                )

        unique = []

        for value in break_evens:
            if not any(
                abs(value - existing)
                < 0.01
                for existing in unique
            ):
                unique.append(value)

        return unique

    def _price_grid(
        self,
        structure,
    ):
        center = structure.underlying_price

        minimum_strike = min(
            structure.strikes
        )

        maximum_strike = max(
            structure.strikes
        )

        lower = max(
            0.01,
            min(
                center
                * (
                    1.0
                    - self.price_range_pct
                ),
                minimum_strike * 0.50,
            ),
        )

        upper = max(
            center
            * (
                1.0
                + self.price_range_pct
            ),
            maximum_strike * 1.50,
        )

        step = (
            upper - lower
        ) / (
            self.price_steps - 1
        )

        return [
            lower + step * index
            for index in range(
                self.price_steps
            )
        ]

    def _capital_required(
        self,
        structure,
        maximum_loss,
    ):
        if maximum_loss is not None:
            return max(
                maximum_loss,
                0.0,
            )

        return (
            structure.net_debit_per_share
            * 100.0
            * structure.contracts
        )

    def _default_expected_profit(
        self,
        maximum_profit,
        maximum_loss,
    ):
        if maximum_profit is None:
            return 0.0

        if maximum_loss is None:
            return 0.0

        return max(
            min(
                maximum_profit * 0.35,
                maximum_loss * 0.50,
            ),
            0.0,
        )

    def _synthetic_leg_key(
        self,
        leg,
    ):
        return (
            f"{leg.option_type}_"
            f"{leg.strike}_"
            f"{leg.expiry}_"
            f"{leg.normalized_action}"
        )
