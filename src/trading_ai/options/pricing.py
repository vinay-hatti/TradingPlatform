import math


class BlackScholesPricingEngine:

    def __init__(self, risk_free_rate=0.04):
        self.risk_free_rate = float(risk_free_rate)

    def _norm_cdf(self, x):
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def _norm_pdf(self, x):
        return (
            math.exp(-0.5 * x * x)
            / math.sqrt(2.0 * math.pi)
        )

    def _time_years(self, days_to_expiry):
        return max(float(days_to_expiry) / 365.0, 1.0 / 365.0)

    def _d1_d2(
        self,
        spot,
        strike,
        volatility,
        days_to_expiry,
    ):
        spot = float(spot)
        strike = float(strike)
        volatility = max(float(volatility), 0.0001)
        t = self._time_years(days_to_expiry)

        d1 = (
            math.log(spot / strike)
            + (
                self.risk_free_rate
                + 0.5 * volatility * volatility
            ) * t
        ) / (volatility * math.sqrt(t))

        d2 = d1 - volatility * math.sqrt(t)

        return d1, d2, t

    def call_price(
        self,
        spot,
        strike,
        volatility,
        days_to_expiry,
    ):
        d1, d2, t = self._d1_d2(
            spot,
            strike,
            volatility,
            days_to_expiry,
        )

        return (
            float(spot) * self._norm_cdf(d1)
            - float(strike)
            * math.exp(-self.risk_free_rate * t)
            * self._norm_cdf(d2)
        )

    def put_price(
        self,
        spot,
        strike,
        volatility,
        days_to_expiry,
    ):
        d1, d2, t = self._d1_d2(
            spot,
            strike,
            volatility,
            days_to_expiry,
        )

        return (
            float(strike)
            * math.exp(-self.risk_free_rate * t)
            * self._norm_cdf(-d2)
            - float(spot) * self._norm_cdf(-d1)
        )

    def price(
        self,
        option_type,
        spot,
        strike,
        volatility,
        days_to_expiry,
    ):
        option_type = str(option_type).upper()

        if option_type == "CALL":
            return self.call_price(
                spot,
                strike,
                volatility,
                days_to_expiry,
            )

        if option_type == "PUT":
            return self.put_price(
                spot,
                strike,
                volatility,
                days_to_expiry,
            )

        raise ValueError(f"Unsupported option type: {option_type}")

    def delta(
        self,
        option_type,
        spot,
        strike,
        volatility,
        days_to_expiry,
    ):
        d1, _, _ = self._d1_d2(
            spot,
            strike,
            volatility,
            days_to_expiry,
        )

        option_type = str(option_type).upper()

        if option_type == "CALL":
            return self._norm_cdf(d1)

        if option_type == "PUT":
            return self._norm_cdf(d1) - 1.0

        raise ValueError(f"Unsupported option type: {option_type}")

    def gamma(
        self,
        spot,
        strike,
        volatility,
        days_to_expiry,
    ):
        d1, _, t = self._d1_d2(
            spot,
            strike,
            volatility,
            days_to_expiry,
        )

        return (
            self._norm_pdf(d1)
            / (
                float(spot)
                * max(float(volatility), 0.0001)
                * math.sqrt(t)
            )
        )

    def vega(
        self,
        spot,
        strike,
        volatility,
        days_to_expiry,
    ):
        d1, _, t = self._d1_d2(
            spot,
            strike,
            volatility,
            days_to_expiry,
        )

        return (
            float(spot)
            * self._norm_pdf(d1)
            * math.sqrt(t)
            / 100.0
        )

    def theta(
        self,
        option_type,
        spot,
        strike,
        volatility,
        days_to_expiry,
    ):
        d1, d2, t = self._d1_d2(
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
            / (2.0 * math.sqrt(t))
        )

        option_type = str(option_type).upper()

        if option_type == "CALL":
            second = (
                -self.risk_free_rate
                * strike
                * math.exp(-self.risk_free_rate * t)
                * self._norm_cdf(d2)
            )
        elif option_type == "PUT":
            second = (
                self.risk_free_rate
                * strike
                * math.exp(-self.risk_free_rate * t)
                * self._norm_cdf(-d2)
            )
        else:
            raise ValueError(f"Unsupported option type: {option_type}")

        return (first + second) / 365.0

    def rho(
        self,
        option_type,
        spot,
        strike,
        volatility,
        days_to_expiry,
    ):
        _, d2, t = self._d1_d2(
            spot,
            strike,
            volatility,
            days_to_expiry,
        )

        strike = float(strike)
        option_type = str(option_type).upper()

        if option_type == "CALL":
            return (
                strike
                * t
                * math.exp(-self.risk_free_rate * t)
                * self._norm_cdf(d2)
                / 100.0
            )

        if option_type == "PUT":
            return (
                -strike
                * t
                * math.exp(-self.risk_free_rate * t)
                * self._norm_cdf(-d2)
                / 100.0
            )

        raise ValueError(f"Unsupported option type: {option_type}")
