from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from typing import Iterable

from .market_hours_policy import MarketHoursPolicy
from .market_hours_profile import MarketSessionProfile


class MarketHoursService:
    """Configurable exchange-session classifier without external dependencies."""

    def __init__(
        self,
        policy: MarketHoursPolicy | None = None,
        *,
        holidays: Iterable[str | date] = (),
        early_closes: dict[str, str] | None = None,
        exchange: str = "US",
    ) -> None:
        self.policy = policy or MarketHoursPolicy()
        self.policy.validate()
        self.exchange = exchange
        self.zone = ZoneInfo(self.policy.timezone)
        self.holidays = {
            item.isoformat() if isinstance(item, date) else str(item)
            for item in holidays
        }
        self.early_closes = dict(early_closes or {})

    @staticmethod
    def _parse_clock(value: str) -> time:
        hour, minute = value.split(":")
        return time(int(hour), int(minute))

    def _localize(self, value: datetime | None) -> datetime:
        current = value or datetime.now(self.zone)
        if current.tzinfo is None:
            current = current.replace(tzinfo=self.zone)
        return current.astimezone(self.zone)

    def _next_weekday(self, day: date) -> date:
        candidate = day
        while True:
            candidate += timedelta(days=1)
            if (
                candidate.weekday() in self.policy.weekdays
                and candidate.isoformat() not in self.holidays
            ):
                return candidate

    def evaluate(self, at: datetime | None = None) -> MarketSessionProfile:
        local = self._localize(at)
        trading_date = local.date()
        date_key = trading_date.isoformat()
        holiday = (
            self.policy.observe_holidays and date_key in self.holidays
        )
        valid_weekday = local.weekday() in self.policy.weekdays
        early_close_value = self.early_closes.get(date_key)
        early_close = early_close_value is not None

        pre_open = self._parse_clock(self.policy.premarket_open)
        regular_open = self._parse_clock(self.policy.regular_open)
        regular_close = self._parse_clock(
            early_close_value or self.policy.regular_close
        )
        after_close = self._parse_clock(self.policy.afterhours_close)
        current_time = local.timetz().replace(tzinfo=None)

        session = "CLOSED"
        market_open = False
        regular = False
        warnings: list[str] = []

        if holiday or not valid_weekday:
            session = "HOLIDAY" if holiday else "WEEKEND"
        elif pre_open <= current_time < regular_open:
            session = "PREMARKET"
            market_open = self.policy.allow_premarket
        elif regular_open <= current_time < regular_close:
            session = "REGULAR"
            market_open = True
            regular = True
        elif regular_close <= current_time < after_close:
            session = "AFTERHOURS"
            market_open = self.policy.allow_afterhours
        else:
            session = "CLOSED"

        if early_close:
            warnings.append("EARLY_CLOSE_SESSION")

        if session in {"HOLIDAY", "WEEKEND", "CLOSED"}:
            next_day = (
                trading_date
                if valid_weekday
                and not holiday
                and current_time < pre_open
                else self._next_weekday(trading_date)
            )
            next_open = datetime.combine(
                next_day,
                pre_open if self.policy.allow_premarket else regular_open,
                self.zone,
            )
        else:
            next_open = None

        if market_open:
            close_clock = (
                regular_close
                if session == "REGULAR" and not self.policy.allow_afterhours
                else after_close
            )
            next_close = datetime.combine(trading_date, close_clock, self.zone)
        else:
            next_close = None

        return MarketSessionProfile(
            exchange=self.exchange,
            timezone=self.policy.timezone,
            local_timestamp=local.isoformat(),
            trading_date=date_key,
            session=session,
            market_open=market_open,
            regular_session=regular,
            holiday=holiday,
            early_close=early_close,
            next_open_at=next_open.isoformat() if next_open else None,
            next_close_at=next_close.isoformat() if next_close else None,
            warnings=tuple(warnings),
            metadata={
                "regular_open": self.policy.regular_open,
                "regular_close": early_close_value or self.policy.regular_close,
                "premarket_open": self.policy.premarket_open,
                "afterhours_close": self.policy.afterhours_close,
            },
        )
