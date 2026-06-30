class ExitEngine:

    def __init__(
        self,
        stop_loss_pct: float = -0.08,
        take_profit_pct: float = 0.15,
        max_holding_bars: int = 10,
    ):
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_holding_bars = max_holding_bars

    def check_exit(self, position, current_index: int, current_option_price: float):

        pnl = position.mark_pnl(current_option_price)

        risk_base = max(
            position.option_entry_price * position.size * 100,
            1,
        )

        pnl_pct = pnl / risk_base

        holding_bars = current_index - position.entry_index

        if pnl_pct <= self.stop_loss_pct:
            return True, "STOP_LOSS"

        if pnl_pct >= self.take_profit_pct:
            return True, "TAKE_PROFIT"

        if holding_bars >= self.max_holding_bars:
            return True, "MAX_HOLD"

        return False, ""
