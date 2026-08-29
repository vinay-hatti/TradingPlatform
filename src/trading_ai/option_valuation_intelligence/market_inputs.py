from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from math import isfinite
from statistics import median
from typing import Any, Iterable, Mapping

POLICY_VERSION = "M69.7-COHERENT-MARKET-INPUTS-1.0"


class MarketInputValidationError(ValueError):
    """The recommendation cannot be valued from one coherent market snapshot."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CoherentMarketInputs:
    payload: dict[str, Any]
    market_date: date
    underlying_price: float
    dte_min: int
    dte_max: int
    option_symbols: tuple[str, ...]


def _value(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, Mapping):
        return row.get(key, default)
    return getattr(row, key, default)


def _date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif value in (None, ""):
        return None
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _market_date(row: Any) -> date | None:
    # quote_date is the capture date in legacy rows. New rows preserve the
    # provider timestamp so a weekend capture can still be identified as a
    # Friday market quote.
    source_timestamp = _timestamp(_value(row, "quote_timestamp"))
    return source_timestamp.date() if source_timestamp else _date(_value(row, "quote_date"))


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def resolve_coherent_market_inputs(
    *,
    contract: Mapping[str, Any],
    option_rows: Iterable[Any],
    price_rows: Iterable[Any],
) -> CoherentMarketInputs:
    """Refresh every leg from one exact, current market date.

    The function is intentionally independent from SQLAlchemy so the temporal
    contract can be regression-tested with the PSX failure fixture. It never
    mixes a newer underlying with older option-leg quotes.
    """
    payload = deepcopy(dict(contract or {}))
    legs = payload.get("legs")
    if not isinstance(legs, list) or not legs:
        raise MarketInputValidationError("NO_LEGS", "recommendation has no option legs")

    option_symbols = tuple(str(leg.get("option_symbol") or "").strip().upper() for leg in legs)
    if any(not symbol for symbol in option_symbols) or len(set(option_symbols)) != len(option_symbols):
        raise MarketInputValidationError(
            "INVALID_LEG_IDENTITY", "every leg must have a distinct exact option symbol"
        )

    prices: dict[date, float] = {}
    for row in price_rows:
        price_date = _date(_value(row, "date"))
        close = _finite(_value(row, "close"))
        if price_date and close is not None and close > 0:
            prices[price_date] = close
    if not prices:
        raise MarketInputValidationError("NO_UNDERLYING_PRICE", "no governed underlying close is available")
    latest_price_date = max(prices)

    by_symbol_and_date: dict[str, dict[date, list[Any]]] = {
        symbol: {} for symbol in option_symbols
    }
    for row in option_rows:
        symbol = str(_value(row, "option_symbol") or "").strip().upper()
        if symbol not in by_symbol_and_date:
            continue
        market_date = _market_date(row)
        if market_date is None:
            continue
        by_symbol_and_date[symbol].setdefault(market_date, []).append(row)

    missing = [symbol for symbol, dates in by_symbol_and_date.items() if not dates]
    if missing:
        raise MarketInputValidationError(
            "MISSING_LEG_QUOTE", f"no persisted quote exists for: {', '.join(missing)}"
        )

    common_option_dates: set[date] | None = None
    for symbol in option_symbols:
        dates = set(by_symbol_and_date[symbol])
        common_option_dates = dates if common_option_dates is None else common_option_dates & dates
    common_option_dates = common_option_dates or set()
    if not common_option_dates:
        raise MarketInputValidationError(
            "NO_COHERENT_MARKET_DATE",
            "all option legs do not share a market date",
        )

    def source_prices_for(candidate_date: date) -> list[float]:
        values: list[float] = []
        for symbol in option_symbols:
            candidates = by_symbol_and_date[symbol][candidate_date]
            row = max(
                candidates,
                key=lambda item: (
                    _timestamp(_value(item, "quote_timestamp")) or datetime.min.replace(tzinfo=timezone.utc),
                    _date(_value(item, "quote_date")) or date.min,
                ),
            )
            value = _finite(_value(row, "source_underlying_price"))
            if value is None or value <= 0:
                return []
            values.append(value)
        return values

    coherent_source_dates = {
        candidate_date
        for candidate_date in common_option_dates
        if len(source_prices_for(candidate_date)) == len(option_symbols)
    }
    usable_dates = (common_option_dates & set(prices)) | coherent_source_dates
    if not usable_dates:
        raise MarketInputValidationError(
            "NO_COHERENT_UNDERLYING",
            "no complete option date has an exact underlying input",
        )
    latest_authoritative_date = max({latest_price_date} | coherent_source_dates)
    market_date = max(usable_dates)
    if market_date != latest_authoritative_date:
        raise MarketInputValidationError(
            "STALE_OPTION_PACKAGE",
            f"latest complete option package is {market_date}; current market session is {latest_authoritative_date}",
        )

    source_prices = source_prices_for(market_date)
    if source_prices:
        source_mid = median(source_prices)
        if (max(source_prices) - min(source_prices)) / source_mid > 0.01:
            raise MarketInputValidationError(
                "INCOHERENT_SOURCE_UNDERLYING",
                "option legs disagree materially on the source underlying price",
            )
        underlying_price = source_mid
        underlying_price_source = "POLYGON_SNAPSHOT"
    else:
        underlying_price = prices[market_date]
        underlying_price_source = "PRICE_HISTORY_EXACT_DATE"

    refreshed_legs: list[dict[str, Any]] = []
    dtes: list[int] = []
    quote_timestamps: list[str] = []
    for original_leg, symbol in zip(legs, option_symbols, strict=True):
        candidates = by_symbol_and_date[symbol][market_date]
        row = max(
            candidates,
            key=lambda item: (
                _timestamp(_value(item, "quote_timestamp")) or datetime.min.replace(tzinfo=timezone.utc),
                _date(_value(item, "quote_date")) or date.min,
            ),
        )
        bid = _finite(_value(row, "bid"))
        ask = _finite(_value(row, "ask"))
        last = _finite(_value(row, "last"))
        if bid is None or ask is None or bid < 0 or ask <= 0 or ask < bid:
            raise MarketInputValidationError(
                "INVALID_LEG_QUOTE", f"{symbol} does not have a valid executable bid/ask"
            )
        expiry = _date(_value(row, "expiry")) or _date(original_leg.get("expiry"))
        if expiry is None:
            raise MarketInputValidationError("MISSING_EXPIRY", f"{symbol} has no expiry")
        dte = (expiry - market_date).days
        if dte <= 0:
            raise MarketInputValidationError("EXPIRED_LEG", f"{symbol} expired on {expiry}")

        refreshed = dict(original_leg)
        for key in (
            "bid", "ask", "last", "volume", "open_interest", "implied_volatility",
            "delta", "gamma", "theta", "vega",
        ):
            value = _value(row, key)
            if value is not None:
                refreshed[key] = value
        refreshed.update({
            "option_symbol": symbol,
            "expiry": expiry.isoformat(),
            "quote_date": market_date.isoformat(),
            "dte": dte,
            "market_input_status": "CURRENT_COHERENT",
        })
        source_timestamp = _timestamp(_value(row, "quote_timestamp"))
        if source_timestamp:
            iso_timestamp = source_timestamp.isoformat().replace("+00:00", "Z")
            refreshed["quote_timestamp"] = iso_timestamp
            quote_timestamps.append(iso_timestamp)
        refreshed_legs.append(refreshed)
        dtes.append(dte)

    payload.update({
        "legs": refreshed_legs,
        "underlying_price": underlying_price,
        "underlying_price_as_of": market_date.isoformat(),
        "market_input_as_of": market_date.isoformat(),
        "quote_input_snapshot_id": f"coherent-options-{market_date.isoformat()}",
        "dte": min(dtes),
        "dte_min": min(dtes),
        "dte_max": max(dtes),
        "market_input_validation": {
            "status": "CURRENT_COHERENT",
            "policy_version": POLICY_VERSION,
            "market_date": market_date.isoformat(),
            "latest_underlying_date": latest_price_date.isoformat(),
            "latest_authoritative_date": latest_authoritative_date.isoformat(),
            "underlying_price_source": underlying_price_source,
            "complete_leg_count": len(refreshed_legs),
            "quote_timestamps": sorted(set(quote_timestamps)),
        },
    })
    return CoherentMarketInputs(
        payload=payload,
        market_date=market_date,
        underlying_price=underlying_price,
        dte_min=min(dtes),
        dte_max=max(dtes),
        option_symbols=option_symbols,
    )



def preload_coherent_market_inputs(session, *, requests: Iterable[tuple[str, str, Mapping[str, Any]]]) -> tuple[dict[str, CoherentMarketInputs], dict[str, MarketInputValidationError], dict[str, int]]:
    """Bulk-load coherent market inputs for a valuation run.

    This is semantically equivalent to calling ``load_coherent_market_inputs`` for
    every recommendation, but it performs a bounded set of bulk SQL queries and
    delegates the actual temporal validation to ``resolve_coherent_market_inputs``.
    """
    from collections import defaultdict
    from sqlalchemy import func, select

    from trading_ai.market.models import PriceHistory
    from trading_ai.market.option_models import OptionContractHistory

    normalized = [(str(k), str(sym).upper(), dict(contract or {})) for k, sym, contract in requests]
    if not normalized:
        return {}, {}, {"requests": 0, "price_rows": 0, "option_rows": 0}

    symbols = sorted({sym for _, sym, _ in normalized})
    latest_rows = session.execute(
        select(PriceHistory.symbol, func.max(PriceHistory.date).label("latest_date"))
        .where(PriceHistory.symbol.in_(symbols))
        .group_by(PriceHistory.symbol)
    ).all()
    latest_by_symbol = {str(sym): latest for sym, latest in latest_rows if latest is not None}

    all_option_symbols: set[str] = set()
    for _, _, contract in normalized:
        legs = contract.get("legs") if isinstance(contract, Mapping) else None
        for leg in legs or ():
            option_symbol = str(leg.get("option_symbol") or "").strip().upper()
            if option_symbol:
                all_option_symbols.add(option_symbol)

    usable_latest = list(latest_by_symbol.values())
    price_rows = []
    option_rows = []
    if usable_latest:
        global_start = min(usable_latest) - timedelta(days=10)
        global_end = max(usable_latest) + timedelta(days=4)
        price_rows = session.execute(
            select(PriceHistory).where(
                PriceHistory.symbol.in_(symbols),
                PriceHistory.date >= global_start,
                PriceHistory.date <= max(usable_latest),
            )
        ).scalars().all()
        if all_option_symbols:
            option_rows = session.execute(
                select(OptionContractHistory).where(
                    OptionContractHistory.option_symbol.in_(sorted(all_option_symbols)),
                    OptionContractHistory.quote_date >= global_start,
                    OptionContractHistory.quote_date <= global_end,
                )
            ).scalars().all()

    prices_by_symbol: dict[str, list[Any]] = defaultdict(list)
    for row in price_rows:
        prices_by_symbol[str(row.symbol)].append(row)
    options_by_symbol: dict[str, list[Any]] = defaultdict(list)
    for row in option_rows:
        options_by_symbol[str(row.option_symbol).strip().upper()].append(row)

    resolved: dict[str, CoherentMarketInputs] = {}
    errors: dict[str, MarketInputValidationError] = {}
    for key, symbol, contract in normalized:
        if symbol not in latest_by_symbol:
            errors[key] = MarketInputValidationError("NO_UNDERLYING_PRICE", f"no price history exists for {symbol}")
            continue
        legs = contract.get("legs") if isinstance(contract, Mapping) else None
        option_symbols = [str(leg.get("option_symbol") or "").strip().upper() for leg in (legs or [])]
        if not option_symbols or any(not item for item in option_symbols):
            errors[key] = MarketInputValidationError("INVALID_LEG_IDENTITY", "recommendation legs lack option symbols")
            continue
        latest_price_date = latest_by_symbol[symbol]
        window_start = latest_price_date - timedelta(days=10)
        window_end = latest_price_date + timedelta(days=4)
        selected_option_rows = [
            row for option_symbol in option_symbols for row in options_by_symbol.get(option_symbol, ())
            if window_start <= row.quote_date <= window_end
        ]
        selected_price_rows = [
            row for row in prices_by_symbol.get(symbol, ())
            if window_start <= row.date <= latest_price_date
        ]
        try:
            resolved[key] = resolve_coherent_market_inputs(
                contract=contract, option_rows=selected_option_rows, price_rows=selected_price_rows
            )
        except MarketInputValidationError as exc:
            errors[key] = exc

    return resolved, errors, {
        "requests": len(normalized),
        "symbols": len(symbols),
        "option_symbols": len(all_option_symbols),
        "price_rows": len(price_rows),
        "option_rows": len(option_rows),
    }

def load_coherent_market_inputs(session, *, symbol: str, contract: Mapping[str, Any]) -> CoherentMarketInputs:
    from sqlalchemy import desc, select

    from trading_ai.market.models import PriceHistory
    from trading_ai.market.option_models import OptionContractHistory

    latest_price = session.execute(
        select(PriceHistory)
        .where(PriceHistory.symbol == symbol)
        .order_by(desc(PriceHistory.date))
    ).scalars().first()
    if latest_price is None:
        raise MarketInputValidationError("NO_UNDERLYING_PRICE", f"no price history exists for {symbol}")

    legs = contract.get("legs") if isinstance(contract, Mapping) else None
    option_symbols = [str(leg.get("option_symbol") or "").strip().upper() for leg in (legs or [])]
    if not option_symbols or any(not item for item in option_symbols):
        raise MarketInputValidationError("INVALID_LEG_IDENTITY", "recommendation legs lack option symbols")

    window_start = latest_price.date - timedelta(days=10)
    window_end = latest_price.date + timedelta(days=4)
    option_rows = session.execute(
        select(OptionContractHistory).where(
            OptionContractHistory.option_symbol.in_(option_symbols),
            OptionContractHistory.quote_date >= window_start,
            OptionContractHistory.quote_date <= window_end,
        )
    ).scalars().all()
    price_rows = session.execute(
        select(PriceHistory).where(
            PriceHistory.symbol == symbol,
            PriceHistory.date >= window_start,
            PriceHistory.date <= latest_price.date,
        )
    ).scalars().all()
    return resolve_coherent_market_inputs(
        contract=contract,
        option_rows=option_rows,
        price_rows=price_rows,
    )
