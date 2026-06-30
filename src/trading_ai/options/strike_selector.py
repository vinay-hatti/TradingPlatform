import numpy as np


class StrikeSelector:

    def __init__(self, strike_step: int = 5):
        self.strike_step = strike_step

    def round_to_strike(self, price: float) -> int:
        return int(round(price / self.strike_step) * self.strike_step)

    def select_call_strike(self, price: float, expected_move: float, strength: float):

        # base target move adjustment
        if strength > 70:
            target_price = price + expected_move * 0.8
        elif strength > 50:
            target_price = price + expected_move * 0.5
        else:
            target_price = price + expected_move * 0.3

        strike = self.round_to_strike(target_price)

        # approximate delta heuristic
        moneyness = (strike - price) / price

        if moneyness < 0:
            delta = 0.6
        elif moneyness < 0.02:
            delta = 0.5
        elif moneyness < 0.05:
            delta = 0.35
        else:
            delta = 0.2

        return {
            "strike": strike,
            "delta": round(delta, 2),
        }

    def select_put_strike(self, price: float, expected_move: float, strength: float):

        if strength > 70:
            target_price = price - expected_move * 0.8
        elif strength > 50:
            target_price = price - expected_move * 0.5
        else:
            target_price = price - expected_move * 0.3

        strike = self.round_to_strike(target_price)

        moneyness = (price - strike) / price

        if moneyness < 0:
            delta = 0.6
        elif moneyness < 0.02:
            delta = 0.5
        elif moneyness < 0.05:
            delta = 0.35
        else:
            delta = 0.2

        return {
            "strike": strike,
            "delta": round(delta, 2),
        }
