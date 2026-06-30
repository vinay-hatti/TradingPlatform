from trading_ai.portfolio.risk_manager import RiskManager
from trading_ai.portfolio.allocator import PositionAllocator
from trading_ai.portfolio.exposure import ExposureTracker


class PortfolioEngine:

    def __init__(self, account_value=100000):

        self.account_value = account_value

        self.risk_manager = RiskManager()
        self.allocator = PositionAllocator()
        self.exposure = ExposureTracker()

        self.portfolio = []

    def add_trade(self, trade):

        if not self.risk_manager.allow_trade(self.portfolio):
            return None

        size = self.allocator.size_position(
            self.account_value, trade["score"], trade["pop"]
        )

        position = {
            "symbol": trade["symbol"],
            "strategy": trade["strategy"],
            "strike": trade["strike"],
            "expiry": trade["expiry"],
            "size": size,
            "risk": size * 0.02,
            "pop": trade["pop"],
        }

        self.portfolio.append(position)

        return position

    def summary(self):

        return {
            "positions": len(self.portfolio),
            "total_risk": sum(p["risk"] for p in self.portfolio),
            "exposure": self.exposure.sector_exposure(self.portfolio),
        }
