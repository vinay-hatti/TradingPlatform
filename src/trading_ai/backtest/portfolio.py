class BacktestPortfolio:

    def __init__(
        self,
        initial_capital=100000.0,
        max_open_positions=5,
        max_position_pct=0.05,
    ):
        self.initial_capital = float(initial_capital)
        self.cash = float(initial_capital)
        self.max_open_positions = int(max_open_positions)
        self.max_position_pct = float(max_position_pct)

        self.open_trades = []
        self.closed_trades = []
        self.rejected = []

    def position_value(self, trade):
        return float(trade.entry_price) * int(trade.contracts) * 100.0

    def can_enter(self, trade):

        value = self.position_value(trade)

        if len(self.open_trades) >= self.max_open_positions:
            return False, "MAX_OPEN_POSITIONS"

        if value > self.cash:
            return False, "INSUFFICIENT_CASH"

        max_position_value = self.initial_capital * self.max_position_pct

        if value > max_position_value:
            return False, "POSITION_TOO_LARGE"

        return True, "OK"

    def enter(self, trade):

        allowed, reason = self.can_enter(trade)

        if not allowed:
            self.rejected.append({
                "trade": trade,
                "reason": reason,
            })
            return False, reason

        value = self.position_value(trade)

        self.cash -= value
        self.open_trades.append(trade)

        return True, "OK"

    def close(self, trade):

        if trade in self.open_trades:
            self.open_trades.remove(trade)

        exit_value = float(trade.exit_price) * int(trade.contracts) * 100.0

        self.cash += exit_value
        self.closed_trades.append(trade)

    def process_trades(self, trades):

        for trade in sorted(trades, key=lambda t: t.entry_date):

            allowed, reason = self.enter(trade)

            if not allowed:
                continue

            self.close(trade)

        return {
            "closed_trades": self.closed_trades,
            "rejected": self.rejected,
            "cash": self.cash,
        }
