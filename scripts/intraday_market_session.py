from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

MARKET_TZ = ZoneInfo("America/New_York")


def market_date_from_iso(value: str) -> date:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=MARKET_TZ)
    return dt.astimezone(MARKET_TZ).date()


def _observed_fixed(d: date) -> date:
    # NYSE observes Saturday holidays on Friday and Sunday holidays on Monday.
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    d = date(year, month, 1)
    delta = (weekday - d.weekday()) % 7
    return d + timedelta(days=delta + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    last = date(year, month, monthrange(year, month)[1])
    delta = (last.weekday() - weekday) % 7
    return last - timedelta(days=delta)


def _easter_sunday(year: int) -> date:
    # Anonymous Gregorian computus.
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def nyse_full_day_holidays(year: int) -> set[date]:
    holidays = {
        _observed_fixed(date(year, 1, 1)),                 # New Year's Day
        _nth_weekday(year, 1, 0, 3),                      # MLK Day
        _nth_weekday(year, 2, 0, 3),                      # Washington's Birthday
        _easter_sunday(year) - timedelta(days=2),          # Good Friday
        _last_weekday(year, 5, 0),                        # Memorial Day
        _observed_fixed(date(year, 7, 4)),                 # Independence Day
        _nth_weekday(year, 9, 0, 1),                      # Labor Day
        _nth_weekday(year, 11, 3, 4),                     # Thanksgiving
        _observed_fixed(date(year, 12, 25)),               # Christmas
    }

    # Juneteenth became an NYSE market holiday beginning in 2022.
    if year >= 2022:
        holidays.add(_observed_fixed(date(year, 6, 19)))

    return holidays


def is_us_market_session_date(d: date) -> bool:
    if d.weekday() >= 5:
        return False
    # Include adjacent-year observed New Year's dates safely.
    holidays = (
        nyse_full_day_holidays(d.year - 1)
        | nyse_full_day_holidays(d.year)
        | nyse_full_day_holidays(d.year + 1)
    )
    return d not in holidays


def market_session_info(value: str) -> dict[str, object]:
    d = market_date_from_iso(value)
    return {
        "market_date": d.isoformat(),
        "market_session": is_us_market_session_date(d),
        "calendar": "SELF_CONTAINED_NYSE_FULL_DAY_CALENDAR",
        "timezone": "America/New_York",
    }
