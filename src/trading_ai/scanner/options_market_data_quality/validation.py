from __future__ import annotations

from math import isfinite

from .contracts import (
    OptionQuoteRecord,
    OptionSide,
    OptionValidationIssue,
    OptionValidationResult,
    OptionValidationSeverity,
)
from .policy import OptionContractValidationPolicy


class OptionContractValidationEngine:
    def __init__(
        self,
        policy: OptionContractValidationPolicy | None = None,
    ) -> None:
        self.policy = policy or OptionContractValidationPolicy()
        self.policy.validate()

    def evaluate(self, record: OptionQuoteRecord) -> OptionValidationResult:
        issues: list[OptionValidationIssue] = []

        self._validate_identity(record, issues)
        self._validate_market(record, issues)
        self._validate_liquidity(record, issues)
        self._validate_greeks(record, issues)

        valid = not any(
            issue.severity is OptionValidationSeverity.ERROR
            for issue in issues
        )
        return OptionValidationResult(
            record=record,
            valid=valid,
            issues=tuple(issues),
            metadata={
                "canonical_key": record.identity.canonical_key,
                "days_to_expiration": record.days_to_expiration,
                "spread_percentage": record.spread_percentage,
            },
        )

    def evaluate_many(
        self,
        records: list[OptionQuoteRecord] | tuple[OptionQuoteRecord, ...],
    ) -> tuple[OptionValidationResult, ...]:
        return tuple(self.evaluate(record) for record in records)

    def _validate_identity(
        self,
        record: OptionQuoteRecord,
        issues: list[OptionValidationIssue],
    ) -> None:
        identity = record.identity
        if not identity.underlying_symbol.strip():
            self._error(
                issues,
                "EMPTY_UNDERLYING",
                "Underlying symbol must not be empty.",
                "underlying_symbol",
                identity.underlying_symbol,
            )

        if not (
            self.policy.minimum_strike
            <= identity.strike
            <= self.policy.maximum_strike
        ):
            self._error(
                issues,
                "INVALID_STRIKE",
                "Strike is outside the configured valid range.",
                "strike",
                identity.strike,
            )

        dte = record.days_to_expiration
        if self.policy.reject_expired_contracts and dte < 0:
            self._error(
                issues,
                "EXPIRED_CONTRACT",
                "Expiration date precedes quote date.",
                "expiration_date",
                identity.expiration_date,
            )
        elif not (
            self.policy.minimum_days_to_expiration
            <= dte
            <= self.policy.maximum_days_to_expiration
        ):
            self._error(
                issues,
                "INVALID_DTE",
                "Days to expiration is outside the configured valid range.",
                "days_to_expiration",
                dte,
            )

    def _validate_market(
        self,
        record: OptionQuoteRecord,
        issues: list[OptionValidationIssue],
    ) -> None:
        for field_name in ("bid", "ask", "last"):
            value = getattr(record, field_name)
            if value is None:
                continue
            if not isfinite(value):
                self._error(
                    issues,
                    "NON_FINITE_MARKET_VALUE",
                    f"{field_name} must be finite.",
                    field_name,
                    value,
                )
            elif self.policy.require_nonnegative_bid_ask_last and value < 0:
                self._error(
                    issues,
                    "NEGATIVE_MARKET_VALUE",
                    f"{field_name} must be nonnegative.",
                    field_name,
                    value,
                )

        if (
            self.policy.reject_crossed_market
            and record.bid is not None
            and record.ask is not None
            and record.bid > record.ask
        ):
            self._error(
                issues,
                "CROSSED_MARKET",
                "Bid must not exceed ask.",
                "bid_ask",
                (record.bid, record.ask),
            )

        spread_percentage = record.spread_percentage
        if (
            spread_percentage is not None
            and spread_percentage > self.policy.maximum_spread_percentage
        ):
            self._warning(
                issues,
                "WIDE_SPREAD",
                "Bid/ask spread exceeds the configured percentage.",
                "spread_percentage",
                spread_percentage,
            )

        iv = record.implied_volatility
        if iv is not None:
            if not isfinite(iv) or iv < 0:
                self._error(
                    issues,
                    "INVALID_IV",
                    "Implied volatility must be finite and nonnegative.",
                    "implied_volatility",
                    iv,
                )
            elif iv > self.policy.maximum_implied_volatility:
                self._warning(
                    issues,
                    "EXTREME_IV",
                    "Implied volatility exceeds the configured maximum.",
                    "implied_volatility",
                    iv,
                )

    def _validate_liquidity(
        self,
        record: OptionQuoteRecord,
        issues: list[OptionValidationIssue],
    ) -> None:
        if not self.policy.require_nonnegative_volume_open_interest:
            return
        for field_name in ("volume", "open_interest"):
            value = getattr(record, field_name)
            if value is not None and value < 0:
                self._error(
                    issues,
                    "NEGATIVE_LIQUIDITY_VALUE",
                    f"{field_name} must be nonnegative.",
                    field_name,
                    value,
                )

    def _validate_greeks(
        self,
        record: OptionQuoteRecord,
        issues: list[OptionValidationIssue],
    ) -> None:
        delta = record.delta
        if delta is not None:
            if not isfinite(delta) or not (
                self.policy.minimum_delta
                <= delta
                <= self.policy.maximum_delta
            ):
                self._error(
                    issues,
                    "INVALID_DELTA",
                    "Delta is outside the configured range.",
                    "delta",
                    delta,
                )
            elif (
                record.identity.option_side is OptionSide.CALL
                and delta < 0
            ):
                self._warning(
                    issues,
                    "CALL_NEGATIVE_DELTA",
                    "Call delta is negative.",
                    "delta",
                    delta,
                )
            elif (
                record.identity.option_side is OptionSide.PUT
                and delta > 0
            ):
                self._warning(
                    issues,
                    "PUT_POSITIVE_DELTA",
                    "Put delta is positive.",
                    "delta",
                    delta,
                )

        self._bounded_nonnegative(
            issues,
            "gamma",
            record.gamma,
            self.policy.minimum_gamma,
            self.policy.maximum_gamma,
        )
        self._bounded_nonnegative(
            issues,
            "vega",
            record.vega,
            self.policy.minimum_vega,
            self.policy.maximum_vega,
        )

        theta = record.theta
        if theta is not None and (
            not isfinite(theta)
            or not (
                self.policy.minimum_theta
                <= theta
                <= self.policy.maximum_theta
            )
        ):
            self._error(
                issues,
                "INVALID_THETA",
                "Theta is outside the configured range.",
                "theta",
                theta,
            )

    def _bounded_nonnegative(
        self,
        issues: list[OptionValidationIssue],
        field_name: str,
        value: float | None,
        minimum: float,
        maximum: float,
    ) -> None:
        if value is None:
            return
        if not isfinite(value) or not (minimum <= value <= maximum):
            self._error(
                issues,
                f"INVALID_{field_name.upper()}",
                f"{field_name} is outside the configured range.",
                field_name,
                value,
            )

    @staticmethod
    def _error(
        issues: list[OptionValidationIssue],
        code: str,
        message: str,
        field_name: str,
        observed_value: object,
    ) -> None:
        issues.append(
            OptionValidationIssue(
                code=code,
                severity=OptionValidationSeverity.ERROR,
                message=message,
                field_name=field_name,
                observed_value=observed_value,
            )
        )

    @staticmethod
    def _warning(
        issues: list[OptionValidationIssue],
        code: str,
        message: str,
        field_name: str,
        observed_value: object,
    ) -> None:
        issues.append(
            OptionValidationIssue(
                code=code,
                severity=OptionValidationSeverity.WARNING,
                message=message,
                field_name=field_name,
                observed_value=observed_value,
            )
        )
