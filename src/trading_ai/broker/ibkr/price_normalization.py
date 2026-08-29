from __future__ import annotations

from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from typing import Iterable, Mapping

_EPS = Decimal("0.000000000001")


def _decimal(value: float | str | Decimal) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def select_price_increment(price: float, price_increments: Iterable[Mapping[str, float]], fallback_min_tick: float) -> float:
    """Return the IBKR order increment applicable at *price*.

    IBKR market rules are a set of ``(lowEdge, increment)`` bands. The active
    increment is the band with the greatest low edge not exceeding the
    absolute order price. ``ContractDetails.minTick`` is used only when a
    market rule cannot be resolved.
    """
    target = abs(float(price))
    bands: list[tuple[float, float]] = []
    for row in price_increments or ():
        try:
            low = float(row.get("low_edge", row.get("lowEdge", 0.0)) or 0.0)
            inc = float(row.get("increment", 0.0) or 0.0)
        except (TypeError, ValueError, AttributeError):
            continue
        if inc > 0:
            bands.append((low, inc))
    eligible = [row for row in bands if row[0] <= target + 1e-12]
    if eligible:
        return float(max(eligible, key=lambda row: row[0])[1])
    if bands:
        return float(min(bands, key=lambda row: row[0])[1])
    fallback = float(fallback_min_tick or 0.0)
    if fallback <= 0:
        raise ValueError("IBKR did not expose a usable market-rule increment or minTick")
    return fallback


def snap_limit_price(price: float, increment: float, side: str) -> float:
    """Snap a positive limit to a legal tick without worsening the limit.

    BUY limits are floored so normalization never pays more than the governed
    maximum. SELL limits are ceiled so normalization never accepts less than
    the governed minimum credit.
    """
    px = _decimal(abs(float(price)))
    tick = _decimal(increment)
    if tick <= 0:
        raise ValueError("minimum price increment must be positive")
    action = str(side or "").upper()
    if action not in {"BUY", "SELL"}:
        raise ValueError(f"unsupported order side for price normalization: {side!r}")
    rounding = ROUND_FLOOR if action == "BUY" else ROUND_CEILING
    ticks = (px / tick).to_integral_value(rounding=rounding)
    snapped = ticks * tick
    if snapped <= 0 and px > 0:
        snapped = tick
    return float(snapped)


def snap_signed_combo_price(price: float, increment: float) -> float:
    """Snap an IBKR BAG signed net price while preserving economic limits.

    TradingPlatform submits combo parents as BUY BAG orders. A positive signed
    price is a net debit, so it is floored to avoid paying above the governed
    debit. A negative signed price is a net credit, so its absolute value is
    ceiled and the sign restored to avoid accepting less credit.
    """
    value = float(price)
    if abs(value) <= 1e-15:
        raise ValueError("combo limit price must be non-zero")
    if value > 0:
        return snap_limit_price(value, increment, "BUY")
    return -snap_limit_price(abs(value), increment, "SELL")


def is_price_on_increment(price: float, increment: float) -> bool:
    """Return True only when *price* is an exact multiple of *increment*."""
    tick = _decimal(increment)
    if tick <= 0:
        return False
    px = abs(_decimal(price))
    quotient = px / tick
    nearest = quotient.to_integral_value()
    return abs(quotient - nearest) <= _EPS


def _stabilize(price: float, side: str | None, price_increments, fallback_min_tick: float, *, signed_combo: bool) -> tuple[float, float]:
    """Normalize until the selected market-rule band is stable.

    Snapping can theoretically cross a market-rule lowEdge. Re-selecting the
    increment at the snapped price prevents a price that is legal under the
    original band but illegal under the resulting band.
    """
    current = float(price)
    increment = 0.0
    for _ in range(6):
        increment = select_price_increment(current, price_increments, fallback_min_tick)
        snapped = snap_signed_combo_price(current, increment) if signed_combo else snap_limit_price(current, increment, str(side))
        next_increment = select_price_increment(snapped, price_increments, fallback_min_tick)
        if abs(next_increment - increment) <= 1e-15 and is_price_on_increment(snapped, increment):
            return float(snapped), float(increment)
        current = float(snapped)
    raise ValueError("IBKR price normalization did not converge to a legal market-rule increment")


def normalize_limit_price(price: float, side: str, price_increments: Iterable[Mapping[str, float]], fallback_min_tick: float) -> dict:
    increments = list(price_increments or ())
    normalized, increment = _stabilize(float(price), str(side), increments, float(fallback_min_tick or 0.0), signed_combo=False)
    valid = is_price_on_increment(normalized, increment)
    if not valid:
        raise ValueError(f"normalized broker price {normalized} is not valid for increment {increment}")
    return {
        "requested_price": float(price),
        "normalized_price": normalized,
        "increment": increment,
        "side": str(side or "").upper(),
        "changed": abs(normalized - abs(float(price))) > 1e-12,
        "valid": True,
    }


def normalize_signed_combo_price(price: float, price_increments: Iterable[Mapping[str, float]], fallback_min_tick: float) -> dict:
    increments = list(price_increments or ())
    normalized, increment = _stabilize(float(price), None, increments, float(fallback_min_tick or 0.0), signed_combo=True)
    valid = is_price_on_increment(normalized, increment)
    if not valid:
        raise ValueError(f"normalized BAG price {normalized} is not valid for increment {increment}")
    return {
        "requested_price": float(price),
        "normalized_price": normalized,
        "increment": increment,
        "economic_side": "NET_DEBIT" if float(price) > 0 else "NET_CREDIT",
        "changed": abs(normalized - float(price)) > 1e-12,
        "valid": True,
    }
