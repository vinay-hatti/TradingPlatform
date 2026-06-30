from scipy.stats import norm
import math


class ProbabilityModel:

    def pop_call(self, S, K, T, iv):

        if iv == 0:
            return 0

        d2 = (math.log(S / K) - (iv**2 / 2) * T) / (iv * math.sqrt(T))

        return norm.cdf(d2)

    def pop_put(self, S, K, T, iv):

        if iv == 0:
            return 0

        d2 = (math.log(S / K) - (iv**2 / 2) * T) / (iv * math.sqrt(T))

        return norm.cdf(-d2)
