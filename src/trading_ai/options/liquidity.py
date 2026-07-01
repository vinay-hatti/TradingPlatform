class OptionLiquidityScorer:

    def score(self, option):

        open_interest = float(getattr(option, "open_interest", 0.0) or 0.0)
        volume = float(getattr(option, "volume", 0.0) or 0.0)

        oi_score = min(open_interest / 1000.0, 1.0)
        volume_score = min(volume / 500.0, 1.0)

        return (oi_score * 0.70 + volume_score * 0.30) * 100.0
