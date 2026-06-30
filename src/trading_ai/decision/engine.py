from trading_ai.decision.signal_engine import SignalEngine
from trading_ai.decision.strategy_engine import StrategyEngine
from trading_ai.models.trade_recommendation import TradeRecommendation
from trading_ai.options.expiry_selector import ExpirySelector
from trading_ai.options.strike_selector import StrikeSelector


class DecisionEngine:

    def __init__(self):

        self.signal_engine = SignalEngine()
        self.strategy_engine = StrategyEngine()
        self.strike_selector = StrikeSelector()
        self.expiry_selector = ExpirySelector()

    def decide(self, symbol: str, row):

        signal = self.signal_engine.generate(row)

        score = row["call_score"] if signal == "CALL" else row["put_score"]

        if signal == "CALL":

            strike = self.strike_selector.select_call_strike(
                row["close"],
                row["expected_move_1d"],
                score,
            )

        else:

            strike = self.strike_selector.select_put_strike(
                row["close"],
                row["expected_move_1d"],
                score,
            )

        return TradeRecommendation(
            symbol=symbol,
            signal=signal,
            strategy=self.strategy_engine.choose(row),
            strike=strike["strike"],
            expiry=self.expiry_selector.choose(row),
            delta=strike["delta"],
            score=score,
            expected_move=row["expected_move_1d"],
            regime=row["market_regime"],
            price=row["close"],
            confidence=score / 100.0,
        )
