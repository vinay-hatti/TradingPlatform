import math
from statistics import NormalDist


class BlackScholesPricer:

    def __init__(self):
        self.normal = NormalDist()

    def price(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        volatility: float,
        risk_free_rate: float = 0.045,
        option_type: str = "CALL",
    ) -> float:

        if spot <= 0 or strike <= 0:
            return 0.0

        if time_to_expiry <= 0:
            if option_type.upper() == "CALL":
                return max(spot - strike, 0.0)
            return max(strike - spot, 0.0)

        volatility = max(volatility, 0.0001)

        d1 = (
            math.log(spot / strike)
            + (risk_free_rate + 0.5 * volatility ** 2) * time_to_expiry
        ) / (volatility * math.sqrt(time_to_expiry))

        d2 = d1 - volatility * math.sqrt(time_to_expiry)

        if option_type.upper() == "CALL":
            return (
                spot * self.normal.cdf(d1)
                - strike * math.exp(-risk_free_rate * time_to_expiry) * self.normal.cdf(d2)
            )

        return (
            strike * math.exp(-risk_free_rate * time_to_expiry) * self.normal.cdf(-d2)
            - spot * self.normal.cdf(-d1)
        )
