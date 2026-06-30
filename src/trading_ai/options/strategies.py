class StrategySelector:

    def choose(self, score: float, iv_rank: float):

        # Simple regime logic (we will improve later)

        if score > 80 and iv_rank < 50:
            return "LONG_CALL"

        if score > 80 and iv_rank >= 50:
            return "CALL_DEBIT_SPREAD"

        if score < 50:
            return "NO_TRADE"

        return "LONG_CALL"
