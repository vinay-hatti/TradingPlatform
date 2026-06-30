import numpy as np
from trading_ai.scanner.signals import Signal


class SignalEngine:

    def build_context(self, row):
        return row

    def __init__(self):

        self.call_threshold = 20
        self.put_threshold = 15

    def generate_signal(self, df):

        latest = df.iloc[-1]

        if latest["ema20"] > latest["ema50"]:
            return "CALL"
        return "PUT"

        call_score = latest.get("call_score", 0)
        put_score = latest.get("put_score", 0)

        regime = latest.get("market_regime", "UNKNOWN")
        expected_move = latest.get("expected_move_1d", 0)

        if call_score >= self.call_threshold and call_score > put_score:
            action = "CALL"
            score = call_score

        elif put_score >= self.put_threshold and put_score > call_score:
            action = "PUT"
            score = put_score

        else:
            action = "NO_TRADE"
            score = max(call_score, put_score)

        return Signal(
            symbol=str(df.index[-1]) if hasattr(df.index[-1], "__str__") else "UNKNOWN",
            action=action,
            score=score,
            confidence=min(score / 50, 1.0),
            regime=regime,
            expected_move=expected_move,
        )
