from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any


@dataclass(frozen=True)
class StrikeSelection:
    signal: str
    spot: float
    raw_strike: float
    strike: float
    target_delta: float
    estimated_delta: float
    increment: float
    moneyness_pct: float


class TargetDeltaStrikeSelector:
    """
    Select a proxy option strike by target absolute delta.

    CALL searches for an out-of-the-money strike above spot.
    PUT searches for an out-of-the-money strike below spot.

    Because the daily scanner uses Black-Scholes proxy prices rather than a
    live option chain, target-delta selection produces a more meaningful strike
    than forcing strike == underlying.
    """

    def __init__(
        self,
        pricing_service: Any,
        *,
        target_delta: float = 0.45,
        minimum_otm_pct: float = 0.005,
        maximum_otm_pct: float = 0.20,
        search_iterations: int = 60,
    ) -> None:
        target_delta = float(target_delta)
        minimum_otm_pct = float(minimum_otm_pct)
        maximum_otm_pct = float(maximum_otm_pct)

        if not 0.05 <= target_delta <= 0.90:
            raise ValueError("target_delta must be between 0.05 and 0.90")
        if minimum_otm_pct < 0:
            raise ValueError("minimum_otm_pct cannot be negative")
        if maximum_otm_pct <= minimum_otm_pct:
            raise ValueError(
                "maximum_otm_pct must be greater than minimum_otm_pct"
            )
        if search_iterations <= 0:
            raise ValueError("search_iterations must be positive")

        self.pricing = pricing_service
        self.target_delta = target_delta
        self.minimum_otm_pct = minimum_otm_pct
        self.maximum_otm_pct = maximum_otm_pct
        self.search_iterations = int(search_iterations)

    @staticmethod
    def strike_increment(spot: float) -> float:
        """Return a practical proxy increment based on underlying price."""
        spot = float(spot)
        if spot < 25.0:
            return 0.50
        if spot < 100.0:
            return 1.00
        if spot < 200.0:
            return 2.50
        if spot < 500.0:
            return 5.00
        if spot < 1000.0:
            return 10.00
        return 25.00

    @staticmethod
    def _round_to_increment(value: float, increment: float) -> float:
        return round(float(value) / increment) * increment

    def _delta(
        self,
        *,
        signal: str,
        spot: float,
        strike: float,
        volatility: float,
        dte: int,
    ) -> float:
        greeks = self.pricing.greeks(
            signal=signal,
            spot=spot,
            strike=strike,
            hv20=volatility,
            dte=dte,
        )
        return float(greeks["delta"])

    def _search_raw_strike(
        self,
        *,
        signal: str,
        spot: float,
        volatility: float,
        dte: int,
        target_delta: float,
    ) -> float:
        signal = signal.upper()

        if signal == "CALL":
            low = spot * (1.0 + self.minimum_otm_pct)
            high = spot * (1.0 + self.maximum_otm_pct)

            for _ in range(self.search_iterations):
                middle = (low + high) / 2.0
                abs_delta = abs(
                    self._delta(
                        signal=signal,
                        spot=spot,
                        strike=middle,
                        volatility=volatility,
                        dte=dte,
                    )
                )
                # Call delta decreases as strike increases.
                if abs_delta > target_delta:
                    low = middle
                else:
                    high = middle

            return (low + high) / 2.0

        if signal == "PUT":
            low = spot * (1.0 - self.maximum_otm_pct)
            high = spot * (1.0 - self.minimum_otm_pct)

            for _ in range(self.search_iterations):
                middle = (low + high) / 2.0
                abs_delta = abs(
                    self._delta(
                        signal=signal,
                        spot=spot,
                        strike=middle,
                        volatility=volatility,
                        dte=dte,
                    )
                )
                # Absolute put delta increases as strike increases.
                if abs_delta < target_delta:
                    low = middle
                else:
                    high = middle

            return (low + high) / 2.0

        raise ValueError(f"Unsupported signal: {signal}")

    def _enforce_otm(
        self,
        *,
        signal: str,
        spot: float,
        strike: float,
        increment: float,
    ) -> float:
        signal = signal.upper()

        if signal == "CALL":
            minimum = spot * (1.0 + self.minimum_otm_pct)
            strike = max(strike, minimum)
            strike = math.ceil(strike / increment) * increment

            if strike <= spot:
                strike = (
                    math.floor(spot / increment) * increment
                    + increment
                )
            return strike

        maximum = spot * (1.0 - self.minimum_otm_pct)
        strike = min(strike, maximum)
        strike = math.floor(strike / increment) * increment

        if strike >= spot:
            strike = (
                math.ceil(spot / increment) * increment
                - increment
            )
        return max(strike, increment)

    def select(
        self,
        *,
        signal: str,
        spot: float,
        volatility: float,
        dte: int,
        target_delta: float | None = None,
    ) -> StrikeSelection:
        signal = str(signal).strip().upper()
        spot = float(spot)
        volatility = max(float(volatility), 0.0001)
        dte = int(dte)
        target = (
            self.target_delta
            if target_delta is None
            else float(target_delta)
        )

        if spot <= 0:
            raise ValueError("spot must be positive")
        if dte <= 0:
            raise ValueError("dte must be positive")

        raw = self._search_raw_strike(
            signal=signal,
            spot=spot,
            volatility=volatility,
            dte=dte,
            target_delta=target,
        )

        increment = self.strike_increment(spot)
        rounded = self._round_to_increment(raw, increment)
        strike = self._enforce_otm(
            signal=signal,
            spot=spot,
            strike=rounded,
            increment=increment,
        )

        estimated_delta = self._delta(
            signal=signal,
            spot=spot,
            strike=strike,
            volatility=volatility,
            dte=dte,
        )

        return StrikeSelection(
            signal=signal,
            spot=spot,
            raw_strike=float(raw),
            strike=float(strike),
            target_delta=float(target),
            estimated_delta=float(estimated_delta),
            increment=float(increment),
            moneyness_pct=(float(strike) / spot) - 1.0,
        )
