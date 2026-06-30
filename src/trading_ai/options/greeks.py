import math
from scipy.stats import norm


class Greeks:

    def d1(self, S, K, T, r, sigma):
        return (math.log(S / K) + (r + sigma**2 / 2) * T) / (sigma * math.sqrt(T))

    def d2(self, S, K, T, r, sigma):
        return self.d1(S, K, T, r, sigma) - sigma * math.sqrt(T)

    def delta_call(self, S, K, T, r, sigma):
        return norm.cdf(self.d1(S, K, T, r, sigma))

    def delta_put(self, S, K, T, r, sigma):
        return -norm.cdf(-self.d1(S, K, T, r, sigma))

    def gamma(self, S, K, T, r, sigma):
        d1 = self.d1(S, K, T, r, sigma)
        return norm.pdf(d1) / (S * sigma * math.sqrt(T))
