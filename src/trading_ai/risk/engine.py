class RiskEngine:

    def __init__(self, max_portfolio_risk=0.2):
        self.max_portfolio_risk = max_portfolio_risk

    def allow_trade(self, portfolio, new_trade):

        exposure = sum(p["size"] for p in portfolio)

        if exposure > self.max_portfolio_risk:
            return False

        if new_trade["score"] < 50:
            return False

        return True
