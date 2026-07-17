from __future__ import annotations

import math
from typing import Literal


OptionType = Literal["CALL", "PUT"]


class BlackScholesPricingEngine:
    """
    Black-Scholes pricing engine using days-to-expiry.

    This preserves the existing project API used by option analytics and
    backtesting code.
    """

    def __init__(self, risk_free_rate: float = 0.04) -> None:
        self.risk_free_rate = float(risk_free_rate)

    @staticmethod
    def _norm_cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    @staticmethod
    def _norm_pdf(x: float) -> float:
        return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

    @staticmethod
    def _normalize_option_type(option_type: str) -> OptionType:
        normalized = str(option_type).strip().upper()
        if normalized in {"C", "CALL"}:
            return "CALL"
        if normalized in {"P", "PUT"}:
            return "PUT"
        raise ValueError(f"Unsupported option type: {option_type}")

    @staticmethod
    def _validate_inputs(
        spot: float,
        strike: float,
        volatility: float,
    ) -> tuple[float, float, float]:
        spot_value = float(spot)
        strike_value = float(strike)
        volatility_value = float(volatility)

        if spot_value <= 0:
            raise ValueError("spot must be positive")
        if strike_value <= 0:
            raise ValueError("strike must be positive")
        if volatility_value < 0:
            raise ValueError("volatility cannot be negative")

        return spot_value, strike_value, max(volatility_value, 0.0001)

    @staticmethod
    def _time_years(days_to_expiry: float) -> float:
        return max(float(days_to_expiry) / 365.0, 1.0 / 365.0)

    def _d1_d2(
        self,
        spot: float,
        strike: float,
        volatility: float,
        days_to_expiry: float,
    ) -> tuple[float, float, float]:
        spot, strike, volatility = self._validate_inputs(
            spot,
            strike,
            volatility,
        )
        time_years = self._time_years(days_to_expiry)
        root_time = math.sqrt(time_years)

        d1 = (
            math.log(spot / strike)
            + (
                self.risk_free_rate
                + 0.5 * volatility * volatility
            )
            * time_years
        ) / (volatility * root_time)
        d2 = d1 - volatility * root_time
        return d1, d2, time_years

    def call_price(
        self,
        spot: float,
        strike: float,
        volatility: float,
        days_to_expiry: float,
    ) -> float:
        d1, d2, time_years = self._d1_d2(
            spot,
            strike,
            volatility,
            days_to_expiry,
        )
        return (
            float(spot) * self._norm_cdf(d1)
            - float(strike)
            * math.exp(-self.risk_free_rate * time_years)
            * self._norm_cdf(d2)
        )

    def put_price(
        self,
        spot: float,
        strike: float,
        volatility: float,
        days_to_expiry: float,
    ) -> float:
        d1, d2, time_years = self._d1_d2(
            spot,
            strike,
            volatility,
            days_to_expiry,
        )
        return (
            float(strike)
            * math.exp(-self.risk_free_rate * time_years)
            * self._norm_cdf(-d2)
            - float(spot) * self._norm_cdf(-d1)
        )

    def price(
        self,
        option_type: str,
        spot: float,
        strike: float,
        volatility: float,
        days_to_expiry: float,
    ) -> float:
        normalized = self._normalize_option_type(option_type)
        if normalized == "CALL":
            return self.call_price(
                spot,
                strike,
                volatility,
                days_to_expiry,
            )
        return self.put_price(
            spot,
            strike,
            volatility,
            days_to_expiry,
        )

    def delta(
        self,
        option_type: str,
        spot: float,
        strike: float,
        volatility: float,
        days_to_expiry: float,
    ) -> float:
        d1, _, _ = self._d1_d2(
            spot,
            strike,
            volatility,
            days_to_expiry,
        )
        normalized = self._normalize_option_type(option_type)
        if normalized == "CALL":
            return self._norm_cdf(d1)
        return self._norm_cdf(d1) - 1.0

    def gamma(
        self,
        spot: float,
        strike: float,
        volatility: float,
        days_to_expiry: float,
    ) -> float:
        d1, _, time_years = self._d1_d2(
            spot,
            strike,
            volatility,
            days_to_expiry,
        )
        return self._norm_pdf(d1) / (
            float(spot)
            * max(float(volatility), 0.0001)
            * math.sqrt(time_years)
        )

    def vega(
        self,
        spot: float,
        strike: float,
        volatility: float,
        days_to_expiry: float,
    ) -> float:
        d1, _, time_years = self._d1_d2(
            spot,
            strike,
            volatility,
            days_to_expiry,
        )
        return (
            float(spot)
            * self._norm_pdf(d1)
            * math.sqrt(time_years)
            / 100.0
        )

    def theta(
        self,
        option_type: str,
        spot: float,
        strike: float,
        volatility: float,
        days_to_expiry: float,
    ) -> float:
        d1, d2, time_years = self._d1_d2(
            spot,
            strike,
            volatility,
            days_to_expiry,
        )
        spot = float(spot)
        strike = float(strike)
        volatility = max(float(volatility), 0.0001)

        first = (
            -spot
            * self._norm_pdf(d1)
            * volatility
            / (2.0 * math.sqrt(time_years))
        )
        normalized = self._normalize_option_type(option_type)
        if normalized == "CALL":
            second = (
                -self.risk_free_rate
                * strike
                * math.exp(-self.risk_free_rate * time_years)
                * self._norm_cdf(d2)
            )
        else:
            second = (
                self.risk_free_rate
                * strike
                * math.exp(-self.risk_free_rate * time_years)
                * self._norm_cdf(-d2)
            )
        return (first + second) / 365.0

    def rho(
        self,
        option_type: str,
        spot: float,
        strike: float,
        volatility: float,
        days_to_expiry: float,
    ) -> float:
        _, d2, time_years = self._d1_d2(
            spot,
            strike,
            volatility,
            days_to_expiry,
        )
        strike = float(strike)
        normalized = self._normalize_option_type(option_type)
        if normalized == "CALL":
            return (
                strike
                * time_years
                * math.exp(-self.risk_free_rate * time_years)
                * self._norm_cdf(d2)
                / 100.0
            )
        return (
            -strike
            * time_years
            * math.exp(-self.risk_free_rate * time_years)
            * self._norm_cdf(-d2)
            / 100.0
        )


