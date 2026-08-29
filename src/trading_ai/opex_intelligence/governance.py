from __future__ import annotations

import hashlib
import json
from calendar import monthrange
from datetime import date, datetime, timedelta
from math import log
from typing import Any, Iterable


INDEXES = ("SPX", "NDX", "RUT")

# Standard third-Friday index expirations are AM settled.  The special opening
# quotation is the only governed terminal truth accepted by M71.4.
SETTLEMENT_CONVENTIONS = {
    "SPX": {
        "settlement_symbol": "SET",
        "candidate_symbols": ("SET", "I:SET"),
        "settlement_style": "AM_OPENING_SPECIAL_QUOTATION",
        "official_source": "CBOE",
    },
    "NDX": {
        "settlement_symbol": "XQO",
        "candidate_symbols": ("XQO", "I:XQO"),
        "settlement_style": "AM_OPENING_SPECIAL_QUOTATION",
        "official_source": "NASDAQ",
    },
    "RUT": {
        "settlement_symbol": "RLS",
        "candidate_symbols": ("RLS", "I:RLS"),
        "settlement_style": "AM_OPENING_SPECIAL_QUOTATION",
        "official_source": "CBOE",
    },
}


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if hasattr(value, "_mapping"):
        return dict(value._mapping)
    if hasattr(value, "__dict__"):
        return {
            key: item
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return str(value)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
        default=_json_default,
    )


def state_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _nth_weekday(year: int, month: int, weekday: int, ordinal: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (ordinal - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    last = date(year, month, monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _easter_sunday(year: int) -> date:
    # Anonymous Gregorian algorithm.
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
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def us_index_market_holidays(year: int) -> frozenset[date]:
    holidays = {
        _observed(date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),  # Martin Luther King Jr. Day
        _nth_weekday(year, 2, 0, 3),  # Presidents Day
        _easter_sunday(year) - timedelta(days=2),  # Good Friday
        _last_weekday(year, 5, 0),  # Memorial Day
        _observed(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),  # Labor Day
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving
        _observed(date(year, 12, 25)),
    }
    if year >= 2022:
        holidays.add(_observed(date(year, 6, 19)))
    # Include next year's observed New Year when it falls in this year.
    observed_next_new_year = _observed(date(year + 1, 1, 1))
    if observed_next_new_year.year == year:
        holidays.add(observed_next_new_year)
    return frozenset(holidays)


def is_trading_session(day: date) -> bool:
    return day.weekday() < 5 and day not in us_index_market_holidays(day.year)


def previous_trading_session(day: date) -> date:
    cursor = day
    while not is_trading_session(cursor):
        cursor -= timedelta(days=1)
    return cursor


def monthly_opex_date(year: int, month: int) -> date:
    third_friday = _nth_weekday(year, month, 4, 3)
    return previous_trading_session(third_friday)


def is_monthly_opex(day: date) -> bool:
    return day == monthly_opex_date(day.year, day.month)


def cycle_type(day: date) -> str:
    if is_monthly_opex(day) and day.month in (3, 6, 9, 12):
        return "QUARTERLY_OPEX"
    if is_monthly_opex(day):
        return "MONTHLY_OPEX"
    return "WEEKLY_EXPIRY"


def trading_sessions(start: date, end: date, *, include_start: bool = False) -> list[date]:
    if end < start:
        return []
    cursor = start if include_start else start + timedelta(days=1)
    sessions: list[date] = []
    while cursor <= end:
        if is_trading_session(cursor):
            sessions.append(cursor)
        cursor += timedelta(days=1)
    return sessions


def trading_dte(start: date, end: date) -> int:
    return len(trading_sessions(start, end, include_start=False))


def horizon_bucket(calendar_dte: int) -> str:
    if calendar_dte <= 7:
        return "0-7"
    if calendar_dte <= 30:
        return "8-30"
    if calendar_dte <= 60:
        return "31-60"
    return "61+"


def settlement_convention(symbol: str, expiration: date) -> dict[str, Any]:
    symbol = symbol.upper()
    convention = dict(SETTLEMENT_CONVENTIONS[symbol])
    convention.update(
        {
            "underlying_symbol": symbol,
            "expiration": expiration.isoformat(),
            "cycle_type": cycle_type(expiration),
            "eligible": is_monthly_opex(expiration),
        }
    )
    return convention


def binary_brier_score(pairs: Iterable[tuple[float, int]]) -> float | None:
    rows = [(max(0.0, min(1.0, float(p))), int(y)) for p, y in pairs]
    if not rows:
        return None
    return sum((p - y) ** 2 for p, y in rows) / len(rows)


def binary_log_loss(pairs: Iterable[tuple[float, int]]) -> float | None:
    rows = [(max(1e-6, min(1 - 1e-6, float(p))), int(y)) for p, y in pairs]
    if not rows:
        return None
    return -sum(y * log(p) + (1 - y) * log(1 - p) for p, y in rows) / len(rows)


def expected_calibration_error(
    pairs: Iterable[tuple[float, int]],
    *,
    bins: int = 10,
) -> float | None:
    rows = [(max(0.0, min(1.0, float(p))), int(y)) for p, y in pairs]
    if not rows:
        return None
    total = len(rows)
    error = 0.0
    for index in range(bins):
        low = index / bins
        high = (index + 1) / bins
        bucket = [
            (p, y)
            for p, y in rows
            if low <= p < high or (index == bins - 1 and p == 1.0)
        ]
        if not bucket:
            continue
        mean_probability = sum(p for p, _ in bucket) / len(bucket)
        observed_rate = sum(y for _, y in bucket) / len(bucket)
        error += len(bucket) / total * abs(mean_probability - observed_rate)
    return error
