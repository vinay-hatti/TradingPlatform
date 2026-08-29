from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

_EPS = 1e-9


def same_price(a: float, b: float, tolerance: float = 1e-9) -> bool:
    return abs(float(a) - float(b)) <= max(float(tolerance), _EPS)


def monotonic_broker_candidate(side: str, current_price: float, candidate_price: float) -> float:
    """Never make an entry chase less aggressive.

    BUY entry limits may stay the same or rise. SELL entry limits may stay the
    same or fall. This is deliberately broker-price based (always positive).
    """
    side = str(side or '').upper()
    current = max(0.0, float(current_price))
    candidate = max(0.0, float(candidate_price))
    if side == 'BUY':
        return max(current, candidate)
    if side == 'SELL':
        return min(current, candidate) if current > 0 else candidate
    return candidate


def _round_price(value: float) -> float:
    return float(Decimal(str(float(value))).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))


def advance_coarse_tick(
    *,
    side: str,
    current_price: float,
    theoretical_price: float,
    normalized_price: float,
    increment: float,
    maximum_debit: float | None = None,
    minimum_credit: float | None = None,
    executable_price: float | None = None,
) -> dict:
    """Advance one legal tick only when the theoretical chase justifies it.

    IBKR market-rule normalization floors BUYs and ceilings SELLs. With coarse
    ticks that can produce repeated theoretical prices mapping to the same
    broker price. Once the theoretical price has crossed half of the next legal
    tick, permit one legal-tick step, but never cross the frozen approval
    envelope or the currently executable quote.
    """
    side = str(side or '').upper()
    current = max(0.0, float(current_price))
    theoretical = max(0.0, float(theoretical_price))
    normalized = max(0.0, float(normalized_price))
    inc = max(0.0, float(increment or 0.0))
    if inc <= _EPS or not same_price(normalized, current):
        return {'price': normalized, 'advanced': False, 'reason': 'NORMALIZED_PRICE_CHANGED'}

    half = inc / 2.0
    executable = None if executable_price is None else max(0.0, float(executable_price))
    if side == 'BUY' and theoretical > current + _EPS:
        nxt = _round_price(current + inc)
        justified = theoretical + _EPS >= current + half
        inside_envelope = maximum_debit is None or nxt <= float(maximum_debit) + _EPS
        inside_market = executable is None or executable <= 0 or nxt <= executable + _EPS
        if justified and inside_envelope and inside_market:
            return {'price': nxt, 'advanced': True, 'reason': 'ADVANCE_NEXT_LEGAL_TICK'}
    elif side == 'SELL' and theoretical < current - _EPS:
        nxt = _round_price(max(0.0, current - inc))
        justified = theoretical <= current - half + _EPS
        inside_envelope = minimum_credit is None or nxt + _EPS >= float(minimum_credit)
        inside_market = executable is None or executable <= 0 or nxt + _EPS >= executable
        if justified and inside_envelope and inside_market:
            return {'price': nxt, 'advanced': True, 'reason': 'ADVANCE_NEXT_LEGAL_TICK'}
    return {'price': current, 'advanced': False, 'reason': 'WAIT_TICK_UNCHANGED'}


def working_order_lifetime_phase(age_seconds: float | None, active_chase_window_seconds: float, maximum_working_order_age_seconds: float) -> dict:
    """Classify a working entry into active-chase, resting, or hard-timeout phase.

    The active chase window controls broker modifications. It is not a terminal
    condition. A valid order rests after active chase and is cancelled only at
    the governed hard timeout.
    """
    age=max(0.0,float(age_seconds or 0.0))
    active=max(0.0,float(active_chase_window_seconds or 0.0))
    hard=max(0.0,float(maximum_working_order_age_seconds or 0.0))
    if hard<=0: raise ValueError('maximum_working_order_age_seconds must be positive')
    if active>hard: raise ValueError('active_chase_window_seconds cannot exceed maximum_working_order_age_seconds')
    if age>hard:
        return {'phase':'HARD_TIMEOUT','reason':'ORDER_AGE_EXCEEDED','cancel_required':True}
    if age>=active:
        return {'phase':'RESTING','reason':'RESTING_AT_FINAL_LIMIT','cancel_required':False}
    return {'phase':'ACTIVE_CHASE','reason':'ACTIVE_CHASE','cancel_required':False}


def adaptive_chase_state(
    *,
    current_price: float,
    fresh_executable_price: float,
    frozen_boundary_price: float,
    age_seconds: float | None,
    active_chase_window_seconds: float,
    maximum_working_order_age_seconds: float,
    reprice_count: int,
    fast_reprice_limit: int,
    adaptive_enabled: bool = True,
) -> dict:
    """Classify a signed-economic working price into fast, adaptive, resting or timeout.

    Signed economic prices make aggressiveness monotonic in one direction for both
    debit/BUY and credit/SELL entries: a more aggressive entry is always a larger
    signed value.  For a debit this means paying more; for a credit it means
    accepting less credit (moving a negative value toward zero).  The target is
    always the lesser of the fresh executable price and the frozen approval
    boundary, so the chase can never cross the user's governed economic limit.
    """
    current=float(current_price)
    executable=float(fresh_executable_price)
    boundary=float(frozen_boundary_price)
    target=min(executable,boundary)
    age=max(0.0,float(age_seconds or 0.0))
    hard=max(0.0,float(maximum_working_order_age_seconds or 0.0))
    active=max(0.0,float(active_chase_window_seconds or 0.0))
    if hard<=0:
        raise ValueError('maximum_working_order_age_seconds must be positive')
    if age>hard:
        return {'phase':'HARD_TIMEOUT','reason':'ORDER_AGE_EXCEEDED','cancel_required':True,'target_price':target,'needs_chase':False}
    needs=current + _EPS < target
    if not needs:
        if boundary <= executable + _EPS and current + _EPS >= boundary:
            reason='FROZEN_BOUNDARY_REACHED'
        else:
            reason='EXECUTABLE_PRICE_REACHED'
        return {'phase':'RESTING','reason':reason,'cancel_required':False,'target_price':target,'needs_chase':False}
    fast=age<active and int(reprice_count)<int(fast_reprice_limit)
    if fast:
        return {'phase':'ACTIVE_CHASE','reason':'FAST_CHASE_ROOM_REMAINS','cancel_required':False,'target_price':target,'needs_chase':True}
    if adaptive_enabled:
        return {'phase':'ADAPTIVE_CHASE','reason':'ADAPTIVE_CHASE_ROOM_REMAINS','cancel_required':False,'target_price':target,'needs_chase':True}
    return {'phase':'RESTING','reason':'ADAPTIVE_CHASE_DISABLED','cancel_required':False,'target_price':target,'needs_chase':False}
