from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from statistics import median
from typing import Iterable, Mapping, Sequence

from .contracts import (
    ExpirationCoverageProfile,
    GovernanceStatus,
    OptionChainCoverageProfile,
)
from .policy import OptionChainCoveragePolicy


@dataclass(frozen=True)
class OptionContractCoverageRow:
    underlying_symbol: str
    quote_date: date
    expiry: date
    option_type: str
    strike: float


class OptionChainCoverageEngine:
    def __init__(
        self,
        policy: OptionChainCoveragePolicy | None = None,
    ) -> None:
        self.policy = policy or OptionChainCoveragePolicy()

    def evaluate(
        self,
        rows: Iterable[OptionContractCoverageRow],
        *,
        quote_date: date,
        expected_symbols: Sequence[str] | None = None,
    ) -> tuple[OptionChainCoverageProfile, ...]:
        grouped: dict[str, list[OptionContractCoverageRow]] = defaultdict(list)

        for row in rows:
            symbol = str(row.underlying_symbol).strip().upper()
            if not symbol:
                continue
            grouped[symbol].append(row)

        if expected_symbols is not None:
            for symbol in expected_symbols:
                normalized = str(symbol).strip().upper()
                if normalized:
                    grouped.setdefault(normalized, [])

        return tuple(
            self._evaluate_symbol(
                symbol=symbol,
                rows=grouped[symbol],
                quote_date=quote_date,
            )
            for symbol in sorted(grouped)
        )

    def _evaluate_symbol(
        self,
        *,
        symbol: str,
        rows: Sequence[OptionContractCoverageRow],
        quote_date: date,
    ) -> OptionChainCoverageProfile:
        expiration_groups: dict[date, list[OptionContractCoverageRow]] = defaultdict(list)
        for row in rows:
            expiration_groups[row.expiry].append(row)

        expiration_profiles = tuple(
            self._evaluate_expiration(
                expiration=expiration,
                rows=expiration_groups[expiration],
                quote_date=quote_date,
            )
            for expiration in sorted(expiration_groups)
        )

        call_count = sum(
            1 for row in rows if self._normalize_side(row.option_type) == "CALL"
        )
        put_count = sum(
            1 for row in rows if self._normalize_side(row.option_type) == "PUT"
        )
        contract_count = len(rows)
        expiration_count = len(expiration_profiles)
        distinct_strike_count = len({float(row.strike) for row in rows})

        call_put_ratio = (
            call_count / put_count
            if put_count > 0
            else (None if call_count == 0 else float("inf"))
        )
        balance_score = self._balance_score(call_count, put_count)

        expiration_score = self.policy.clamp(
            expiration_count / max(1, self.policy.minimum_expirations_per_symbol)
        )

        if expiration_profiles:
            strike_surface_score = sum(
                profile.completeness_score for profile in expiration_profiles
            ) / len(expiration_profiles)
        else:
            strike_surface_score = 0.0

        contract_score = self.policy.clamp(
            contract_count / max(1, self.policy.minimum_contracts_per_symbol)
        )

        overall = self.policy.clamp(
            0.30 * contract_score
            + 0.25 * expiration_score
            + 0.30 * strike_surface_score
            + 0.15 * balance_score
        )

        status, reasons = self._govern(
            contract_count=contract_count,
            expiration_count=expiration_count,
            call_put_balance_score=balance_score,
            expiration_coverage_score=expiration_score,
            strike_surface_score=strike_surface_score,
            overall_score=overall,
        )

        expirations = sorted(expiration_groups)
        minimum_expiration = expirations[0] if expirations else None
        maximum_expiration = expirations[-1] if expirations else None

        return OptionChainCoverageProfile(
            symbol=symbol,
            quote_date=quote_date,
            contract_count=contract_count,
            call_count=call_count,
            put_count=put_count,
            expiration_count=expiration_count,
            distinct_strike_count=distinct_strike_count,
            minimum_expiration=minimum_expiration,
            maximum_expiration=maximum_expiration,
            minimum_dte=(
                (minimum_expiration - quote_date).days
                if minimum_expiration is not None
                else None
            ),
            maximum_dte=(
                (maximum_expiration - quote_date).days
                if maximum_expiration is not None
                else None
            ),
            call_put_ratio=call_put_ratio,
            call_put_balance_score=round(balance_score, 6),
            expiration_coverage_score=round(expiration_score, 6),
            strike_surface_score=round(strike_surface_score, 6),
            overall_coverage_score=round(overall, 6),
            governance_status=status,
            governance_reasons=tuple(reasons),
            expirations=expiration_profiles,
        )

    def _evaluate_expiration(
        self,
        *,
        expiration: date,
        rows: Sequence[OptionContractCoverageRow],
        quote_date: date,
    ) -> ExpirationCoverageProfile:
        calls = [
            row for row in rows if self._normalize_side(row.option_type) == "CALL"
        ]
        puts = [
            row for row in rows if self._normalize_side(row.option_type) == "PUT"
        ]
        strikes = sorted({float(row.strike) for row in rows})
        gaps = [
            current - previous
            for previous, current in zip(strikes, strikes[1:])
            if current > previous
        ]

        median_gap = median(gaps) if gaps else None
        maximum_gap = max(gaps) if gaps else None

        strike_count_score = self.policy.clamp(
            len(strikes) / max(1, self.policy.minimum_strikes_per_expiration)
        )

        if not gaps or median_gap in (None, 0):
            gap_score = 1.0 if len(strikes) <= 1 else 0.0
        else:
            ratio = maximum_gap / median_gap
            gap_score = self.policy.clamp(
                self.policy.maximum_acceptable_strike_gap_multiple / max(ratio, 1.0)
            )

        balance_score = self._balance_score(len(calls), len(puts))
        completeness = self.policy.clamp(
            0.55 * strike_count_score
            + 0.25 * gap_score
            + 0.20 * balance_score
        )

        return ExpirationCoverageProfile(
            expiration_date=expiration,
            days_to_expiration=(expiration - quote_date).days,
            contract_count=len(rows),
            call_count=len(calls),
            put_count=len(puts),
            distinct_strikes=len(strikes),
            minimum_strike=min(strikes) if strikes else None,
            maximum_strike=max(strikes) if strikes else None,
            median_strike_gap=(
                round(float(median_gap), 8) if median_gap is not None else None
            ),
            maximum_strike_gap=(
                round(float(maximum_gap), 8) if maximum_gap is not None else None
            ),
            strike_gap_completeness_score=round(gap_score, 6),
            call_put_balance_score=round(balance_score, 6),
            completeness_score=round(completeness, 6),
        )

    def _govern(
        self,
        *,
        contract_count: int,
        expiration_count: int,
        call_put_balance_score: float,
        expiration_coverage_score: float,
        strike_surface_score: float,
        overall_score: float,
    ) -> tuple[GovernanceStatus, list[str]]:
        reasons: list[str] = []

        hard_failures = []
        if contract_count < self.policy.review_contracts_per_symbol:
            hard_failures.append(
                f"contracts {contract_count} < "
                f"{self.policy.review_contracts_per_symbol}"
            )
        if expiration_count < self.policy.review_expirations_per_symbol:
            hard_failures.append(
                f"expirations {expiration_count} < "
                f"{self.policy.review_expirations_per_symbol}"
            )
        if overall_score < self.policy.review_overall_score:
            hard_failures.append(
                f"overall score {overall_score:.3f} < "
                f"{self.policy.review_overall_score:.3f}"
            )

        if hard_failures:
            return GovernanceStatus.FAILED, hard_failures

        if contract_count < self.policy.minimum_contracts_per_symbol:
            reasons.append(
                f"contracts {contract_count} < "
                f"{self.policy.minimum_contracts_per_symbol}"
            )
        if expiration_count < self.policy.minimum_expirations_per_symbol:
            reasons.append(
                f"expirations {expiration_count} < "
                f"{self.policy.minimum_expirations_per_symbol}"
            )
        if call_put_balance_score < self.policy.minimum_call_put_balance_score:
            reasons.append(
                f"call/put balance {call_put_balance_score:.3f} < "
                f"{self.policy.minimum_call_put_balance_score:.3f}"
            )
        if expiration_coverage_score < self.policy.minimum_expiration_coverage_score:
            reasons.append(
                f"expiration coverage {expiration_coverage_score:.3f} < "
                f"{self.policy.minimum_expiration_coverage_score:.3f}"
            )
        if strike_surface_score < self.policy.minimum_strike_surface_score:
            reasons.append(
                f"strike surface {strike_surface_score:.3f} < "
                f"{self.policy.minimum_strike_surface_score:.3f}"
            )
        if overall_score < self.policy.ready_overall_score:
            reasons.append(
                f"overall score {overall_score:.3f} < "
                f"{self.policy.ready_overall_score:.3f}"
            )

        if reasons:
            return GovernanceStatus.REVIEW, reasons

        return GovernanceStatus.READY, []

    @staticmethod
    def _balance_score(call_count: int, put_count: int) -> float:
        total = call_count + put_count
        if total <= 0:
            return 0.0
        return 1.0 - abs(call_count - put_count) / total

    @staticmethod
    def _normalize_side(value: str) -> str:
        normalized = str(value).strip().upper()
        if normalized in {"C", "CALL"}:
            return "CALL"
        if normalized in {"P", "PUT"}:
            return "PUT"
        return normalized
