from __future__ import annotations

import math

from trading_ai.daily.strike_selector import (
    TargetDeltaStrikeSelector,
)
from trading_ai.options.pricing_service import OptionPricingService


def main() -> None:
    pricing = OptionPricingService(
        risk_free_rate=0.04,
        default_dte=30,
    )
    selector = TargetDeltaStrikeSelector(
        pricing,
        target_delta=0.45,
        minimum_otm_pct=0.005,
        maximum_otm_pct=0.20,
    )

    cases = (
        ("CALL", 343.15, 0.25, 30),
        ("PUT", 364.96, 0.20, 30),
        ("CALL", 1169.17, 0.30, 30),
    )

    for signal, spot, volatility, dte in cases:
        result = selector.select(
            signal=signal,
            spot=spot,
            volatility=volatility,
            dte=dte,
        )

        assert result.strike != spot

        if signal == "CALL":
            assert result.strike > spot
            assert result.moneyness_pct > 0
        else:
            assert result.strike < spot
            assert result.moneyness_pct < 0

        assert result.increment > 0
        assert math.isfinite(result.estimated_delta)
        assert abs(result.estimated_delta) <= 1.0

    jpm = selector.select(
        signal="CALL",
        spot=343.15,
        volatility=0.25,
        dte=30,
    )
    gld = selector.select(
        signal="PUT",
        spot=364.96,
        volatility=0.20,
        dte=30,
    )
    lly = selector.select(
        signal="CALL",
        spot=1169.17,
        volatility=0.30,
        dte=30,
    )

    print(
        f"JPM proxy: spot=343.15 strike={jpm.strike:.2f} "
        f"delta={jpm.estimated_delta:.4f}"
    )
    print(
        f"GLD proxy: spot=364.96 strike={gld.strike:.2f} "
        f"delta={gld.estimated_delta:.4f}"
    )
    print(
        f"LLY proxy: spot=1169.17 strike={lly.strike:.2f} "
        f"delta={lly.estimated_delta:.4f}"
    )
    print("All target-delta strike-selection assertions passed.")


if __name__ == "__main__":
    main()
