import numpy as np


class Metrics:

    @staticmethod
    def win_rate(trades):

        wins = [
            t
            for t in trades
            if t["pnl"] > 0
        ]

        return len(wins) / len(trades)

    @staticmethod
    def total_return(trades):

        return sum(
            t["pnl"]
            for t in trades
        )