class BlackScholesPricer:
    """
    Backward-compatible pricer using time-to-expiry in years.

    Paper-trading scripts historically import BlackScholesPricer and call:

        price(
            spot=...,
            strike=...,
            time_to_expiry=...,
            volatility=...,
            option_type=...,
        )

    The canonical BlackScholesPricingEngine uses days_to_expiry. This adapter
    keeps both APIs available without changing existing callers.
    """

    def __init__(self, risk_free_rate: float = 0.04) -> None:
        self.risk_free_rate = float(risk_free_rate)
        self.engine = BlackScholesPricingEngine(
            risk_free_rate=self.risk_free_rate
        )

    @staticmethod
    def _to_days(
        *,
        time_to_expiry: float | None = None,
        days_to_expiry: float | None = None,
    ) -> float:
        if days_to_expiry is not None:
            return max(float(days_to_expiry), 1.0)
        if time_to_expiry is None:
            raise TypeError(
                "Either time_to_expiry (years) or days_to_expiry is required"
            )
        return max(float(time_to_expiry) * 365.0, 1.0)

    def price(
        self,
        *,
        spot: float,
        strike: float,
        volatility: float,
        option_type: str,
        time_to_expiry: float | None = None,
        days_to_expiry: float | None = None,
    ) -> float:
        return self.engine.price(
            option_type=option_type,
            spot=spot,
            strike=strike,
            volatility=volatility,
            days_to_expiry=self._to_days(
                time_to_expiry=time_to_expiry,
                days_to_expiry=days_to_expiry,
            ),
        )

    def delta(
        self,
        *,
        spot: float,
        strike: float,
        volatility: float,
        option_type: str,
        time_to_expiry: float | None = None,
        days_to_expiry: float | None = None,
    ) -> float:
        return self.engine.delta(
            option_type=option_type,
            spot=spot,
            strike=strike,
            volatility=volatility,
            days_to_expiry=self._to_days(
                time_to_expiry=time_to_expiry,
                days_to_expiry=days_to_expiry,
            ),
        )

    def gamma(
        self,
        *,
        spot: float,
        strike: float,
        volatility: float,
        time_to_expiry: float | None = None,
        days_to_expiry: float | None = None,
    ) -> float:
        return self.engine.gamma(
            spot=spot,
            strike=strike,
            volatility=volatility,
            days_to_expiry=self._to_days(
                time_to_expiry=time_to_expiry,
                days_to_expiry=days_to_expiry,
            ),
        )

    def vega(
        self,
        *,
        spot: float,
        strike: float,
        volatility: float,
        time_to_expiry: float | None = None,
        days_to_expiry: float | None = None,
    ) -> float:
        return self.engine.vega(
            spot=spot,
            strike=strike,
            volatility=volatility,
            days_to_expiry=self._to_days(
                time_to_expiry=time_to_expiry,
                days_to_expiry=days_to_expiry,
            ),
        )

    def theta(
        self,
        *,
        spot: float,
        strike: float,
        volatility: float,
        option_type: str,
        time_to_expiry: float | None = None,
        days_to_expiry: float | None = None,
    ) -> float:
        return self.engine.theta(
            option_type=option_type,
            spot=spot,
            strike=strike,
            volatility=volatility,
            days_to_expiry=self._to_days(
                time_to_expiry=time_to_expiry,
                days_to_expiry=days_to_expiry,
            ),
        )

    def rho(
        self,
        *,
        spot: float,
        strike: float,
        volatility: float,
        option_type: str,
        time_to_expiry: float | None = None,
        days_to_expiry: float | None = None,
    ) -> float:
        return self.engine.rho(
            option_type=option_type,
            spot=spot,
            strike=strike,
            volatility=volatility,
            days_to_expiry=self._to_days(
                time_to_expiry=time_to_expiry,
                days_to_expiry=days_to_expiry,
            ),
        )
