import math

from trading_ai.strategy_engine.option_scenario_pricer import (
    OptionScenarioPricer,
)
from trading_ai.strategy_engine.scenario_policy import (
    ScenarioPolicy,
)
from trading_ai.strategy_engine.scenario_result import (
    ScenarioAnalysisResult,
    ScenarioPoint,
)


class ScenarioEngine:
    """
    Deterministic institutional strategy scenario engine.
    """

    def __init__(
        self,
        policy: ScenarioPolicy | None = None,
        pricer: OptionScenarioPricer | None = None,
    ):
        self.policy = (
            policy
            or ScenarioPolicy()
        )

        self.pricer = (
            pricer
            or OptionScenarioPricer(
                annual_calendar_days=(
                    self.policy
                    .annual_calendar_days
                )
            )
        )

    def analyze(
        self,
        structure,
        volatility: float,
        days_to_expiry: int,
        capital_required: float | None = None,
        maximum_loss: float | None = None,
        scenarios=None,
    ) -> ScenarioAnalysisResult:
        base_price = float(
            structure.underlying_price
        )

        base_volatility = (
            self._normalize_volatility(
                volatility
            )
        )

        dte = max(
            int(days_to_expiry or 0),
            0,
        )

        capital = (
            float(capital_required)
            if capital_required is not None
            else self._derive_capital_required(
                structure
            )
        )

        max_loss = (
            float(maximum_loss)
            if maximum_loss is not None
            else capital
        )

        enabled_scenarios = [
            scenario
            for scenario in (
                scenarios
                or self.policy.scenarios
            )
            if scenario.enabled
        ]

        if (
            base_price <= 0
            or base_volatility <= 0
            or not enabled_scenarios
        ):
            return self._invalid_result(
                structure=structure,
                base_price=base_price,
                base_volatility=base_volatility,
                dte=dte,
                capital=capital,
                maximum_loss=max_loss,
                reason="INVALID_SCENARIO_INPUT",
            )

        base_value = self.pricer.structure_value(
            structure=structure,
            underlying_price=base_price,
            volatility=base_volatility,
            days_forward=0,
            risk_free_rate=(
                self.policy.risk_free_rate
            ),
            dividend_yield=(
                self.policy.dividend_yield
            ),
            base_days_to_expiry=dte,
        )

        entry_cash_flow = float(
            structure.net_cash_flow_dollars
        )

        base_pnl = (
            base_value
            + entry_cash_flow
        )

        scenario_points = []
        global_rejections = []
        global_warnings = []

        for scenario in enabled_scenarios:
            point = self._evaluate_scenario(
                structure=structure,
                scenario=scenario,
                base_underlying_price=base_price,
                base_volatility=base_volatility,
                base_days_to_expiry=dte,
                base_strategy_value=base_value,
                base_pnl=base_pnl,
                entry_cash_flow=entry_cash_flow,
                capital_required=capital,
                maximum_loss=max_loss,
            )

            scenario_points.append(point)

            if not point.passed:
                global_rejections.extend(
                    point.rejection_reasons
                )

            global_warnings.extend(
                point.warnings
            )

        valid_points = [
            point
            for point in scenario_points
            if not point.rejection_reasons
            or point.stressed_strategy_value
            is not None
        ]

        if not valid_points:
            return self._invalid_result(
                structure=structure,
                base_price=base_price,
                base_volatility=base_volatility,
                dte=dte,
                capital=capital,
                maximum_loss=max_loss,
                reason="NO_PRICEABLE_SCENARIOS",
            )

        worst = min(
            scenario_points,
            key=lambda point:
                point.stressed_pnl,
        )

        best = max(
            scenario_points,
            key=lambda point:
                point.stressed_pnl,
        )

        maximum_stress_loss = max(
            -worst.stressed_pnl,
            0.0,
        )

        loss_pct_of_capital = (
            maximum_stress_loss / capital
            if capital > 0
            else 0.0
        )

        loss_pct_of_max_loss = (
            maximum_stress_loss / max_loss
            if max_loss > 0
            else None
        )

        average_scenario_pnl = (
            sum(
                point.stressed_pnl
                for point in scenario_points
            )
            / len(scenario_points)
        )

        weighted_scenario_pnl = (
            self._weighted_scenario_pnl(
                scenario_points,
                enabled_scenarios,
            )
        )

        downside_count = sum(
            1
            for point in scenario_points
            if point.stressed_pnl < 0
        )

        profitable_count = sum(
            1
            for point in scenario_points
            if point.stressed_pnl > 0
        )

        failed_count = sum(
            1
            for point in scenario_points
            if not point.passed
        )

        final_rejections = list(
            dict.fromkeys(
                global_rejections
            )
        )

        if (
            loss_pct_of_capital
            > self.policy
            .maximum_stress_loss_pct_of_capital
        ):
            final_rejections.append(
                "MAXIMUM_STRESS_LOSS_PCT_OF_CAPITAL_EXCEEDED"
            )

        if (
            loss_pct_of_max_loss is not None
            and loss_pct_of_max_loss
            > self.policy
            .maximum_stress_loss_pct_of_max_loss
        ):
            final_rejections.append(
                "MAXIMUM_STRESS_LOSS_PCT_OF_MAXIMUM_LOSS_EXCEEDED"
            )

        stress_score = self._stress_score(
            maximum_loss_pct=(
                loss_pct_of_capital
            ),
            failed_scenario_count=(
                failed_count
            ),
            scenario_count=len(
                scenario_points
            ),
        )

        allowed = not final_rejections

        return ScenarioAnalysisResult(
            symbol=structure.symbol,
            strategy=structure.strategy,
            underlying_price=round(
                base_price,
                4,
            ),
            base_volatility=round(
                base_volatility,
                4,
            ),
            days_to_expiry=dte,
            capital_required=round(
                capital,
                2,
            ),
            maximum_loss=round(
                max_loss,
                2,
            ),
            base_strategy_value=round(
                base_value,
                2,
            ),
            base_pnl=round(
                base_pnl,
                2,
            ),
            scenario_points=scenario_points,
            worst_scenario_name=(
                worst.scenario_name
            ),
            worst_scenario_pnl=round(
                worst.stressed_pnl,
                2,
            ),
            best_scenario_name=(
                best.scenario_name
            ),
            best_scenario_pnl=round(
                best.stressed_pnl,
                2,
            ),
            maximum_stress_loss=round(
                maximum_stress_loss,
                2,
            ),
            maximum_stress_loss_pct_of_capital=round(
                loss_pct_of_capital,
                4,
            ),
            maximum_stress_loss_pct_of_maximum_loss=(
                round(
                    loss_pct_of_max_loss,
                    4,
                )
                if loss_pct_of_max_loss
                is not None
                else None
            ),
            average_scenario_pnl=round(
                average_scenario_pnl,
                2,
            ),
            weighted_scenario_pnl=(
                round(
                    weighted_scenario_pnl,
                    2,
                )
                if weighted_scenario_pnl
                is not None
                else None
            ),
            downside_scenario_count=(
                downside_count
            ),
            profitable_scenario_count=(
                profitable_count
            ),
            failed_scenario_count=(
                failed_count
            ),
            stress_score=round(
                stress_score,
                2,
            ),
            stress_grade=self._grade(
                stress_score
            ),
            risk_severity=self._risk_severity(
                loss_pct_of_capital
            ),
            allowed=allowed,
            valid=True,
            rejection_reasons=list(
                dict.fromkeys(
                    final_rejections
                )
            ),
            warnings=list(
                dict.fromkeys(
                    global_warnings
                )
            ),
            metadata={
                "scenario_count":
                    len(scenario_points),
                "entry_cash_flow":
                    round(
                        entry_cash_flow,
                        2,
                    ),
            },
        )

    def _evaluate_scenario(
        self,
        structure,
        scenario,
        base_underlying_price,
        base_volatility,
        base_days_to_expiry,
        base_strategy_value,
        base_pnl,
        entry_cash_flow,
        capital_required,
        maximum_loss,
    ) -> ScenarioPoint:
        stressed_price = max(
            base_underlying_price
            * (
                1.0
                + scenario
                .underlying_shock_pct
            ),
            self.policy.minimum_underlying_price,
        )

        stressed_volatility = (
            base_volatility
            * (
                1.0
                + scenario
                .volatility_shock_pct
            )
        )

        stressed_volatility = max(
            self.policy.minimum_volatility,
            min(
                self.policy.maximum_volatility,
                stressed_volatility,
            ),
        )

        stressed_dte = max(
            base_days_to_expiry
            - scenario.days_forward,
            0,
        )

        stressed_rate = (
            self.policy.risk_free_rate
            + scenario.risk_free_rate_shock
        )

        stressed_dividend = (
            self.policy.dividend_yield
            + scenario.dividend_yield_shock
        )

        rejection_reasons = []
        warnings = []

        try:
            stressed_value = (
                self.pricer.structure_value(
                    structure=structure,
                    underlying_price=(
                        stressed_price
                    ),
                    volatility=(
                        stressed_volatility
                    ),
                    days_forward=(
                        scenario.days_forward
                    ),
                    risk_free_rate=(
                        stressed_rate
                    ),
                    dividend_yield=(
                        stressed_dividend
                    ),
                    base_days_to_expiry=(
                        base_days_to_expiry
                    ),
                )
            )

        except Exception as exc:
            stressed_value = 0.0

            warnings.append(
                "Scenario pricing failed: "
                f"{exc}"
            )

            if (
                self.policy
                .reject_unpriceable_scenarios
            ):
                rejection_reasons.append(
                    "SCENARIO_PRICING_FAILED"
                )

        stressed_pnl = (
            stressed_value
            + entry_cash_flow
        )

        pnl_change = (
            stressed_pnl
            - base_pnl
        )

        return_on_capital = (
            stressed_pnl
            / capital_required
            if capital_required > 0
            else 0.0
        )

        loss_pct_of_maximum_loss = (
            max(
                -stressed_pnl,
                0.0,
            )
            / maximum_loss
            if maximum_loss > 0
            else None
        )

        if (
            capital_required > 0
            and max(
                -stressed_pnl,
                0.0,
            )
            / capital_required
            > self.policy
            .maximum_stress_loss_pct_of_capital
        ):
            rejection_reasons.append(
                "SCENARIO_LOSS_PCT_OF_CAPITAL_EXCEEDED"
            )

        if (
            loss_pct_of_maximum_loss
            is not None
            and loss_pct_of_maximum_loss
            > self.policy
            .maximum_stress_loss_pct_of_max_loss
        ):
            rejection_reasons.append(
                "SCENARIO_LOSS_PCT_OF_MAXIMUM_LOSS_EXCEEDED"
            )

        return ScenarioPoint(
            scenario_name=scenario.name,
            scenario_description=(
                scenario.description
            ),
            category=scenario.category,
            severity=scenario.severity,
            base_underlying_price=round(
                base_underlying_price,
                4,
            ),
            stressed_underlying_price=round(
                stressed_price,
                4,
            ),
            base_volatility=round(
                base_volatility,
                4,
            ),
            stressed_volatility=round(
                stressed_volatility,
                4,
            ),
            base_days_to_expiry=(
                base_days_to_expiry
            ),
            stressed_days_to_expiry=(
                stressed_dte
            ),
            days_forward=(
                scenario.days_forward
            ),
            base_strategy_value=round(
                base_strategy_value,
                2,
            ),
            stressed_strategy_value=round(
                stressed_value,
                2,
            ),
            entry_cash_flow=round(
                entry_cash_flow,
                2,
            ),
            stressed_pnl=round(
                stressed_pnl,
                2,
            ),
            pnl_change_from_base=round(
                pnl_change,
                2,
            ),
            return_on_capital=round(
                return_on_capital,
                4,
            ),
            loss_pct_of_maximum_loss=(
                round(
                    loss_pct_of_maximum_loss,
                    4,
                )
                if loss_pct_of_maximum_loss
                is not None
                else None
            ),
            passed=not rejection_reasons,
            rejection_reasons=list(
                dict.fromkeys(
                    rejection_reasons
                )
            ),
            warnings=warnings,
        )

    def _derive_capital_required(
        self,
        structure,
    ) -> float:
        debit = float(
            structure.net_debit_per_share
        )

        if debit > 0:
            return (
                debit
                * 100.0
                * int(
                    structure.contracts
                    or 1
                )
            )

        strikes = sorted(
            structure.strikes
        )

        if len(strikes) >= 2:
            width = (
                max(strikes)
                - min(strikes)
            )

            credit = float(
                structure
                .net_credit_per_share
            )

            return max(
                (
                    width - credit
                )
                * 100.0
                * int(
                    structure.contracts
                    or 1
                ),
                0.0,
            )

        return 0.0

    def _weighted_scenario_pnl(
        self,
        points,
        scenarios,
    ):
        weights = {
            scenario.name:
                scenario.probability_weight
            for scenario in scenarios
            if scenario.probability_weight
            is not None
        }

        if not weights:
            return None

        total_weight = sum(
            weights.values()
        )

        if total_weight <= 0:
            return None

        return sum(
            point.stressed_pnl
            * weights.get(
                point.scenario_name,
                0.0,
            )
            for point in points
        ) / total_weight

    def _stress_score(
        self,
        maximum_loss_pct,
        failed_scenario_count,
        scenario_count,
    ):
        score = 100.0

        if maximum_loss_pct >= 0.20:
            score -= 70.0
        elif maximum_loss_pct >= 0.10:
            score -= 50.0
        elif maximum_loss_pct >= 0.05:
            score -= 30.0
        elif maximum_loss_pct >= 0.02:
            score -= 15.0

        if scenario_count > 0:
            failed_ratio = (
                failed_scenario_count
                / scenario_count
            )

            score -= (
                failed_ratio
                * 30.0
            )

        return max(
            0.0,
            min(
                100.0,
                score,
            ),
        )

    def _risk_severity(
        self,
        loss_pct,
    ):
        if (
            loss_pct
            >= self.policy
            .critical_loss_threshold_pct
        ):
            return "CRITICAL"

        if (
            loss_pct
            >= self.policy
            .severe_loss_threshold_pct
        ):
            return "SEVERE"

        if loss_pct >= 0.02:
            return "MODERATE"

        return "LOW"

    def _grade(
        self,
        score,
    ):
        if score >= 90:
            return "A"

        if score >= 80:
            return "B"

        if score >= 70:
            return "C"

        if score >= 60:
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

    def _invalid_result(
        self,
        structure,
        base_price,
        base_volatility,
        dte,
        capital,
        maximum_loss,
        reason,
    ):
        return ScenarioAnalysisResult(
            symbol=structure.symbol,
            strategy=structure.strategy,
            underlying_price=base_price,
            base_volatility=base_volatility,
            days_to_expiry=dte,
            capital_required=capital,
            maximum_loss=maximum_loss,
            base_strategy_value=0.0,
            base_pnl=0.0,
            scenario_points=[],
            worst_scenario_name="",
            worst_scenario_pnl=0.0,
            best_scenario_name="",
            best_scenario_pnl=0.0,
            maximum_stress_loss=0.0,
            maximum_stress_loss_pct_of_capital=0.0,
            maximum_stress_loss_pct_of_maximum_loss=None,
            average_scenario_pnl=0.0,
            weighted_scenario_pnl=None,
            downside_scenario_count=0,
            profitable_scenario_count=0,
            failed_scenario_count=0,
            stress_score=0.0,
            stress_grade="F",
            risk_severity="UNKNOWN",
            allowed=False,
            valid=False,
            rejection_reasons=[
                reason
            ],
            warnings=[],
            metadata={},
        )
