from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Mapping


class OptionSide(str, Enum):
    CALL = "CALL"
    PUT = "PUT"


class OptionValidationSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True, order=True)
class OptionContractIdentity:
    underlying_symbol: str
    expiration_date: date
    strike: float
    option_side: OptionSide

    @property
    def canonical_key(self) -> str:
        return (
            f"{self.underlying_symbol}|"
            f"{self.expiration_date.isoformat()}|"
            f"{self.strike:.8f}|"
            f"{self.option_side.value}"
        )


@dataclass(frozen=True)
class OptionQuoteRecord:
    identity: OptionContractIdentity
    quote_date: date
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    volume: int | None = None
    open_interest: int | None = None
    implied_volatility: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    provider_symbol: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    @property
    def days_to_expiration(self) -> int:
        return (self.identity.expiration_date - self.quote_date).days

    @property
    def midpoint(self) -> float | None:
        if self.bid is None or self.ask is None:
            return None
        return (self.bid + self.ask) / 2.0

    @property
    def absolute_spread(self) -> float | None:
        if self.bid is None or self.ask is None:
            return None
        return self.ask - self.bid

    @property
    def spread_percentage(self) -> float | None:
        midpoint = self.midpoint
        spread = self.absolute_spread
        if midpoint is None or spread is None or midpoint <= 0:
            return None
        return spread / midpoint


@dataclass(frozen=True)
class OptionValidationIssue:
    code: str
    severity: OptionValidationSeverity
    message: str
    field_name: str | None = None
    observed_value: object | None = None


@dataclass(frozen=True)
class OptionValidationResult:
    record: OptionQuoteRecord
    valid: bool
    issues: tuple[OptionValidationIssue, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        return sum(
            issue.severity is OptionValidationSeverity.ERROR
            for issue in self.issues
        )

    @property
    def warning_count(self) -> int:
        return sum(
            issue.severity is OptionValidationSeverity.WARNING
            for issue in self.issues
        )
