from trading_ai.domain.recommendation import TradeRecommendation


class StrategyEngine:

    def __init__(self, options_engine):
        self.options_engine = options_engine

    def recommend(self, symbol, ctx, analytics):

        score = self._score(ctx, analytics)

        if score >= 60:
            signal = "CALL"
            strategy = "LONG_CALL"
        else:
            signal = "PUT"
            strategy = "LONG_PUT"

        option = self.options_engine.select_contract(
            symbol,
            ctx,
            analytics,
            strategy=strategy,
        )

        if option is None:
            return None

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

    def _score(self, ctx, analytics):

        score = 50.0

        if ctx.market_regime == "BULL_TREND":
            score += 15
        elif ctx.market_regime == "BEAR_TREND":
            score -= 15

        if ctx.rsi14 > 55:
            score += 10
        elif ctx.rsi14 < 40:
            score -= 10

        iv_rank = analytics.get("iv_rank", 0.5)

        if iv_rank > 0.7:
            score += 10
        elif iv_rank < 0.3:
            score -= 5

        if ctx.em_ratio > 0.05:
            score += 5

        return float(max(0, min(100, score)))
