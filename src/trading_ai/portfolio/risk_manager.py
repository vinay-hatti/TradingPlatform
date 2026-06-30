class RiskManager:

    def __init__(self):

        self.max_risk_per_trade = 0.02  # 2%
        self.max_total_risk = 0.10  # 10%
        self.max_positions = 8

    def allow_trade(self, portfolio):

        if len(portfolio) >= self.max_positions:
            return False

        total_risk = sum([p["risk"] for p in portfolio])

        if total_risk >= self.max_total_risk:
            return False

        return True
