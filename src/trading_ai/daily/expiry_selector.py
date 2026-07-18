from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta


@dataclass(frozen=True)
class ExpirySelection:
    valuation_date: date
    target_dte: int
    expiration_date: date
    actual_dte: int
    source: str = "STANDARD_FRIDAY_PROXY"

    @property
    def expiration_iso(self) -> str:
        return self.expiration_date.isoformat()


class StandardFridayExpirySelector:
    SOURCE = "STANDARD_FRIDAY_PROXY"

    @staticmethod
    def _as_date(value: str | date | datetime | None) -> date:
        if value is None:
            return date.today()
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value)[:10])

    def select(
        self,
        *,
        valuation_date: str | date | datetime | None,
        target_dte: int,
    ) -> ExpirySelection:
        valuation = self._as_date(valuation_date)
        requested = int(target_dte)
        if requested <= 0:
            raise ValueError("target_dte must be positive")

        target = valuation + timedelta(days=requested)
        previous_friday = target - timedelta(
            days=(target.weekday() - 4) % 7
        )
        next_friday = target + timedelta(
            days=(4 - target.weekday()) % 7
        )
        candidates = [
            candidate
            for candidate in (previous_friday, next_friday)
            if candidate > valuation
        ]
        expiration = min(
            candidates,
            key=lambda candidate: (
                abs((candidate - target).days),
                -candidate.toordinal(),
            ),
        )

        return ExpirySelection(
            valuation_date=valuation,
            target_dte=requested,
            expiration_date=expiration,
            actual_dte=(expiration - valuation).days,
            source=self.SOURCE,
        )
