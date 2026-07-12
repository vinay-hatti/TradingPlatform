import numpy as np

from trading_ai.strategy_engine.distribution_risk_engine import (
    DistributionRiskEngine,
)
from trading_ai.strategy_engine.distribution_risk_policy import (
    DistributionRiskPolicy,
)
from trading_ai.strategy_engine.distribution_risk_profile import (
    PortfolioRiskContribution,
    PortfolioTailRiskProfile,
)


class PortfolioTailRiskEngine:
    """
    Portfolio VaR, Expected Shortfall, and contribution engine.

    Input:
        pnl_matrix shape = observations x positions
    """

    def __init__(
        self,
        policy: DistributionRiskPolicy | None = None,
        distribution_engine: DistributionRiskEngine | None = None,
    ):
        self.policy = (
            policy
            or DistributionRiskPolicy()
        )

        self.distribution_engine = (
            distribution_engine
            or DistributionRiskEngine(
                policy=self.policy
            )
        )

    def analyze(
        self,
        pnl_matrix,
        position_metadata,
        initial_capital: float,
        weights=None,
    ) -> PortfolioTailRiskProfile:
        matrix = np.asarray(
            pnl_matrix,
            dtype=float,
        )

        if matrix.ndim != 2:
            raise ValueError(
                "pnl_matrix must be two-dimensional"
            )

        observations, position_count = (
            matrix.shape
        )

        if position_count == 0:
            return self._invalid_profile(
                initial_capital=initial_capital,
                reason="NO_PORTFOLIO_POSITIONS",
            )

        if len(position_metadata) != position_count:
            raise ValueError(
                "position_metadata length must match "
                "pnl_matrix columns"
            )

        matrix = np.where(
            np.isfinite(matrix),
            matrix,
            0.0,
        )

        if weights is None:
            weights_array = np.full(
                position_count,
                1.0,
            )
        else:
            weights_array = np.asarray(
                weights,
                dtype=float,
            )

            if weights_array.size != position_count:
                raise ValueError(
                    "weights length must match "
                    "pnl_matrix columns"
                )

        weighted_matrix = (
            matrix
            * weights_array
        )

        portfolio_pnl = np.sum(
            weighted_matrix,
            axis=1,
        )

        portfolio_profile = (
            self.distribution_engine
            .analyze(
                pnl_values=portfolio_pnl,
                capital_required=initial_capital,
                initial_capital=initial_capital,
                symbol="PORTFOLIO",
                strategy="MULTI_STRATEGY",
            )
        )

        standalone_var = []
        standalone_es = []

        for column in range(
            position_count
        ):
            profile = (
                self.distribution_engine
                .analyze(
                    pnl_values=(
                        weighted_matrix[
                            :,
                            column
                        ]
                    ),
                    capital_required=(
                        initial_capital
                    ),
                    initial_capital=(
                        initial_capital
                    ),
                    symbol=str(
                        position_metadata[
                            column
                        ].get(
                            "symbol",
                            "",
                        )
                    ),
                    strategy=str(
                        position_metadata[
                            column
                        ].get(
                            "strategy",
                            "",
                        )
                    ),
                )
            )

            standalone_var.append(
                profile.historical_var
            )

            standalone_es.append(
                profile
                .historical_expected_shortfall
            )

        marginal_var = self._marginal_risk(
            weighted_matrix=weighted_matrix,
            base_value=(
                portfolio_profile
                .historical_var
            ),
            initial_capital=initial_capital,
            risk_type="VAR",
        )

        marginal_es = self._marginal_risk(
            weighted_matrix=weighted_matrix,
            base_value=(
                portfolio_profile
                .historical_expected_shortfall
            ),
            initial_capital=initial_capital,
            risk_type="ES",
        )

        component_var = (
            marginal_var
            * weights_array
        )

        component_es = (
            marginal_es
            * weights_array
        )

        total_component_var = float(
            np.sum(
                np.abs(
                    component_var
                )
            )
        )

        total_component_es = float(
            np.sum(
                np.abs(
                    component_es
                )
            )
        )

        contributions = []

        for index, metadata in enumerate(
            position_metadata
        ):
            var_pct = (
                abs(component_var[index])
                / total_component_var
                if total_component_var > 0
                else 0.0
            )

            es_pct = (
                abs(component_es[index])
                / total_component_es
                if total_component_es > 0
                else 0.0
            )

            contributions.append(
                PortfolioRiskContribution(
                    position_id=str(
                        metadata.get(
                            "position_id",
                            index,
                        )
                    ),
                    symbol=str(
                        metadata.get(
                            "symbol",
                            "",
                        )
                    ).upper(),
                    strategy=str(
                        metadata.get(
                            "strategy",
                            "",
                        )
                    ).upper(),
                    weight=float(
                        weights_array[index]
                    ),
                    standalone_var=round(
                        standalone_var[index],
                        2,
                    ),
                    marginal_var=round(
                        float(
                            marginal_var[
                                index
                            ]
                        ),
                        2,
                    ),
                    component_var=round(
                        float(
                            component_var[
                                index
                            ]
                        ),
                        2,
                    ),
                    standalone_expected_shortfall=round(
                        standalone_es[index],
                        2,
                    ),
                    marginal_expected_shortfall=round(
                        float(
                            marginal_es[
                                index
                            ]
                        ),
                        2,
                    ),
                    component_expected_shortfall=round(
                        float(
                            component_es[
                                index
                            ]
                        ),
                        2,
                    ),
                    var_contribution_pct=round(
                        var_pct,
                        4,
                    ),
                    expected_shortfall_contribution_pct=round(
                        es_pct,
                        4,
                    ),
                    concentration_flag=(
                        var_pct > 0.40
                        or es_pct > 0.40
                    ),
                )
            )

        largest_var = max(
            contributions,
            key=lambda item:
                item.var_contribution_pct,
        )

        largest_es = max(
            contributions,
            key=lambda item:
                item
                .expected_shortfall_contribution_pct,
        )

        concentration_score = self._concentration_score(
            contributions
        )

        sum_standalone_var = float(
            np.sum(
                standalone_var
            )
        )

        diversification_benefit = (
            1.0
            - (
                portfolio_profile
                .historical_var
                / sum_standalone_var
            )
            if sum_standalone_var > 0
            else 0.0
        )

        rejection_reasons = list(
            portfolio_profile
            .rejection_reasons
        )

        return PortfolioTailRiskProfile(
            initial_capital=round(
                float(initial_capital),
                2,
            ),
            position_count=position_count,
            observation_count=observations,
            portfolio_var=(
                portfolio_profile
                .historical_var
            ),
            portfolio_expected_shortfall=(
                portfolio_profile
                .historical_expected_shortfall
            ),
            portfolio_var_99=(
                portfolio_profile
                .historical_var_99
            ),
            portfolio_expected_shortfall_99=(
                portfolio_profile
                .historical_expected_shortfall_99
            ),
            var_pct_of_capital=(
                portfolio_profile
                .var_pct_of_capital
            ),
            expected_shortfall_pct_of_capital=(
                portfolio_profile
                .expected_shortfall_pct_of_capital
            ),
            maximum_drawdown=(
                portfolio_profile
                .maximum_drawdown
            ),
            maximum_drawdown_pct=(
                portfolio_profile
                .maximum_drawdown_pct
            ),
            drawdown_at_risk=(
                portfolio_profile
                .drawdown_at_risk
            ),
            expected_drawdown_shortfall=(
                portfolio_profile
                .expected_drawdown_shortfall
            ),
            skewness=(
                portfolio_profile.skewness
            ),
            excess_kurtosis=(
                portfolio_profile
                .excess_kurtosis
            ),
            downside_deviation=(
                portfolio_profile
                .downside_deviation
            ),
            sortino_ratio=(
                portfolio_profile
                .sortino_ratio
            ),
            omega_ratio=(
                portfolio_profile
                .omega_ratio
            ),
            largest_var_contributor=(
                largest_var.symbol
            ),
            largest_es_contributor=(
                largest_es.symbol
            ),
            risk_concentration_score=round(
                concentration_score,
                2,
            ),
            diversification_benefit=round(
                diversification_benefit,
                4,
            ),
            contributions=contributions,
            tail_risk_score=(
                portfolio_profile
                .tail_risk_score
            ),
            tail_risk_grade=(
                portfolio_profile
                .tail_risk_grade
            ),
            risk_severity=(
                portfolio_profile
                .risk_severity
            ),
            allowed=(
                portfolio_profile.allowed
            ),
            valid=(
                portfolio_profile.valid
            ),
            rejection_reasons=(
                rejection_reasons
            ),
            warnings=list(
                portfolio_profile
                .warnings
            ),
            metadata={
                "sum_standalone_var":
                    round(
                        sum_standalone_var,
                        2,
                    ),
            },
        )

    def _marginal_risk(
        self,
        weighted_matrix,
        base_value,
        initial_capital,
        risk_type,
    ):
        epsilon = (
            self.policy
            .finite_difference_epsilon
        )

        position_count = (
            weighted_matrix.shape[1]
        )

        marginal = np.zeros(
            position_count,
            dtype=float,
        )

        for index in range(
            position_count
        ):
            shocked = (
                weighted_matrix.copy()
            )

            shocked[
                :,
                index
            ] *= (
                1.0 + epsilon
            )

            shocked_portfolio = np.sum(
                shocked,
                axis=1,
            )

            profile = (
                self.distribution_engine
                .analyze(
                    pnl_values=(
                        shocked_portfolio
                    ),
                    capital_required=(
                        initial_capital
                    ),
                    initial_capital=(
                        initial_capital
                    ),
                    symbol="PORTFOLIO",
                    strategy="MARGINAL_RISK",
                )
            )

            shocked_value = (
                profile.historical_var
                if risk_type == "VAR"
                else profile
                .historical_expected_shortfall
            )

            marginal[index] = (
                shocked_value
                - base_value
            ) / epsilon

        return marginal

    def _concentration_score(
        self,
        contributions,
    ):
        if not contributions:
            return 0.0

        percentages = np.asarray(
            [
                item
                .expected_shortfall_contribution_pct
                for item in contributions
            ],
            dtype=float,
        )

        herfindahl = float(
            np.sum(
                percentages ** 2
            )
        )

        minimum_hhi = (
            1.0 / len(contributions)
        )

        normalized = (
            (
                herfindahl
                - minimum_hhi
            )
            / (
                1.0
                - minimum_hhi
            )
            if len(contributions) > 1
            else 1.0
        )

        return max(
            0.0,
            min(
                100.0,
                normalized * 100.0,
            ),
        )

    def _invalid_profile(
        self,
        initial_capital,
        reason,
    ):
        return PortfolioTailRiskProfile(
            initial_capital=float(
                initial_capital
            ),
            position_count=0,
            observation_count=0,
            portfolio_var=0.0,
            portfolio_expected_shortfall=0.0,
            portfolio_var_99=0.0,
            portfolio_expected_shortfall_99=0.0,
            var_pct_of_capital=0.0,
            expected_shortfall_pct_of_capital=0.0,
            maximum_drawdown=0.0,
            maximum_drawdown_pct=0.0,
            drawdown_at_risk=0.0,
            expected_drawdown_shortfall=0.0,
            skewness=0.0,
            excess_kurtosis=0.0,
            downside_deviation=0.0,
            sortino_ratio=None,
            omega_ratio=None,
            largest_var_contributor="",
            largest_es_contributor="",
            risk_concentration_score=0.0,
            diversification_benefit=0.0,
            contributions=[],
            tail_risk_score=0.0,
            tail_risk_grade="F",
            risk_severity="UNKNOWN",
            allowed=False,
            valid=False,
            rejection_reasons=[
                reason
            ],
            warnings=[],
            metadata={},
        )
