from trading_ai.strategy_engine.scenario_policy import (
    ScenarioPolicy,
)
from trading_ai.strategy_engine.scenario_result import (
    PortfolioScenarioPoint,
    PortfolioScenarioResult,
)


class PortfolioScenarioEngine:
    """
    Aggregates deterministic scenario losses across portfolio positions.

    Each position must expose a strategy structure through one of:

        position.metadata["strategy_structure"]
        position.source_opportunity.metadata["strategy_structure"]
        position.source_opportunity.metadata["payoff_profile"]
            .strategy_structure
    """

    def __init__(
        self,
        scenario_engine,
        policy: ScenarioPolicy | None = None,
    ):
        self.scenario_engine = (
            scenario_engine
        )

        self.policy = (
            policy
            or scenario_engine.policy
        )

    def analyze(
        self,
        positions,
        initial_capital: float,
        volatility_by_symbol: dict,
        dte_by_symbol: dict | None = None,
    ) -> PortfolioScenarioResult:
        initial_capital = float(
            initial_capital
        )

        dte_by_symbol = dict(
            dte_by_symbol or {}
        )

        portfolio_points = []
        rejection_reasons = []
        warnings = []

        for scenario in self.policy.scenarios:
            if not scenario.enabled:
                continue

            total_base_value = 0.0
            total_stressed_value = 0.0
            total_stressed_pnl = 0.0
            total_base_pnl = 0.0

            position_results = []

            for position in positions:
                structure = self._structure_from_position(
                    position
                )

                if structure is None:
                    warnings.append(
                        f"{position.symbol}: strategy structure unavailable"
                    )
                    continue

                volatility = float(
                    volatility_by_symbol.get(
                        position.symbol,
                        0.0,
                    )
                    or 0.0
                )

                dte = int(
                    dte_by_symbol.get(
                        position.symbol,
                        getattr(
                            position,
                            "dte",
                            0,
                        ),
                    )
                    or 0
                )

                single_policy_scenarios = [
                    scenario
                ]

                result = (
                    self.scenario_engine
                    .analyze(
                        structure=structure,
                        volatility=volatility,
                        days_to_expiry=dte,
                        capital_required=(
                            position
                            .capital_required
                        ),
                        maximum_loss=(
                            position
                            .maximum_loss
                        ),
                        scenarios=(
                            single_policy_scenarios
                        ),
                    )
                )

                if (
                    not result.valid
                    or not result.scenario_points
                ):
                    position_results.append({
                        "symbol":
                            position.symbol,
                        "strategy":
                            position.strategy,
                        "valid": False,
                        "pnl": 0.0,
                        "rejections":
                            result
                            .rejection_reasons,
                    })
                    continue

                point = result.scenario_points[0]

                total_base_value += (
                    point.base_strategy_value
                )

                total_stressed_value += (
                    point.stressed_strategy_value
                )

                total_stressed_pnl += (
                    point.stressed_pnl
                )

                total_base_pnl += (
                    result.base_pnl
                )

                position_results.append({
                    "symbol":
                        position.symbol,
                    "strategy":
                        position.strategy,
                    "contracts":
                        position.contracts,
                    "base_value":
                        point
                        .base_strategy_value,
                    "stressed_value":
                        point
                        .stressed_strategy_value,
                    "stressed_pnl":
                        point.stressed_pnl,
                    "pnl_change":
                        point
                        .pnl_change_from_base,
                    "passed":
                        point.passed,
                    "rejections":
                        point
                        .rejection_reasons,
                })

            pnl_change = (
                total_stressed_pnl
                - total_base_pnl
            )

            loss_pct = (
                max(
                    -total_stressed_pnl,
                    0.0,
                )
                / initial_capital
                if initial_capital > 0
                else 0.0
            )

            scenario_rejections = []

            if (
                loss_pct
                > self.policy
                .maximum_portfolio_stress_loss_pct
            ):
                scenario_rejections.append(
                    "MAXIMUM_PORTFOLIO_STRESS_LOSS_EXCEEDED"
                )

            portfolio_points.append(
                PortfolioScenarioPoint(
                    scenario_name=(
                        scenario.name
                    ),
                    scenario_description=(
                        scenario.description
                    ),
                    total_base_value=round(
                        total_base_value,
                        2,
                    ),
                    total_stressed_value=round(
                        total_stressed_value,
                        2,
                    ),
                    total_stressed_pnl=round(
                        total_stressed_pnl,
                        2,
                    ),
                    pnl_change_from_base=round(
                        pnl_change,
                        2,
                    ),
                    loss_pct_of_portfolio_capital=round(
                        loss_pct,
                        4,
                    ),
                    position_results=(
                        position_results
                    ),
                    passed=(
                        not scenario_rejections
                    ),
                    rejection_reasons=(
                        scenario_rejections
                    ),
                )
            )

            rejection_reasons.extend(
                scenario_rejections
            )

        if not portfolio_points:
            return PortfolioScenarioResult(
                initial_capital=(
                    initial_capital
                ),
                position_count=len(
                    positions
                ),
                scenario_points=[],
                worst_scenario_name="",
                worst_scenario_pnl=0.0,
                worst_scenario_loss_pct=0.0,
                best_scenario_name="",
                best_scenario_pnl=0.0,
                maximum_stress_loss=0.0,
                average_scenario_pnl=0.0,
                stress_score=0.0,
                stress_grade="F",
                risk_severity="UNKNOWN",
                allowed=False,
                valid=False,
                rejection_reasons=[
                    "NO_PORTFOLIO_SCENARIOS"
                ],
                warnings=warnings,
                metadata={},
            )

        worst = min(
            portfolio_points,
            key=lambda point:
                point.total_stressed_pnl,
        )

        best = max(
            portfolio_points,
            key=lambda point:
                point.total_stressed_pnl,
        )

        maximum_stress_loss = max(
            -worst.total_stressed_pnl,
            0.0,
        )

        worst_loss_pct = (
            maximum_stress_loss
            / initial_capital
            if initial_capital > 0
            else 0.0
        )

        average_pnl = (
            sum(
                point.total_stressed_pnl
                for point in portfolio_points
            )
            / len(portfolio_points)
        )

        stress_score = self._stress_score(
            worst_loss_pct
        )

        unique_rejections = list(
            dict.fromkeys(
                rejection_reasons
            )
        )

        return PortfolioScenarioResult(
            initial_capital=round(
                initial_capital,
                2,
            ),
            position_count=len(
                positions
            ),
            scenario_points=(
                portfolio_points
            ),
            worst_scenario_name=(
                worst.scenario_name
            ),
            worst_scenario_pnl=round(
                worst.total_stressed_pnl,
                2,
            ),
            worst_scenario_loss_pct=round(
                worst_loss_pct,
                4,
            ),
            best_scenario_name=(
                best.scenario_name
            ),
            best_scenario_pnl=round(
                best.total_stressed_pnl,
                2,
            ),
            maximum_stress_loss=round(
                maximum_stress_loss,
                2,
            ),
            average_scenario_pnl=round(
                average_pnl,
                2,
            ),
            stress_score=round(
                stress_score,
                2,
            ),
            stress_grade=self._grade(
                stress_score
            ),
            risk_severity=self._severity(
                worst_loss_pct
            ),
            allowed=(
                not unique_rejections
            ),
            valid=True,
            rejection_reasons=(
                unique_rejections
            ),
            warnings=list(
                dict.fromkeys(
                    warnings
                )
            ),
            metadata={
                "scenario_count":
                    len(portfolio_points),
            },
        )

    def _structure_from_position(
        self,
        position,
    ):
        metadata = dict(
            getattr(
                position,
                "metadata",
                {},
            )
            or {}
        )

        structure = metadata.get(
            "strategy_structure"
        )

        if structure is not None:
            return structure

        opportunity = getattr(
            position,
            "source_opportunity",
            None,
        )

        if opportunity is None:
            return None

        opportunity_metadata = dict(
            getattr(
                opportunity,
                "metadata",
                {},
            )
            or {}
        )

        structure = opportunity_metadata.get(
            "strategy_structure"
        )

        if structure is not None:
            return structure

        payoff_profile = (
            opportunity_metadata.get(
                "payoff_profile"
            )
        )

        if payoff_profile is not None:
            return getattr(
                payoff_profile,
                "strategy_structure",
                None,
            )

        return getattr(
            opportunity.strike_candidate,
            "strategy_structure",
            None,
        )

    def _stress_score(
        self,
        worst_loss_pct,
    ):
        if worst_loss_pct >= 0.20:
            return 10.0

        if worst_loss_pct >= 0.15:
            return 30.0

        if worst_loss_pct >= 0.10:
            return 50.0

        if worst_loss_pct >= 0.08:
            return 65.0

        if worst_loss_pct >= 0.05:
            return 75.0

        if worst_loss_pct >= 0.02:
            return 85.0

        return 95.0

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

    def _severity(
        self,
        loss_pct,
    ):
        if (
            loss_pct
            >= self.policy
            .maximum_portfolio_stress_loss_pct
        ):
            return "CRITICAL"

        if (
            loss_pct
            >= self.policy
            .warning_portfolio_stress_loss_pct
        ):
            return "SEVERE"

        if loss_pct >= 0.04:
            return "MODERATE"

        return "LOW"
