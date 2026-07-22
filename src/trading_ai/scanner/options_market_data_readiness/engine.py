from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from .contracts import (
    GovernanceStatus,
    OptionDataReadinessProfile,
)
from .policy import OptionDataReadinessPolicy


@dataclass(frozen=True)
class CoverageInput:
    symbol: str
    status: str
    score: float
    contract_count: int
    expiration_count: int
    distinct_strike_count: int
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class QualityInput:
    symbol: str
    status: str
    score: float
    quote_data_observed: bool
    reasons: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


class OptionDataReadinessEngine:
    def __init__(
        self,
        policy: OptionDataReadinessPolicy | None = None,
    ) -> None:
        self.policy = policy or OptionDataReadinessPolicy()
        self.policy.validate()

    def evaluate(
        self,
        *,
        as_of_date: date,
        coverage_rows: Iterable[CoverageInput],
        quality_rows: Iterable[QualityInput],
    ) -> tuple[OptionDataReadinessProfile, ...]:
        coverage = {
            self._symbol(row.symbol): row
            for row in coverage_rows
        }
        quality = {
            self._symbol(row.symbol): row
            for row in quality_rows
        }

        symbols = sorted(set(coverage) | set(quality))
        return tuple(
            self._evaluate_symbol(
                symbol=symbol,
                as_of_date=as_of_date,
                coverage=coverage.get(symbol),
                quality=quality.get(symbol),
            )
            for symbol in symbols
        )

    def _evaluate_symbol(
        self,
        *,
        symbol: str,
        as_of_date: date,
        coverage: CoverageInput | None,
        quality: QualityInput | None,
    ) -> OptionDataReadinessProfile:
        coverage_status = self._status(
            coverage.status if coverage else "FAILED"
        )
        quality_status = self._status(
            quality.status if quality else "FAILED"
        )

        coverage_score = self.policy.clamp(
            coverage.score if coverage else 0.0
        )
        quality_score = self.policy.clamp(
            quality.score if quality else 0.0
        )

        total_weight = (
            self.policy.coverage_weight + self.policy.quality_weight
        )
        readiness_score = self.policy.clamp(
            (
                self.policy.coverage_weight * coverage_score
                + self.policy.quality_weight * quality_score
            )
            / total_weight
        )

        reasons: list[str] = []
        notes: list[str] = []

        if coverage is None:
            reasons.append("coverage profile missing")
        if quality is None:
            reasons.append("quality profile missing")

        if (
            self.policy.fail_if_coverage_failed
            and coverage_status == GovernanceStatus.FAILED
        ):
            reasons.append("coverage governance failed")

        if (
            self.policy.fail_if_quality_failed
            and quality_status == GovernanceStatus.FAILED
        ):
            reasons.append("quality governance failed")

        contract_count = coverage.contract_count if coverage else 0
        expiration_count = coverage.expiration_count if coverage else 0
        distinct_strike_count = (
            coverage.distinct_strike_count if coverage else 0
        )

        hard_failure = bool(reasons)

        if hard_failure:
            readiness_status = GovernanceStatus.FAILED
        else:
            if (
                readiness_score >= self.policy.ready_score
                and coverage_status == GovernanceStatus.READY
                and quality_status == GovernanceStatus.READY
                and contract_count
                >= self.policy.require_minimum_contracts_for_ready
                and expiration_count
                >= self.policy.require_minimum_expirations_for_ready
            ):
                readiness_status = GovernanceStatus.READY
            elif readiness_score >= self.policy.review_score:
                readiness_status = GovernanceStatus.REVIEW
                if coverage_status != GovernanceStatus.READY:
                    reasons.append(
                        f"coverage status {coverage_status.value}"
                    )
                if quality_status != GovernanceStatus.READY:
                    reasons.append(
                        f"quality status {quality_status.value}"
                    )
                if (
                    contract_count
                    < self.policy.require_minimum_contracts_for_ready
                ):
                    reasons.append(
                        f"contracts {contract_count} < "
                        f"{self.policy.require_minimum_contracts_for_ready}"
                    )
                if (
                    expiration_count
                    < self.policy.require_minimum_expirations_for_ready
                ):
                    reasons.append(
                        f"expirations {expiration_count} < "
                        f"{self.policy.require_minimum_expirations_for_ready}"
                    )
                if readiness_score < self.policy.ready_score:
                    reasons.append(
                        f"readiness score {readiness_score:.3f} < "
                        f"{self.policy.ready_score:.3f}"
                    )
            else:
                readiness_status = GovernanceStatus.FAILED
                reasons.append(
                    f"readiness score {readiness_score:.3f} < "
                    f"{self.policy.review_score:.3f}"
                )

        quote_data_observed = (
            quality.quote_data_observed if quality else False
        )
        provider_capability_limited = not quote_data_observed

        if provider_capability_limited:
            notes.append(
                "NBBO quote/spread data not observed; provider-aware "
                "quality score used"
            )

        if quality:
            notes.extend(quality.notes)

        return OptionDataReadinessProfile(
            symbol=symbol,
            as_of_date=as_of_date,
            coverage_status=coverage_status,
            quality_status=quality_status,
            readiness_status=readiness_status,
            coverage_score=round(coverage_score, 6),
            quality_score=round(quality_score, 6),
            readiness_score=round(readiness_score, 6),
            contract_count=contract_count,
            expiration_count=expiration_count,
            distinct_strike_count=distinct_strike_count,
            quote_data_observed=quote_data_observed,
            provider_capability_limited=provider_capability_limited,
            coverage_reasons=coverage.reasons if coverage else (),
            quality_reasons=quality.reasons if quality else (),
            readiness_reasons=tuple(reasons),
            informational_notes=tuple(dict.fromkeys(notes)),
        )

    @staticmethod
    def _status(value: str) -> GovernanceStatus:
        normalized = str(value).strip().upper()
        try:
            return GovernanceStatus(normalized)
        except ValueError:
            return GovernanceStatus.FAILED

    @staticmethod
    def _symbol(value: str) -> str:
        return str(value).strip().upper()
