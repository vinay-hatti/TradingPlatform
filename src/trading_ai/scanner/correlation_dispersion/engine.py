from __future__ import annotations

from datetime import date
from itertools import combinations
from math import sqrt
from statistics import mean, median, pstdev
from typing import Any, Mapping, Sequence

from .contracts import (
    CorrelationDispersionGovernanceStatus,
    CorrelationDispersionProfile,
    PairCorrelationProfile,
)
from .policy import CorrelationDispersionPolicy


class CorrelationDispersionEngine:
    def __init__(
        self,
        policy: CorrelationDispersionPolicy | None = None,
    ) -> None:
        self.policy = policy or CorrelationDispersionPolicy()

    def evaluate(
        self,
        *,
        as_of_date: date,
        features_by_symbol: Mapping[str, Mapping[str, Any]],
        return_history_by_symbol: Mapping[str, Sequence[float]],
    ) -> CorrelationDispersionProfile:
        governed_symbols = sorted(
            symbol
            for symbol, record in features_by_symbol.items()
            if record.get("governance_status") in {"READY", "REVIEW"}
            and return_history_by_symbol.get(symbol)
        )

        status, reasons = self._govern_symbol_count(
            len(governed_symbols)
        )

        pair_profiles: list[PairCorrelationProfile] = []
        for left_symbol, right_symbol in combinations(
            governed_symbols,
            2,
        ):
            left = list(return_history_by_symbol[left_symbol])
            right = list(return_history_by_symbol[right_symbol])
            pair_profiles.append(
                self._pair_profile(
                    left_symbol=left_symbol,
                    right_symbol=right_symbol,
                    left_returns=left,
                    right_returns=right,
                )
            )

        valid_21 = [
            profile.correlation_21d
            for profile in pair_profiles
            if profile.correlation_21d is not None
        ]
        valid_abs_21 = [abs(value) for value in valid_21]
        valid_stability = [
            profile.stability_score
            for profile in pair_profiles
            if profile.stability_score is not None
        ]

        average_correlation = mean(valid_21) if valid_21 else None
        average_absolute_correlation = (
            mean(valid_abs_21) if valid_abs_21 else None
        )
        median_correlation = median(valid_21) if valid_21 else None
        stability_score = (
            mean(valid_stability) if valid_stability else None
        )

        breakdown_profiles = [
            profile
            for profile in pair_profiles
            if profile.breakdown_detected
        ]
        pair_count = len(pair_profiles)
        breakdown_ratio = (
            len(breakdown_profiles) / pair_count
            if pair_count
            else 0.0
        )

        if (
            status == CorrelationDispersionGovernanceStatus.READY
            and breakdown_ratio
            > self.policy.maximum_breakdown_ratio_ready
        ):
            status = CorrelationDispersionGovernanceStatus.REVIEW
            reasons.append(
                f"correlation breakdown ratio {breakdown_ratio:.6f} > "
                f"{self.policy.maximum_breakdown_ratio_ready:.6f}"
            )

        if (
            breakdown_ratio
            > self.policy.maximum_breakdown_ratio_review
        ):
            status = CorrelationDispersionGovernanceStatus.EXCLUDED
            reasons.append(
                f"correlation breakdown ratio {breakdown_ratio:.6f} > "
                f"{self.policy.maximum_breakdown_ratio_review:.6f}"
            )

        dispersion_1d = self._cross_sectional_dispersion(
            features_by_symbol,
            governed_symbols,
            "return_1d",
        )
        dispersion_5d = self._cross_sectional_dispersion(
            features_by_symbol,
            governed_symbols,
            "return_5d",
        )
        dispersion_21d = self._cross_sectional_dispersion(
            features_by_symbol,
            governed_symbols,
            "return_21d",
        )
        dispersion_change = (
            dispersion_1d - dispersion_21d
            if dispersion_1d is not None
            and dispersion_21d is not None
            else None
        )

        diversification_score = (
            max(
                0.0,
                min(
                    1.0,
                    1.0 - average_absolute_correlation,
                ),
            )
            if average_absolute_correlation is not None
            else 0.0
        )
        concentration_risk_score = 1.0 - diversification_score

        correlation_regime = self._correlation_regime(
            average_absolute_correlation
        )
        dispersion_regime = self._dispersion_regime(
            dispersion_21d
        )
        market_structure_state = self._market_structure_state(
            correlation_regime=correlation_regime,
            dispersion_regime=dispersion_regime,
            breakdown_ratio=breakdown_ratio,
        )

        completeness = min(
            1.0,
            len(governed_symbols) / self.policy.minimum_symbols_ready,
        )
        stability_component = (
            stability_score
            if stability_score is not None
            else 0.0
        )
        confidence = completeness * max(
            0.0,
            min(1.0, stability_component * (1.0 - breakdown_ratio)),
        )

        valid_pairs = [
            profile
            for profile in pair_profiles
            if profile.correlation_21d is not None
        ]
        strongest_positive = sorted(
            valid_pairs,
            key=lambda profile: (
                -(profile.correlation_21d or -1.0),
                profile.left_symbol,
                profile.right_symbol,
            ),
        )[: self.policy.strongest_pair_count]
        strongest_negative = sorted(
            valid_pairs,
            key=lambda profile: (
                profile.correlation_21d or 1.0,
                profile.left_symbol,
                profile.right_symbol,
            ),
        )[: self.policy.strongest_pair_count]

        return CorrelationDispersionProfile(
            as_of_date=as_of_date,
            symbol_count=len(features_by_symbol),
            governed_symbol_count=len(governed_symbols),
            pair_count=pair_count,
            average_correlation_21d=average_correlation,
            average_absolute_correlation_21d=average_absolute_correlation,
            median_correlation_21d=median_correlation,
            correlation_stability_score=stability_score,
            correlation_breakdown_count=len(breakdown_profiles),
            correlation_breakdown_ratio=breakdown_ratio,
            cross_sectional_dispersion_1d=dispersion_1d,
            cross_sectional_dispersion_5d=dispersion_5d,
            cross_sectional_dispersion_21d=dispersion_21d,
            dispersion_change=dispersion_change,
            diversification_score=diversification_score,
            concentration_risk_score=concentration_risk_score,
            correlation_regime=correlation_regime,
            dispersion_regime=dispersion_regime,
            market_structure_state=market_structure_state,
            confidence=confidence,
            strongest_positive_pairs=tuple(
                self._pair_name(profile)
                for profile in strongest_positive
            ),
            strongest_negative_pairs=tuple(
                self._pair_name(profile)
                for profile in strongest_negative
            ),
            breakdown_pairs=tuple(
                self._pair_name(profile)
                for profile in breakdown_profiles
            ),
            pair_profiles=tuple(pair_profiles),
            governance_status=status,
            governance_reasons=tuple(reasons),
        )

    def _pair_profile(
        self,
        *,
        left_symbol: str,
        right_symbol: str,
        left_returns: list[float],
        right_returns: list[float],
    ) -> PairCorrelationProfile:
        count = min(len(left_returns), len(right_returns))
        left = left_returns[-count:]
        right = right_returns[-count:]

        correlation_21d = self._correlation(
            left[-21:],
            right[-21:],
            self.policy.minimum_pair_observations_21d,
        )
        correlation_63d = self._correlation(
            left[-63:],
            right[-63:],
            self.policy.minimum_pair_observations_63d,
        )

        change = (
            correlation_21d - correlation_63d
            if correlation_21d is not None
            and correlation_63d is not None
            else None
        )
        stability = (
            max(0.0, 1.0 - abs(change) / 2.0)
            if change is not None
            else None
        )
        breakdown = (
            change is not None
            and abs(change)
            >= self.policy.breakdown_change_threshold
        )

        if correlation_21d is None:
            relationship_state = "NOT_OBSERVED"
        elif correlation_21d >= self.policy.high_correlation_threshold:
            relationship_state = "STRONGLY_POSITIVE"
        elif correlation_21d <= -self.policy.high_correlation_threshold:
            relationship_state = "STRONGLY_NEGATIVE"
        elif abs(correlation_21d) <= self.policy.low_correlation_threshold:
            relationship_state = "DIVERSIFYING"
        elif correlation_21d > 0:
            relationship_state = "MODERATELY_POSITIVE"
        else:
            relationship_state = "MODERATELY_NEGATIVE"

        return PairCorrelationProfile(
            left_symbol=left_symbol,
            right_symbol=right_symbol,
            observation_count=count,
            correlation_21d=correlation_21d,
            correlation_63d=correlation_63d,
            correlation_change=change,
            stability_score=stability,
            breakdown_detected=breakdown,
            relationship_state=relationship_state,
        )

    @staticmethod
    def _correlation(
        left: Sequence[float],
        right: Sequence[float],
        minimum_observations: int,
    ) -> float | None:
        count = min(len(left), len(right))
        if count < minimum_observations:
            return None

        x = list(left[-count:])
        y = list(right[-count:])
        x_mean = mean(x)
        y_mean = mean(y)

        x_variance = sum(
            (value - x_mean) ** 2
            for value in x
        )
        y_variance = sum(
            (value - y_mean) ** 2
            for value in y
        )
        denominator = sqrt(x_variance * y_variance)

        if denominator == 0:
            return None

        covariance = sum(
            (x[index] - x_mean) * (y[index] - y_mean)
            for index in range(count)
        )
        return covariance / denominator

    @staticmethod
    def _cross_sectional_dispersion(
        features_by_symbol: Mapping[str, Mapping[str, Any]],
        symbols: Sequence[str],
        field_name: str,
    ) -> float | None:
        values = [
            float(features_by_symbol[symbol][field_name])
            for symbol in symbols
            if features_by_symbol[symbol].get(field_name) is not None
        ]
        return pstdev(values) if len(values) >= 2 else None

    def _correlation_regime(
        self,
        average_absolute_correlation: float | None,
    ) -> str:
        if average_absolute_correlation is None:
            return "NOT_OBSERVED"
        if (
            average_absolute_correlation
            >= self.policy.high_correlation_threshold
        ):
            return "HIGH_CORRELATION"
        if (
            average_absolute_correlation
            <= self.policy.low_correlation_threshold
        ):
            return "LOW_CORRELATION"
        return "NORMAL_CORRELATION"

    def _dispersion_regime(
        self,
        dispersion_21d: float | None,
    ) -> str:
        if dispersion_21d is None:
            return "NOT_OBSERVED"
        if dispersion_21d >= self.policy.high_dispersion_threshold:
            return "HIGH_DISPERSION"
        if dispersion_21d <= self.policy.low_dispersion_threshold:
            return "LOW_DISPERSION"
        return "NORMAL_DISPERSION"

    @staticmethod
    def _market_structure_state(
        *,
        correlation_regime: str,
        dispersion_regime: str,
        breakdown_ratio: float,
    ) -> str:
        if breakdown_ratio >= 0.30:
            return "CORRELATION_BREAKDOWN"
        if (
            correlation_regime == "HIGH_CORRELATION"
            and dispersion_regime == "LOW_DISPERSION"
        ):
            return "MACRO_DOMINATED"
        if (
            correlation_regime == "LOW_CORRELATION"
            and dispersion_regime == "HIGH_DISPERSION"
        ):
            return "SECURITY_SELECTION"
        if dispersion_regime == "HIGH_DISPERSION":
            return "ROTATION"
        if correlation_regime == "HIGH_CORRELATION":
            return "SYSTEMIC"
        return "BALANCED"

    def _govern_symbol_count(
        self,
        count: int,
    ) -> tuple[CorrelationDispersionGovernanceStatus, list[str]]:
        if count < self.policy.minimum_symbols_review:
            return (
                CorrelationDispersionGovernanceStatus.EXCLUDED,
                [
                    f"governed symbol count {count} < "
                    f"{self.policy.minimum_symbols_review}"
                ],
            )
        if count < self.policy.minimum_symbols_ready:
            return (
                CorrelationDispersionGovernanceStatus.REVIEW,
                [
                    f"governed symbol count {count} < "
                    f"{self.policy.minimum_symbols_ready}"
                ],
            )
        return CorrelationDispersionGovernanceStatus.READY, []

    @staticmethod
    def _pair_name(profile: PairCorrelationProfile) -> str:
        return f"{profile.left_symbol}:{profile.right_symbol}"
