import math
from datetime import datetime


class OptionProbabilityScorer:

    def _norm_cdf(self, x):

        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def _days_to_expiry(self, option):

        expiry = getattr(option, "expiry", None)

        if expiry is None:
            return 30

        try:
            expiry_dt = datetime.strptime(str(expiry), "%Y-%m-%d")
            today = datetime.now()
            return max((expiry_dt - today).days, 1)
        except Exception:
            return 30

    def probability_itm(self, option, spot=None):

        delta = abs(float(getattr(option, "delta", 0.0) or 0.0))

        if delta > 0:
            return max(0.05, min(delta, 0.95))

        return 0.50

    def probability_otm(self, option, spot=None):

        return 1.0 - self.probability_itm(option, spot)

    def probability_of_profit(self, option, signal, spot=None):

        strike = float(getattr(option, "strike", 0.0) or 0.0)
        iv = float(getattr(option, "implied_volatility", 0.0) or 0.0)

        if spot is None:
            spot = float(getattr(option, "underlying_price", 0.0) or 0.0)

        if spot <= 0 or strike <= 0 or iv <= 0:
            delta = abs(float(getattr(option, "delta", 0.0) or 0.0))
            return max(0.35, min(1.0 - abs(delta - 0.45), 0.85))

        dte = self._days_to_expiry(option)
        t = max(dte / 365.0, 1 / 365.0)

        sigma_t = iv * math.sqrt(t)

        if sigma_t <= 0:
            return 0.50

        z = math.log(spot / strike) / sigma_t

        if signal == "CALL":
            pop = self._norm_cdf(z)
        else:
            pop = self._norm_cdf(-z)

        return max(0.05, min(pop, 0.95))
