from trading_ai.domain.recommendation import TradeRecommendation


class StrategyEngine:

    def __init__(self, options_engine):
        self.options_engine = options_engine

    def recommend(self, symbol, ctx, analytics):

        # Stronger pre-Phase-8 logic:
        # choose direction by score, not regime.
        if ctx.call_score >= ctx.put_score:
            strategy = "LONG_CALL"
            signal = "CALL"
        else:
            strategy = "LONG_PUT"
            signal = "PUT"

        option = self.options_engine.select_contract(
            symbol,
            ctx,
            analytics,
            strategy=strategy,
        )

        if option is None:
            return None

        score = self._score(ctx, option, analytics, strategy)

        return TradeRecommendation(
            symbol=symbol,
            signal=signal,
            strategy=strategy,
            strike=option.strike,
            expiry=option.expiry,
            score=score,
            confidence=min(0.9, score / 100),
            expected_move=ctx.expected_move_1d,
            regime=ctx.market_regime,
            price=ctx.close,
            delta=option.delta,
            option=option,
        )

    def _score(self, ctx, option, analytics, strategy):

        if strategy == "LONG_CALL":
            return float(ctx.call_score)

        if strategy == "LONG_PUT":
            return float(ctx.put_score)

        return 0.0

