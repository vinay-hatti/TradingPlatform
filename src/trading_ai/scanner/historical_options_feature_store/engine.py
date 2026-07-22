from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import log
from typing import Iterable

from .contracts import (
    FeatureGovernanceStatus,
    HistoricalOptionFeatureRecord,
)
from .policy import HistoricalOptionFeaturePolicy


@dataclass(frozen=True)
class HistoricalOptionInput:
    underlying_symbol: str
    quote_date: date
    expiry: date
    option_type: str
    strike: float
    underlying_price: float | None
    last_price: float | None
    volume: int | None
    open_interest: int | None
    implied_volatility: float | None
    delta: float | None
    gamma: float | None
    theta: float | None
    vega: float | None
    readiness_status: str


class HistoricalOptionFeatureEngine:
    def __init__(
        self,
        policy: HistoricalOptionFeaturePolicy | None = None,
    ) -> None:
        self.policy = policy or HistoricalOptionFeaturePolicy()

    def build(
        self,
        rows: Iterable[HistoricalOptionInput],
    ) -> tuple[HistoricalOptionFeatureRecord, ...]:
        return tuple(self._build_record(row) for row in rows)

    def _build_record(
        self,
        row: HistoricalOptionInput,
    ) -> HistoricalOptionFeatureRecord:
        reasons: list[str] = []
        status = FeatureGovernanceStatus.READY

        readiness = str(row.readiness_status).strip().upper()
        if readiness not in self.policy.normalized_allowed_statuses():
            status = FeatureGovernanceStatus.EXCLUDED
            reasons.append(f"readiness status {readiness} not allowed")

        dte = (row.expiry - row.quote_date).days
        if dte < self.policy.minimum_days_to_expiration:
            status = FeatureGovernanceStatus.EXCLUDED
            reasons.append(
                f"DTE {dte} < {self.policy.minimum_days_to_expiration}"
            )
        elif dte > self.policy.maximum_days_to_expiration:
            status = FeatureGovernanceStatus.EXCLUDED
            reasons.append(
                f"DTE {dte} > {self.policy.maximum_days_to_expiration}"
            )

        if (row.open_interest or 0) < self.policy.minimum_open_interest:
            status = FeatureGovernanceStatus.EXCLUDED
            reasons.append(
                f"open interest {(row.open_interest or 0)} < "
                f"{self.policy.minimum_open_interest}"
            )

        if (row.volume or 0) < self.policy.minimum_volume:
            status = FeatureGovernanceStatus.EXCLUDED
            reasons.append(
                f"volume {(row.volume or 0)} < "
                f"{self.policy.minimum_volume}"
            )

        if (
            self.policy.require_implied_volatility
            and row.implied_volatility is None
        ):
            status = FeatureGovernanceStatus.EXCLUDED
            reasons.append("implied volatility missing")

        if self.policy.require_delta and row.delta is None:
            status = FeatureGovernanceStatus.EXCLUDED
            reasons.append("delta missing")

        missing_optional = [
            name
            for name, value in (
                ("gamma", row.gamma),
                ("theta", row.theta),
                ("vega", row.vega),
            )
            if value is None
        ]
        if (
            status == FeatureGovernanceStatus.READY
            and missing_optional
            and self.policy.review_missing_optional_greeks
        ):
            status = FeatureGovernanceStatus.REVIEW
            reasons.append(
                "optional Greeks missing: " + ", ".join(missing_optional)
            )

        option_type = str(row.option_type).strip().upper()
        underlying = row.underlying_price
        strike = float(row.strike)

        moneyness = None
        log_moneyness = None
        intrinsic = None
        extrinsic = None

        if underlying is not None and underlying > 0 and strike > 0:
            moneyness = strike / underlying
            log_moneyness = log(moneyness)

            if option_type in {"C", "CALL"}:
                intrinsic = max(underlying - strike, 0.0)
            elif option_type in {"P", "PUT"}:
                intrinsic = max(strike - underlying, 0.0)

            if intrinsic is not None and row.last_price is not None:
                extrinsic = max(row.last_price - intrinsic, 0.0)

        volume_to_oi = None
        if row.open_interest is not None and row.open_interest > 0:
            volume_to_oi = (row.volume or 0) / row.open_interest

        return HistoricalOptionFeatureRecord(
            underlying_symbol=str(
                row.underlying_symbol
            ).strip().upper(),
            quote_date=row.quote_date,
            expiry=row.expiry,
            option_type=option_type,
            strike=strike,
            days_to_expiration=dte,
            moneyness=self._round(moneyness),
            log_moneyness=self._round(log_moneyness),
            intrinsic_value=self._round(intrinsic),
            extrinsic_value=self._round(extrinsic),
            last_price=row.last_price,
            volume=row.volume,
            open_interest=row.open_interest,
            implied_volatility=row.implied_volatility,
            delta=row.delta,
            gamma=row.gamma,
            theta=row.theta,
            vega=row.vega,
            volume_to_open_interest=self._round(volume_to_oi),
            absolute_delta=(
                self._round(abs(row.delta))
                if row.delta is not None
                else None
            ),
            theta_per_day=self._round(row.theta),
            vega_per_iv_point=(
                self._round(row.vega / 100.0)
                if row.vega is not None
                else None
            ),
            readiness_status=readiness,
            governance_status=status,
            governance_reasons=tuple(reasons),
        )

    @staticmethod
    def _round(value):
        return None if value is None else round(float(value), 8)
