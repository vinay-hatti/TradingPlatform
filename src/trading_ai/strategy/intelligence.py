class StrategyIntelligence:

    def __init__(self):
        pass

    def select_strategy(self, ctx, iv_rank, skew, em_ratio):

        regime = ctx.market_regime

        # High IV regime → sell premium bias
        if iv_rank > 0.75:
            return "SHORT_VOL"

        # Low IV → breakout / directional
        if iv_rank < 0.3:
            return "LONG_VOL_BREAKOUT"

        # Strong skew → directional calls/puts
        if abs(skew) > 0.15:
            return "SKEW_DIRECTIONAL"

        # High expected move → momentum
        if em_ratio > 0.03:
            return "MOMENTUM"

        # Default regime-based
        if regime == "BULL_TREND":
            return "CALL_BIAS"

        if regime == "BEAR_TREND":
            return "PUT_BIAS"

        return "NEUTRAL"
