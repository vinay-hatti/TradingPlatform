from trading_ai.options.liquidity import OptionLiquidityScorer
from trading_ai.options.probability import OptionProbabilityScorer


class OptionQualityScorer:

    def __init__(self):
        self.liquidity = OptionLiquidityScorer()
        self.probability = OptionProbabilityScorer()

    def score(self, option, signal, spot=None):

#        pop = self.probability.probability_of_profit(option, signal)
        pop = self.probability.probability_of_profit(
            option,
            signal,
            spot=spot,
        )

        liquidity = self.liquidity.score(option)

        delta = abs(float(getattr(option, "delta", 0.0) or 0.0))
        iv = float(getattr(option, "implied_volatility", 0.0) or 0.0)

        delta_score = max(0.0, 1.0 - abs(delta - 0.45)) * 100.0

        iv_score = 100.0
        if iv < 0.10:
            iv_score = 40.0
        elif iv > 1.00:
            iv_score = 50.0

        return {
            "option_score": (
                pop * 100.0 * 0.40
                + liquidity * 0.25
                + delta_score * 0.25
                + iv_score * 0.10
            ),
            "probability_of_profit": pop,
            "liquidity_score": liquidity,
            "delta_score": delta_score,
            "iv_score": iv_score,
        }
