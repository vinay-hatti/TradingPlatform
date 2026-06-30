import math


class ExpectedMove:

    def calc(self, price: float, iv: float, days: int) -> float:
        """
        Expected Move = Price × IV × sqrt(T)
        """
        return price * iv * math.sqrt(days / 365)
