import math


class ExpectedMoveEngine:
    def calculate(self, underlying_price: float, volatility: float, dte: int) -> float:
        underlying_price = float(underlying_price or 0.0)
        volatility = float(volatility or 0.0)
        dte = int(dte or 0)

        if underlying_price <= 0 or volatility <= 0 or dte <= 0:
            return 0.0

        return underlying_price * volatility * math.sqrt(dte / 365.0)
