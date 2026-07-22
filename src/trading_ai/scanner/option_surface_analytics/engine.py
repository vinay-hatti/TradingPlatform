from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Iterable

from .contracts import (
    AggregateGovernanceStatus,
    ExpirationSurfaceRecord,
    SymbolSurfaceProfile,
)
from .policy import OptionSurfaceAnalyticsPolicy


@dataclass(frozen=True)
class OptionFeatureInput:
    underlying_symbol: str
    quote_date: date
    expiry: date
    option_type: str
    strike: float
    days_to_expiration: int
    implied_volatility: float | None
    absolute_delta: float | None
    volume: int | None
    open_interest: int | None
    governance_status: str


class OptionSurfaceAnalyticsEngine:
    def __init__(
        self,
        policy: OptionSurfaceAnalyticsPolicy | None = None,
    ) -> None:
        self.policy = policy or OptionSurfaceAnalyticsPolicy()

    def build(
        self,
        rows: Iterable[OptionFeatureInput],
    ) -> tuple[
        tuple[ExpirationSurfaceRecord, ...],
        tuple[SymbolSurfaceProfile, ...],
    ]:
        eligible = [
            row
            for row in rows
            if str(row.governance_status).strip().upper()
            in self.policy.normalized_allowed_statuses()
        ]

        grouped: dict[tuple[str, date, date], list[OptionFeatureInput]] = (
            defaultdict(list)
        )
        for row in eligible:
            grouped[
                (
                    row.underlying_symbol.upper(),
                    row.quote_date,
                    row.expiry,
                )
            ].append(row)

        expirations = tuple(
            self._build_expiration(group_rows)
            for _, group_rows in sorted(grouped.items())
        )

        by_symbol: dict[tuple[str, date], list[ExpirationSurfaceRecord]] = (
            defaultdict(list)
        )
        for record in expirations:
            by_symbol[
                (record.underlying_symbol, record.quote_date)
            ].append(record)

        symbols = tuple(
            self._build_symbol(records)
            for _, records in sorted(by_symbol.items())
        )
        return expirations, symbols

    def _build_expiration(
        self,
        rows: list[OptionFeatureInput],
    ) -> ExpirationSurfaceRecord:
        first = rows[0]
        calls = [r for r in rows if self._is_call(r.option_type)]
        puts = [r for r in rows if self._is_put(r.option_type)]

        total_volume = sum(max(r.volume or 0, 0) for r in rows)
        total_oi = sum(max(r.open_interest or 0, 0) for r in rows)
        call_volume = sum(max(r.volume or 0, 0) for r in calls)
        put_volume = sum(max(r.volume or 0, 0) for r in puts)
        call_oi = sum(max(r.open_interest or 0, 0) for r in calls)
        put_oi = sum(max(r.open_interest or 0, 0) for r in puts)

        near_money = [
            r for r in rows
            if self._between(
                r.absolute_delta,
                self.policy.near_money_absolute_delta_minimum,
                self.policy.near_money_absolute_delta_maximum,
            )
        ]
        downside_puts = [
            r for r in puts
            if self._between(
                r.absolute_delta,
                self.policy.downside_put_absolute_delta_minimum,
                self.policy.downside_put_absolute_delta_maximum,
            )
        ]
        upside_calls = [
            r for r in calls
            if self._between(
                r.absolute_delta,
                self.policy.upside_call_absolute_delta_minimum,
                self.policy.upside_call_absolute_delta_maximum,
            )
        ]

        weighted_iv = self._weighted_average(rows)
        call_weighted_iv = self._weighted_average(calls)
        put_weighted_iv = self._weighted_average(puts)
        atm_iv = self._weighted_average(near_money)
        downside_put_iv = self._weighted_average(downside_puts)
        upside_call_iv = self._weighted_average(upside_calls)

        reasons: list[str] = []
        status = AggregateGovernanceStatus.READY
        strike_count = len({r.strike for r in rows})

        if len(rows) < self.policy.minimum_contracts_per_expiration:
            status = AggregateGovernanceStatus.EXCLUDED
            reasons.append(
                f"contracts {len(rows)} < "
                f"{self.policy.minimum_contracts_per_expiration}"
            )
        if strike_count < self.policy.minimum_strikes_per_expiration:
            status = AggregateGovernanceStatus.EXCLUDED
            reasons.append(
                f"strikes {strike_count} < "
                f"{self.policy.minimum_strikes_per_expiration}"
            )
        if total_oi < self.policy.minimum_open_interest_per_expiration:
            status = AggregateGovernanceStatus.EXCLUDED
            reasons.append(
                f"open interest {total_oi} < "
                f"{self.policy.minimum_open_interest_per_expiration}"
            )

        oi_concentration = self._concentration(
            [max(r.open_interest or 0, 0) for r in rows]
        )
        volume_concentration = self._concentration(
            [max(r.volume or 0, 0) for r in rows]
        )

        if status != AggregateGovernanceStatus.EXCLUDED:
            if atm_iv is None:
                status = AggregateGovernanceStatus.REVIEW
                reasons.append("ATM implied volatility unavailable")

            # Concentration governance is meaningful only when the number of
            # contracts exceeds the top-N concentration bucket. Otherwise,
            # top-N necessarily captures the entire surface and equals 100%.
            concentration_is_actionable = (
                len(rows) > self.policy.concentration_top_n
            )

            if concentration_is_actionable and oi_concentration is not None:
                if (
                    oi_concentration
                    > self.policy.maximum_review_open_interest_concentration
                ):
                    status = AggregateGovernanceStatus.EXCLUDED
                    reasons.append(
                        "open-interest concentration exceeds review limit"
                    )
                elif (
                    oi_concentration
                    > self.policy.maximum_ready_open_interest_concentration
                    and status == AggregateGovernanceStatus.READY
                ):
                    status = AggregateGovernanceStatus.REVIEW
                    reasons.append(
                        "open-interest concentration exceeds ready limit"
                    )

        return ExpirationSurfaceRecord(
            underlying_symbol=first.underlying_symbol.upper(),
            quote_date=first.quote_date,
            expiry=first.expiry,
            days_to_expiration=first.days_to_expiration,
            contract_count=len(rows),
            call_contract_count=len(calls),
            put_contract_count=len(puts),
            strike_count=strike_count,
            total_volume=total_volume,
            total_open_interest=total_oi,
            call_volume=call_volume,
            put_volume=put_volume,
            call_open_interest=call_oi,
            put_open_interest=put_oi,
            call_put_volume_ratio=self._ratio(call_volume, put_volume),
            call_put_open_interest_ratio=self._ratio(call_oi, put_oi),
            weighted_implied_volatility=weighted_iv,
            call_weighted_implied_volatility=call_weighted_iv,
            put_weighted_implied_volatility=put_weighted_iv,
            atm_implied_volatility=atm_iv,
            downside_put_implied_volatility=downside_put_iv,
            upside_call_implied_volatility=upside_call_iv,
            put_skew_25d_minus_atm=self._difference(
                downside_put_iv,
                atm_iv,
            ),
            call_skew_25d_minus_atm=self._difference(
                upside_call_iv,
                atm_iv,
            ),
            risk_reversal_25d=self._difference(
                upside_call_iv,
                downside_put_iv,
            ),
            near_money_contract_count=len(near_money),
            downside_put_contract_count=len(downside_puts),
            upside_call_contract_count=len(upside_calls),
            top_5_open_interest_concentration=oi_concentration,
            top_5_volume_concentration=volume_concentration,
            governance_status=status,
            governance_reasons=tuple(reasons),
        )

    def _build_symbol(
        self,
        records: list[ExpirationSurfaceRecord],
    ) -> SymbolSurfaceProfile:
        records = sorted(records, key=lambda r: r.expiry)
        valid = [
            r for r in records
            if r.governance_status
            != AggregateGovernanceStatus.EXCLUDED
        ]
        ready = [
            r for r in records
            if r.governance_status
            == AggregateGovernanceStatus.READY
        ]
        review = [
            r for r in records
            if r.governance_status
            == AggregateGovernanceStatus.REVIEW
        ]
        excluded = [
            r for r in records
            if r.governance_status
            == AggregateGovernanceStatus.EXCLUDED
        ]

        atm_points = [
            (r.days_to_expiration, r.atm_implied_volatility)
            for r in valid
            if r.atm_implied_volatility is not None
        ]

        nearest = valid[0] if valid else None
        farthest = valid[-1] if valid else None

        reasons: list[str] = []
        if len(valid) < self.policy.minimum_expirations_per_symbol:
            status = AggregateGovernanceStatus.EXCLUDED
            reasons.append(
                f"eligible expirations {len(valid)} < "
                f"{self.policy.minimum_expirations_per_symbol}"
            )
        elif len(atm_points) < self.policy.minimum_atm_term_points_for_ready:
            status = AggregateGovernanceStatus.REVIEW
            reasons.append(
                "insufficient ATM term-structure points for READY"
            )
        elif review:
            status = AggregateGovernanceStatus.REVIEW
            reasons.append("one or more expirations require review")
        else:
            status = AggregateGovernanceStatus.READY

        total_call_volume = sum(r.call_volume for r in valid)
        total_put_volume = sum(r.put_volume for r in valid)
        total_call_oi = sum(r.call_open_interest for r in valid)
        total_put_oi = sum(r.put_open_interest for r in valid)

        return SymbolSurfaceProfile(
            underlying_symbol=records[0].underlying_symbol,
            quote_date=records[0].quote_date,
            expiration_count=len(records),
            ready_expiration_count=len(ready),
            review_expiration_count=len(review),
            excluded_expiration_count=len(excluded),
            nearest_expiry=nearest.expiry if nearest else None,
            farthest_expiry=farthest.expiry if farthest else None,
            nearest_atm_implied_volatility=(
                nearest.atm_implied_volatility if nearest else None
            ),
            farthest_atm_implied_volatility=(
                farthest.atm_implied_volatility if farthest else None
            ),
            atm_term_structure_slope=self._term_slope(atm_points),
            total_contract_count=sum(r.contract_count for r in valid),
            total_volume=sum(r.total_volume for r in valid),
            total_open_interest=sum(r.total_open_interest for r in valid),
            aggregate_put_call_volume_ratio=self._ratio(
                total_put_volume,
                total_call_volume,
            ),
            aggregate_put_call_open_interest_ratio=self._ratio(
                total_put_oi,
                total_call_oi,
            ),
            governance_status=status,
            governance_reasons=tuple(reasons),
        )

    def _weighted_average(
        self,
        rows: Iterable[OptionFeatureInput],
    ) -> float | None:
        values = [
            (
                float(row.implied_volatility),
                max(row.open_interest or 0, 0),
            )
            for row in rows
            if row.implied_volatility is not None
        ]
        if not values:
            return None

        weighted_total = sum(value * weight for value, weight in values)
        total_weight = sum(weight for _, weight in values)
        if total_weight > 0:
            return self._round(weighted_total / total_weight)

        return self._round(
            sum(value for value, _ in values) / len(values)
        )

    def _concentration(self, values: list[int]) -> float | None:
        total = sum(values)
        if total <= 0:
            return None
        top = sorted(values, reverse=True)[
            : self.policy.concentration_top_n
        ]
        return self._round(sum(top) / total)

    @staticmethod
    def _ratio(numerator: int, denominator: int) -> float | None:
        if denominator <= 0:
            return None
        return round(numerator / denominator, 8)

    @staticmethod
    def _difference(
        left: float | None,
        right: float | None,
    ) -> float | None:
        if left is None or right is None:
            return None
        return round(left - right, 8)

    @staticmethod
    def _term_slope(
        points: list[tuple[int, float]],
    ) -> float | None:
        points = sorted(points)
        if len(points) < 2:
            return None
        first_dte, first_iv = points[0]
        last_dte, last_iv = points[-1]
        span = last_dte - first_dte
        if span <= 0:
            return None
        return round((last_iv - first_iv) / span, 8)

    @staticmethod
    def _between(
        value: float | None,
        lower: float,
        upper: float,
    ) -> bool:
        return value is not None and lower <= value <= upper

    @staticmethod
    def _is_call(value: str) -> bool:
        return str(value).strip().upper() in {"C", "CALL"}

    @staticmethod
    def _is_put(value: str) -> bool:
        return str(value).strip().upper() in {"P", "PUT"}

    @staticmethod
    def _round(value: float | None) -> float | None:
        return None if value is None else round(float(value), 8)
