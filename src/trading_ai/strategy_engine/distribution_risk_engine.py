import math
from statistics import NormalDist

import numpy as np

from trading_ai.strategy_engine.distribution_risk_policy import (
    DistributionRiskPolicy,
)
from trading_ai.strategy_engine.distribution_risk_profile import (
    DistributionRiskProfile,
)
from trading_ai.strategy_engine.drawdown_risk_engine import (
    DrawdownRiskEngine,
)


class DistributionRiskEngine:
    """
    Strategy-level distribution and tail-risk engine.
    """

    def __init__(
        self,
        policy: DistributionRiskPolicy | None = None,
        drawdown_engine: DrawdownRiskEngine | None = None,
    ):
        self.policy = (
            policy
            or DistributionRiskPolicy()
        )

        self.policy.validate()

        self.drawdown_engine = (
            drawdown_engine
            or DrawdownRiskEngine()
        )

    def analyze(
        self,
        pnl_values,
        capital_required: float,
        symbol: str = "",
        strategy: str = "",
        monte_carlo_pnl_values=None,
        initial_capital: float | None = None,
    ) -> DistributionRiskProfile:
        pnl = self._clean_array(
            pnl_values
        )

        mc_pnl = self._clean_array(
            monte_carlo_pnl_values
        )

        capital = float(
            capital_required or 0.0
        )

        account_capital = float(
            initial_capital
            if initial_capital is not None
            else capital
        )

        warnings = []
        rejection_reasons = []

        if pnl.size < 2:
            return self._invalid_profile(
                symbol=symbol,
                strategy=strategy,
                observation_count=int(
                    pnl.size
                ),
                reason="INSUFFICIENT_DISTRIBUTION_OBSERVATIONS",
            )

        if (
            pnl.size
            < self.policy.minimum_observations
        ):
            warnings.append(
                "Observation count below institutional minimum"
            )

            if (
                self.policy
                .reject_insufficient_observations
            ):
                rejection_reasons.append(
                    "INSUFFICIENT_DISTRIBUTION_OBSERVATIONS"
                )

        returns = (
            pnl / capital
            if capital > 0
            else np.zeros_like(pnl)
        )

        mean_pnl = float(
            np.mean(pnl)
        )

        median_pnl = float(
            np.median(pnl)
        )

        pnl_std = float(
            np.std(
                pnl,
                ddof=1,
            )
        )

        mean_return = float(
            np.mean(returns)
        )

        annualized_return = (
            mean_return
            * self.policy
            .annualization_factor
        )

        annualized_volatility = (
            float(
                np.std(
                    returns,
                    ddof=1,
                )
            )
            * math.sqrt(
                self.policy
                .annualization_factor
            )
        )

        downside = returns[
            returns
            < self.policy.downside_target_return
        ]

        downside_deviation = (
            float(
                np.sqrt(
                    np.mean(
                        np.square(
                            downside
                            - self.policy
                            .downside_target_return
                        )
                    )
                )
            )
            if downside.size
            else 0.0
        )

        semi_variance = (
            float(
                np.mean(
                    np.square(
                        downside
                        - self.policy
                        .downside_target_return
                    )
                )
            )
            if downside.size
            else 0.0
        )

        skewness = self._skewness(
            pnl
        )

        excess_kurtosis = self._excess_kurtosis(
            pnl
        )

        historical_var, historical_es = (
            self._historical_var_es(
                pnl,
                self.policy.confidence_level,
            )
        )

        historical_var_99, historical_es_99 = (
            self._historical_var_es(
                pnl,
                self.policy
                .secondary_confidence_level,
            )
        )

        parametric_var, parametric_es = (
            self._parametric_var_es(
                mean=mean_pnl,
                stddev=pnl_std,
                confidence_level=(
                    self.policy
                    .confidence_level
                ),
            )
        )

        monte_carlo_var = None
        monte_carlo_es = None

        if mc_pnl.size:
            (
                monte_carlo_var,
                monte_carlo_es,
            ) = self._historical_var_es(
                mc_pnl,
                self.policy.confidence_level,
            )

        probability_of_loss = float(
            np.mean(pnl < 0)
        )

        probability_of_large_loss = (
            self._loss_probability(
                pnl=pnl,
                capital=capital,
                threshold=(
                    self.policy
                    .large_loss_threshold_pct
                ),
            )
        )

        probability_of_severe_loss = (
            self._loss_probability(
                pnl=pnl,
                capital=capital,
                threshold=(
                    self.policy
                    .severe_loss_threshold_pct
                ),
            )
        )

        probability_of_critical_loss = (
            self._loss_probability(
                pnl=pnl,
                capital=capital,
                threshold=(
                    self.policy
                    .critical_loss_threshold_pct
                ),
            )
        )

        gains = pnl[
            pnl > 0
        ]

        losses = pnl[
            pnl < 0
        ]

        average_gain = (
            float(np.mean(gains))
            if gains.size
            else 0.0
        )

        average_loss = (
            float(np.mean(losses))
            if losses.size
            else 0.0
        )

        gain_loss_ratio = (
            average_gain
            / abs(average_loss)
            if average_loss < 0
            else None
        )

        payoff_ratio = gain_loss_ratio

        gross_profit = float(
            np.sum(gains)
        )

        gross_loss = abs(
            float(
                np.sum(losses)
            )
        )

        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else None
        )

        omega_ratio = self._omega_ratio(
            returns
        )

        sortino_ratio = self._sortino_ratio(
            annualized_return=annualized_return,
            downside_deviation=(
                downside_deviation
            ),
        )

        gain_to_pain_ratio = (
            float(np.sum(pnl))
            / float(
                np.sum(
                    np.abs(
                        pnl[pnl < 0]
                    )
                )
            )
            if np.any(pnl < 0)
            else None
        )

        drawdown = self.drawdown_engine.analyze(
            pnl_values=pnl,
            confidence_level=(
                self.policy
                .confidence_level
            ),
            initial_capital=account_capital,
        )

        tail_loss_ratio = (
            historical_es
            / historical_var
            if historical_var > 0
            else None
        )

        upper_quantile = float(
            np.quantile(
                pnl,
                self.policy.confidence_level,
            )
        )

        lower_quantile = float(
            np.quantile(
                pnl,
                1.0
                - self.policy
                .confidence_level,
            )
        )

        tail_asymmetry_ratio = (
            abs(lower_quantile)
            / upper_quantile
            if upper_quantile > 0
            else None
        )

        var_pct_of_capital = (
            historical_var
            / account_capital
            if account_capital > 0
            else 0.0
        )

        es_pct_of_capital = (
            historical_es
            / account_capital
            if account_capital > 0
            else 0.0
        )

        if (
            var_pct_of_capital
            > self.policy
            .maximum_var_pct_of_capital
        ):
            rejection_reasons.append(
                "VALUE_AT_RISK_LIMIT_EXCEEDED"
            )

        if (
            es_pct_of_capital
            > self.policy
            .maximum_expected_shortfall_pct_of_capital
        ):
            rejection_reasons.append(
                "EXPECTED_SHORTFALL_LIMIT_EXCEEDED"
            )

        if (
            drawdown["drawdown_at_risk"]
            > self.policy
            .maximum_drawdown_at_risk_pct
        ):
            rejection_reasons.append(
                "DRAWDOWN_AT_RISK_LIMIT_EXCEEDED"
            )

        if (
            skewness
            < self.policy.maximum_negative_skew
        ):
            warnings.append(
                "Distribution has excessive negative skew"
            )

        if (
            excess_kurtosis
            > self.policy.maximum_excess_kurtosis
        ):
            warnings.append(
                "Distribution has excessive tail kurtosis"
            )

        if (
            sortino_ratio is not None
            and sortino_ratio
            < self.policy.minimum_sortino_ratio
        ):
            warnings.append(
                "Sortino ratio below preferred minimum"
            )

        if (
            omega_ratio is not None
            and omega_ratio
            < self.policy.minimum_omega_ratio
        ):
            warnings.append(
                "Omega ratio below preferred minimum"
            )

        rejection_reasons = list(
            dict.fromkeys(
                rejection_reasons
            )
        )

        if (
            not self.policy
            .reject_tail_limit_breaches
        ):
            warnings.extend(
                rejection_reasons
            )
            rejection_reasons = []

        tail_risk_score = self._tail_risk_score(
            var_pct=var_pct_of_capital,
            es_pct=es_pct_of_capital,
            drawdown_at_risk=(
                drawdown[
                    "drawdown_at_risk"
                ]
            ),
            skewness=skewness,
            excess_kurtosis=(
                excess_kurtosis
            ),
            probability_of_large_loss=(
                probability_of_large_loss
            ),
            observation_count=int(
                pnl.size
            ),
        )

        return DistributionRiskProfile(
            symbol=str(
                symbol or ""
            ).upper(),
            strategy=str(
                strategy or ""
            ).upper(),
            observation_count=int(
                pnl.size
            ),
            confidence_level=(
                self.policy
                .confidence_level
            ),
            secondary_confidence_level=(
                self.policy
                .secondary_confidence_level
            ),
            mean_pnl=round(
                mean_pnl,
                2,
            ),
            median_pnl=round(
                median_pnl,
                2,
            ),
            pnl_standard_deviation=round(
                pnl_std,
                2,
            ),
            mean_return=round(
                mean_return,
                6,
            ),
            annualized_return=round(
                annualized_return,
                6,
            ),
            annualized_volatility=round(
                annualized_volatility,
                6,
            ),
            downside_deviation=round(
                downside_deviation,
                6,
            ),
            semi_variance=round(
                semi_variance,
                8,
            ),
            skewness=round(
                skewness,
                4,
            ),
            excess_kurtosis=round(
                excess_kurtosis,
                4,
            ),
            historical_var=round(
                historical_var,
                2,
            ),
            historical_expected_shortfall=round(
                historical_es,
                2,
            ),
            parametric_var=round(
                parametric_var,
                2,
            ),
            parametric_expected_shortfall=round(
                parametric_es,
                2,
            ),
            monte_carlo_var=(
                round(
                    monte_carlo_var,
                    2,
                )
                if monte_carlo_var
                is not None
                else None
            ),
            monte_carlo_expected_shortfall=(
                round(
                    monte_carlo_es,
                    2,
                )
                if monte_carlo_es
                is not None
                else None
            ),
            historical_var_99=round(
                historical_var_99,
                2,
            ),
            historical_expected_shortfall_99=round(
                historical_es_99,
                2,
            ),
            probability_of_loss=round(
                probability_of_loss,
                4,
            ),
            probability_of_large_loss=round(
                probability_of_large_loss,
                4,
            ),
            probability_of_severe_loss=round(
                probability_of_severe_loss,
                4,
            ),
            probability_of_critical_loss=round(
                probability_of_critical_loss,
                4,
            ),
            average_gain=round(
                average_gain,
                2,
            ),
            average_loss=round(
                average_loss,
                2,
            ),
            gain_loss_ratio=(
                round(
                    gain_loss_ratio,
                    4,
                )
                if gain_loss_ratio
                is not None
                else None
            ),
            payoff_ratio=(
                round(
                    payoff_ratio,
                    4,
                )
                if payoff_ratio
                is not None
                else None
            ),
            profit_factor=(
                round(
                    profit_factor,
                    4,
                )
                if profit_factor
                is not None
                else None
            ),
            omega_ratio=(
                round(
                    omega_ratio,
                    4,
                )
                if omega_ratio
                is not None
                else None
            ),
            sortino_ratio=(
                round(
                    sortino_ratio,
                    4,
                )
                if sortino_ratio
                is not None
                else None
            ),
            gain_to_pain_ratio=(
                round(
                    gain_to_pain_ratio,
                    4,
                )
                if gain_to_pain_ratio
                is not None
                else None
            ),
            maximum_drawdown=round(
                drawdown[
                    "maximum_drawdown"
                ],
                2,
            ),
            maximum_drawdown_pct=round(
                drawdown[
                    "maximum_drawdown_pct"
                ],
                4,
            ),
            average_drawdown_pct=round(
                drawdown[
                    "average_drawdown_pct"
                ],
                4,
            ),
            drawdown_at_risk=round(
                drawdown[
                    "drawdown_at_risk"
                ],
                4,
            ),
            expected_drawdown_shortfall=round(
                drawdown[
                    "expected_drawdown_shortfall"
                ],
                4,
            ),
            ulcer_index=round(
                drawdown[
                    "ulcer_index"
                ],
                4,
            ),
            pain_index=round(
                drawdown[
                    "pain_index"
                ],
                4,
            ),
            tail_loss_ratio=(
                round(
                    tail_loss_ratio,
                    4,
                )
                if tail_loss_ratio
                is not None
                else None
            ),
            tail_asymmetry_ratio=(
                round(
                    tail_asymmetry_ratio,
                    4,
                )
                if tail_asymmetry_ratio
                is not None
                else None
            ),
            var_pct_of_capital=round(
                var_pct_of_capital,
                4,
            ),
            expected_shortfall_pct_of_capital=round(
                es_pct_of_capital,
                4,
            ),
            tail_risk_score=round(
                tail_risk_score,
                2,
            ),
            tail_risk_grade=self._grade(
                tail_risk_score
            ),
            risk_severity=self._severity(
                es_pct_of_capital
            ),
            allowed=(
                not rejection_reasons
            ),
            valid=True,
            rejection_reasons=(
                rejection_reasons
            ),
            warnings=list(
                dict.fromkeys(
                    warnings
                )
            ),
            metadata={
                "capital_required":
                    capital,
                "initial_capital":
                    account_capital,
                "equity_curve":
                    drawdown[
                        "equity_curve"
                    ],
                "drawdown_curve":
                    drawdown[
                        "drawdown_curve"
                    ],
            },
        )

    def _historical_var_es(
        self,
        pnl,
        confidence_level,
    ) -> tuple[float, float]:
        loss_values = -np.asarray(
            pnl,
            dtype=float,
        )

        var = float(
            np.quantile(
                loss_values,
                confidence_level,
            )
        )

        tail = loss_values[
            loss_values >= var
        ]

        expected_shortfall = (
            float(np.mean(tail))
            if tail.size
            else var
        )

        return (
            max(var, 0.0),
            max(
                expected_shortfall,
                0.0,
            ),
        )

    def _parametric_var_es(
        self,
        mean,
        stddev,
        confidence_level,
    ) -> tuple[float, float]:
        if stddev <= 0:
            return (
                max(-mean, 0.0),
                max(-mean, 0.0),
            )

        normal = NormalDist()

        z = normal.inv_cdf(
            confidence_level
        )

        density = (
            math.exp(
                -0.5 * z * z
            )
            / math.sqrt(
                2.0 * math.pi
            )
        )

        var = (
            -mean
            + z * stddev
        )

        expected_shortfall = (
            -mean
            + stddev
            * density
            / (
                1.0
                - confidence_level
            )
        )

        return (
            max(var, 0.0),
            max(
                expected_shortfall,
                0.0,
            ),
        )

    def _skewness(
        self,
        values,
    ) -> float:
        values = np.asarray(
            values,
            dtype=float,
        )

        n = values.size

        if n < 3:
            return 0.0

        stddev = float(
            np.std(
                values,
                ddof=1,
            )
        )

        if stddev == 0:
            return 0.0

        mean = float(
            np.mean(values)
        )

        standardized = (
            values - mean
        ) / stddev

        return float(
            n
            / (
                (n - 1)
                * (n - 2)
            )
            * np.sum(
                standardized ** 3
            )
        )

    def _excess_kurtosis(
        self,
        values,
    ) -> float:
        values = np.asarray(
            values,
            dtype=float,
        )

        n = values.size

        if n < 4:
            return 0.0

        stddev = float(
            np.std(
                values,
                ddof=1,
            )
        )

        if stddev == 0:
            return 0.0

        mean = float(
            np.mean(values)
        )

        standardized = (
            values - mean
        ) / stddev

        first = (
            n
            * (n + 1)
            / (
                (n - 1)
                * (n - 2)
                * (n - 3)
            )
            * np.sum(
                standardized ** 4
            )
        )

        second = (
            3
            * (n - 1) ** 2
            / (
                (n - 2)
                * (n - 3)
            )
        )

        return float(
            first - second
        )

    def _omega_ratio(
        self,
        returns,
    ) -> float | None:
        threshold = (
            self.policy
            .omega_threshold_return
        )

        gains = np.maximum(
            returns - threshold,
            0.0,
        )

        losses = np.maximum(
            threshold - returns,
            0.0,
        )

        denominator = float(
            np.sum(losses)
        )

        if denominator <= 0:
            return None

        return float(
            np.sum(gains)
            / denominator
        )

    def _sortino_ratio(
        self,
        annualized_return,
        downside_deviation,
    ) -> float | None:
        if downside_deviation <= 0:
            return None

        annualized_downside = (
            downside_deviation
            * math.sqrt(
                self.policy
                .annualization_factor
            )
        )

        annual_risk_free = (
            self.policy
            .risk_free_rate
        )

        return (
            annualized_return
            - annual_risk_free
        ) / annualized_downside

    def _loss_probability(
        self,
        pnl,
        capital,
        threshold,
    ) -> float:
        if capital <= 0:
            return 0.0

        loss_limit = (
            -capital * threshold
        )

        return float(
            np.mean(
                pnl <= loss_limit
            )
        )

    def _tail_risk_score(
        self,
        var_pct,
        es_pct,
        drawdown_at_risk,
        skewness,
        excess_kurtosis,
        probability_of_large_loss,
        observation_count,
    ) -> float:
        score = 100.0

        if var_pct > 0.10:
            score -= 30.0
        elif var_pct > 0.05:
            score -= 20.0
        elif var_pct > 0.03:
            score -= 10.0

        if es_pct > 0.15:
            score -= 30.0
        elif es_pct > 0.08:
            score -= 20.0
        elif es_pct > 0.05:
            score -= 10.0

        if drawdown_at_risk > 0.20:
            score -= 20.0
        elif drawdown_at_risk > 0.12:
            score -= 12.0
        elif drawdown_at_risk > 0.08:
            score -= 6.0

        if skewness < -2.0:
            score -= 12.0
        elif skewness < -1.0:
            score -= 7.0
        elif skewness < -0.5:
            score -= 3.0

        if excess_kurtosis > 10:
            score -= 12.0
        elif excess_kurtosis > 5:
            score -= 7.0
        elif excess_kurtosis > 3:
            score -= 3.0

        if probability_of_large_loss > 0.20:
            score -= 15.0
        elif probability_of_large_loss > 0.10:
            score -= 8.0
        elif probability_of_large_loss > 0.05:
            score -= 4.0

        if (
            observation_count
            < self.policy.minimum_observations
        ):
            score -= 10.0
        elif (
            observation_count
            < self.policy.preferred_observations
        ):
            score -= 5.0

        return max(
            0.0,
            min(
                100.0,
                score,
            ),
        )

    def _grade(
        self,
        score,
    ) -> str:
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
        expected_shortfall_pct,
    ) -> str:
        if expected_shortfall_pct >= 0.20:
            return "CRITICAL"

        if expected_shortfall_pct >= 0.10:
            return "SEVERE"

        if expected_shortfall_pct >= 0.05:
            return "MODERATE"

        return "LOW"

    def _clean_array(
        self,
        values,
    ) -> np.ndarray:
        if values is None:
            return np.asarray(
                [],
                dtype=float,
            )

        array = np.asarray(
            values,
            dtype=float,
        ).reshape(-1)

        return array[
            np.isfinite(array)
        ]

    def _invalid_profile(
        self,
        symbol,
        strategy,
        observation_count,
        reason,
    ) -> DistributionRiskProfile:
        return DistributionRiskProfile(
            symbol=str(
                symbol or ""
            ).upper(),
            strategy=str(
                strategy or ""
            ).upper(),
            observation_count=(
                observation_count
            ),
            confidence_level=(
                self.policy
                .confidence_level
            ),
            secondary_confidence_level=(
                self.policy
                .secondary_confidence_level
            ),
            mean_pnl=0.0,
            median_pnl=0.0,
            pnl_standard_deviation=0.0,
            mean_return=0.0,
            annualized_return=0.0,
            annualized_volatility=0.0,
            downside_deviation=0.0,
            semi_variance=0.0,
            skewness=0.0,
            excess_kurtosis=0.0,
            historical_var=0.0,
            historical_expected_shortfall=0.0,
            parametric_var=0.0,
            parametric_expected_shortfall=0.0,
            monte_carlo_var=None,
            monte_carlo_expected_shortfall=None,
            historical_var_99=0.0,
            historical_expected_shortfall_99=0.0,
            probability_of_loss=0.0,
            probability_of_large_loss=0.0,
            probability_of_severe_loss=0.0,
            probability_of_critical_loss=0.0,
            average_gain=0.0,
            average_loss=0.0,
            gain_loss_ratio=None,
            payoff_ratio=None,
            profit_factor=None,
            omega_ratio=None,
            sortino_ratio=None,
            gain_to_pain_ratio=None,
            maximum_drawdown=0.0,
            maximum_drawdown_pct=0.0,
            average_drawdown_pct=0.0,
            drawdown_at_risk=0.0,
            expected_drawdown_shortfall=0.0,
            ulcer_index=0.0,
            pain_index=0.0,
            tail_loss_ratio=None,
            tail_asymmetry_ratio=None,
            var_pct_of_capital=0.0,
            expected_shortfall_pct_of_capital=0.0,
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
