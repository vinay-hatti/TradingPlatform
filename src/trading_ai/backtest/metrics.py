import math


class BacktestMetrics:

    def calculate(self, trades, initial_capital=100000.0):

        if not trades:
            return {
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
                "average_win": 0.0,
                "average_loss": 0.0,
                "largest_win": 0.0,
                "largest_loss": 0.0,
                "average_hold_days": 0.0,
                "net_pnl": 0.0,
                "return_pct": 0.0,
            }

        pnls = [float(t.pnl) for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))

        net_pnl = sum(pnls)

        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else float("inf")
        )

        average_win = sum(wins) / len(wins) if wins else 0.0
        average_loss = sum(losses) / len(losses) if losses else 0.0

        expectancy = net_pnl / len(trades)

        hold_days = [int(t.days_held) for t in trades]

        return {
            "trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(trades),
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "profit_factor": profit_factor,
            "expectancy": expectancy,
            "average_win": average_win,
            "average_loss": average_loss,
            "largest_win": max(pnls),
            "largest_loss": min(pnls),
            "average_hold_days": sum(hold_days) / len(hold_days),
            "net_pnl": net_pnl,
            "return_pct": net_pnl / initial_capital,
        }
