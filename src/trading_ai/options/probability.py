class OptionProbabilityScorer:

    def probability_itm(self, option):

        delta = abs(float(getattr(option, "delta", 0.0) or 0.0))

        return max(0.05, min(delta, 0.95))

    def probability_otm(self, option):

        return 1.0 - self.probability_itm(option)

    def probability_of_profit(self, option, signal):

        delta = abs(float(getattr(option, "delta", 0.0) or 0.0))

        base = 1.0 - abs(delta - 0.45)

        if signal == "CALL" and delta > 0.30:
            base += 0.05

        if signal == "PUT" and delta > 0.30:
            base += 0.05

        return max(0.35, min(base, 0.85))
