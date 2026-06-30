class RiskEngine:

    def validate_trade(self, pop, liquidity_score):

        if pop < 0.55:
            return False

        if liquidity_score < 50:
            return False

        return True
