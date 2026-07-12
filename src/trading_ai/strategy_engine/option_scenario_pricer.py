import math
from datetime import date, datetime


class OptionScenarioPricer:
    """
    Black-Scholes scenario pricer.

    This pricer values remaining option time after a deterministic
    price, volatility, rate, and time shock.

    At zero DTE, intrinsic value is returned.
    """

    def __init__(
        self,
        annual_calendar_days: int = 365,
    ):
        self.annual_calendar_days = max(
            int(annual_calendar_days or 365),
            1,
        )

    def price_leg(
        self,
        leg,
        underlying_price: float,
        volatility: float,
        days_to_expiry: int,
        risk_free_rate: float,
        dividend_yield: float = 0.0,
    ) -> float:
        option_type = str(
            leg.option_type
        ).upper()

        price = self.price_option(
            option_type=option_type,
            underlying_price=underlying_price,
            strike=float(leg.strike),
            volatility=volatility,
            days_to_expiry=days_to_expiry,
            risk_free_rate=risk_free_rate,
            dividend_yield=dividend_yield,
        )

        return (
            price
            * int(leg.quantity or 1)
            * float(leg.sign)
        )

    def price_option(
        self,
        option_type: str,
        underlying_price: float,
        strike: float,
        volatility: float,
        days_to_expiry: int,
        risk_free_rate: float,
        dividend_yield: float = 0.0,
    ) -> float:
        option_type = str(
            option_type or ""
        ).upper()

        s = float(underlying_price)
        k = float(strike)
        sigma = float(volatility)
        days = max(
            int(days_to_expiry),
            0,
        )

        r = float(risk_free_rate)
        q = float(dividend_yield)

        if s <= 0 or k <= 0:
            return 0.0

        if days <= 0 or sigma <= 0:
            return self.intrinsic_value(
                option_type=option_type,
                underlying_price=s,
                strike=k,
            )

        t = days / self.annual_calendar_days

        sqrt_t = math.sqrt(t)

        d1 = (
            math.log(s / k)
            + (
                r
                - q
                + 0.5 * sigma * sigma
            )
            * t
        ) / (
            sigma * sqrt_t
        )

        d2 = d1 - sigma * sqrt_t

        discounted_spot = (
            s
            * math.exp(-q * t)
        )

        discounted_strike = (
            k
            * math.exp(-r * t)
        )

        if option_type == "CALL":
            return max(
                discounted_spot
                * self._normal_cdf(d1)
                - discounted_strike
                * self._normal_cdf(d2),
                0.0,
            )

        if option_type == "PUT":
            return max(
                discounted_strike
                * self._normal_cdf(-d2)
                - discounted_spot
                * self._normal_cdf(-d1),
                0.0,
            )

        raise ValueError(
            f"Unsupported option type: {option_type}"
        )

    def structure_value(
        self,
        structure,
        underlying_price: float,
        volatility: float,
        days_forward: int,
        risk_free_rate: float,
        dividend_yield: float = 0.0,
        base_days_to_expiry: int | None = None,
    ) -> float:
        total_per_share = 0.0

        for leg in structure.legs:
            leg_dte = self._leg_days_to_expiry(
                leg=leg,
                base_days_to_expiry=base_days_to_expiry,
            )

            stressed_dte = max(
                leg_dte - int(days_forward or 0),
                0,
            )

            total_per_share += self.price_leg(
                leg=leg,
                underlying_price=underlying_price,
                volatility=volatility,
                days_to_expiry=stressed_dte,
                risk_free_rate=risk_free_rate,
                dividend_yield=dividend_yield,
            )

        return (
            total_per_share
            * 100.0
            * int(structure.contracts or 1)
        )

    def intrinsic_value(
        self,
        option_type: str,
        underlying_price: float,
        strike: float,
    ) -> float:
        if option_type == "CALL":
            return max(
                underlying_price - strike,
                0.0,
            )

        if option_type == "PUT":
            return max(
                strike - underlying_price,
                0.0,
            )

        raise ValueError(
            f"Unsupported option type: {option_type}"
        )

    def _leg_days_to_expiry(
        self,
        leg,
        base_days_to_expiry,
    ) -> int:
        explicit = getattr(
            leg,
            "dte",
            None,
        )

        if explicit is not None:
            try:
                return max(
                    int(explicit),
                    0,
                )
            except (
                TypeError,
                ValueError,
            ):
                pass

        if base_days_to_expiry is not None:
            return max(
                int(base_days_to_expiry),
                0,
            )

        expiry_text = str(
            getattr(
                leg,
                "expiry",
                "",
            )
            or ""
        )

        if expiry_text:
            try:
                expiry_date = (
                    datetime.fromisoformat(
                        expiry_text
                    ).date()
                )

                return max(
                    (
                        expiry_date
                        - date.today()
                    ).days,
                    0,
                )
            except ValueError:
                pass

        return 0

    def _normal_cdf(
        self,
        value: float,
    ) -> float:
        return 0.5 * (
            1.0
            + math.erf(
                value
                / math.sqrt(2.0)
            )
        )
