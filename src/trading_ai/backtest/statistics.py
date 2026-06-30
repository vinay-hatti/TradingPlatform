import numpy as np


class BacktestStatistics:

    def summarize(self, portfolio):

        pnl = [
            p.pnl
            for p in portfolio.closed
        ]

        wins = [
            x
            for x in pnl
            if x > 0
        ]

        losses = [
            x
            for x in pnl
            if x <= 0
        ]

        return {

            "Trades":
                len(pnl),

            "WinRate":
                len(wins) / max(1, len(pnl)),

            "AverageWin":
                np.mean(wins) if wins else 0,

            "AverageLoss":
                np.mean(losses) if losses else 0,

            "NetProfit":
                np.sum(pnl),

            "MaxDrawdown":
                self.drawdown(
                    portfolio.equity_curve
                ),

        }

    def drawdown(self, curve):

        if len(curve) == 0:
            return 0

        peak = curve[0]

        dd = 0

        for x in curve:

            peak = max(peak, x)

            dd = max(
                dd,
                peak - x
            )

        return dd
