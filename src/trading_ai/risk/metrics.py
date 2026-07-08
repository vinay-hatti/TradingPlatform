import math


class RiskMetricsEngine:

    def _safe_div(self, a, b):
        return a / b if b not in (0, 0.0) else 0.0

    def returns_from_equity(self, equity_curve):

        returns = []

        for idx in range(1, len(equity_curve)):
            prev = float(equity_curve[idx - 1]["equity"])
            curr = float(equity_curve[idx]["equity"])

            if prev > 0:
                returns.append((curr - prev) / prev)

        return returns

    def max_drawdown(self, equity_curve):

        peak = None
        max_dd = 0.0
        max_dd_dollars = 0.0

        for point in equity_curve:
            equity = float(point["equity"])

            if peak is None or equity > peak:
                peak = equity

            drawdown_dollars = equity - peak
            drawdown_pct = self._safe_div(drawdown_dollars, peak)

            if drawdown_pct < max_dd:
                max_dd = drawdown_pct
                max_dd_dollars = drawdown_dollars

        return {
            "max_drawdown_pct": max_dd,
            "max_drawdown_dollars": max_dd_dollars,
        }

    def sharpe_ratio(self, returns, periods_per_year=252):

        if not returns:
            return 0.0

        mean = sum(returns) / len(returns)

        variance = (
            sum((r - mean) ** 2 for r in returns)
            / len(returns)
        )

        std = math.sqrt(variance)

        if std == 0:
            return 0.0

        return (
            mean / std
            * math.sqrt(periods_per_year)
        )

    def sortino_ratio(self, returns, periods_per_year=252):

        if not returns:
            return 0.0

        mean = sum(returns) / len(returns)

        downside = [
            r for r in returns
            if r < 0
        ]

        if not downside:
            return 0.0

        downside_variance = (
            sum(r ** 2 for r in downside)
            / len(downside)
        )

        downside_std = math.sqrt(downside_variance)

        if downside_std == 0:
            return 0.0

        return (
            mean / downside_std
            * math.sqrt(periods_per_year)
        )

    def calmar_ratio(self, total_return, max_drawdown_pct):

        if max_drawdown_pct == 0:
            return 0.0

        return total_return / abs(max_drawdown_pct)

#    def profit_metrics(self, trades):
#        pnls = [
#            float(getattr(t, "net_pnl", getattr(t, "pnl", 0.0)))
#            value = getattr(t, "net_pnl", None)
#            if value in (None, 0.0):
#                value = getattr(t, "pnl", 0.0)
#            pnls.append(float(value))
#            for t in trades
#        ]

    def profit_metrics(self, trades):

        pnls = []

        for t in trades:
            value = getattr(t, "net_pnl", None)

            if value in (None, 0.0):
                value = getattr(t, "pnl", 0.0)

            pnls.append(float(value))


        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))

        avg_win = self._safe_div(gross_profit, len(wins))
        avg_loss = self._safe_div(gross_loss, len(losses))

        largest_win = max(wins) if wins else 0.0
        largest_loss = min(losses) if losses else 0.0

        return {
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "largest_win": largest_win,
            "largest_loss": largest_loss,
            "payoff_ratio": self._safe_div(avg_win, avg_loss),
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
        }

    def compute(
        self,
        equity_curve,
        trades,
        initial_capital,
    ):
        returns = self.returns_from_equity(equity_curve)
        dd = self.max_drawdown(equity_curve)

        final_equity = (
            float(equity_curve[-1]["equity"])
            if equity_curve
            else float(initial_capital)
        )

        total_return = self._safe_div(
            final_equity - float(initial_capital),
            float(initial_capital),
        )

        profit = self.profit_metrics(trades)

        return {
            "total_return": total_return,
            "max_drawdown_pct": dd["max_drawdown_pct"],
            "max_drawdown_dollars": dd["max_drawdown_dollars"],
            "sharpe_ratio": self.sharpe_ratio(returns),
            "sortino_ratio": self.sortino_ratio(returns),
            "calmar_ratio": self.calmar_ratio(
                total_return,
                dd["max_drawdown_pct"],
            ),
            "avg_win": profit["avg_win"],
            "avg_loss": profit["avg_loss"],
            "largest_win": profit["largest_win"],
            "largest_loss": profit["largest_loss"],
            "payoff_ratio": profit["payoff_ratio"],
            "gross_profit": profit["gross_profit"],
            "gross_loss": profit["gross_loss"],
        }
