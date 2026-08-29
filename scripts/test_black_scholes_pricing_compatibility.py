from __future__ import annotations

import math

from trading_ai.options.pricing import (
    BlackScholesPricer,
    BlackScholesPricingEngine,
)


def main() -> None:
    engine = BlackScholesPricingEngine(risk_free_rate=0.04)
    adapter = BlackScholesPricer(risk_free_rate=0.04)

    call_days = engine.price(
        option_type="CALL",
        spot=100.0,
        strike=100.0,
        volatility=0.20,
        days_to_expiry=30,
    )
    call_years = adapter.price(
        option_type="CALL",
        spot=100.0,
        strike=100.0,
        volatility=0.20,
        time_to_expiry=30.0 / 365.0,
    )
    call_direct_days = adapter.price(
        option_type="C",
        spot=100.0,
        strike=100.0,
        volatility=0.20,
        days_to_expiry=30,
    )

    assert call_days > 0
    assert math.isclose(call_days, call_years, rel_tol=1e-12)
    assert math.isclose(call_days, call_direct_days, rel_tol=1e-12)

    put_price = adapter.price(
        option_type="PUT",
        spot=100.0,
        strike=105.0,
        volatility=0.25,
        time_to_expiry=45.0 / 365.0,
    )
    assert put_price > 0

    call_delta = adapter.delta(
        option_type="CALL",
        spot=100.0,
        strike=100.0,
        volatility=0.20,
        time_to_expiry=30.0 / 365.0,
    )
    put_delta = adapter.delta(
        option_type="PUT",
        spot=100.0,
        strike=100.0,
        volatility=0.20,
        time_to_expiry=30.0 / 365.0,
    )
    assert 0 < call_delta < 1
    assert -1 < put_delta < 0

    print("All Black-Scholes compatibility assertions passed.")


if __name__ == "__main__":
    main()
