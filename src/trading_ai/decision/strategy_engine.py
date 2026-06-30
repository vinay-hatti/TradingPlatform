class StrategyEngine:

    def choose(self, row):

        regime = row["market_regime"]

        atr = row["atr14"]

        if regime == "TREND":

            if atr > row["atr14_mean"]:
                return "LONG_CALL"

            return "BULL_CALL_SPREAD"

        if atr > row["atr14_mean"]:

            return "LONG_STRADDLE"

        return "IRON_CONDOR"
