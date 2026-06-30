class StrategySelector:

    def choose(self, ctx):

        regime = str(ctx.market_regime).upper()

        if regime == "BULL_TREND":
            return "LONG_CALL"

        if regime == "BEAR_TREND":
            return "LONG_PUT"

        if regime == "VOLATILE":
            if ctx.call_score >= ctx.put_score:
                return "LONG_CALL"
            return "LONG_PUT"

        return "NONE"
