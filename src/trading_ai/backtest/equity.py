class EquityCurveBuilder:

    def build(self, trades, initial_capital=100000.0):

        equity = float(initial_capital)
        curve = []

        sorted_trades = sorted(
            trades,
            key=lambda t: t.exit_date,
        )

        for trade in sorted_trades:
            equity += float(trade.pnl)

            curve.append({
                "date": trade.exit_date,
                "equity": equity,
                "pnl": trade.pnl,
                "symbol": trade.symbol,
                "exit_reason": trade.exit_reason,
            })

        return curve

    def max_drawdown(self, curve):

        if not curve:
            return 0.0

        peak = curve[0]["equity"]
        max_dd = 0.0

        for point in curve:
            equity = float(point["equity"])

            peak = max(peak, equity)

            drawdown = equity - peak

            max_dd = min(max_dd, drawdown)

        return max_dd
