class HistoricalTradeGenerator:

    def __init__(
        self,
        datasource,
        simulator,
        contracts=1,
        max_hold_days=10,
        position_sizer=None,
        capital=100000.0,
    ):
        self.datasource = datasource
        self.simulator = simulator
        self.contracts = contracts
        self.max_hold_days = max_hold_days
        self.position_sizer = position_sizer
        self.capital = float(capital)

    def _contracts_for_trade(self, entry_price):

        if self.position_sizer is None:
            return int(self.contracts)

        return self.position_sizer.contracts(
            capital=self.capital,
            option_price=entry_price,
        )

    def generate(
        self,
        signals,
        price_history,
    ):
        trades = []

        for signal in signals:

            entry_date = signal["date"]
            entry_price = float(signal["close"])

            contracts = self._contracts_for_trade(entry_price)

            if contracts <= 0:
                continue

            future_prices = self.datasource.get_next_days(
                price_history,
                entry_date,
                days=self.max_hold_days,
            )

            if not future_prices:
                continue

            trade = self.simulator.simulate(
                symbol=signal["symbol"],
                signal=signal["signal"],
                strategy=(
                    "LONG_CALL"
                    if signal["signal"] == "CALL"
                    else "LONG_PUT"
                ),
                strike=entry_price,
                expiry="STOCK_PROXY",
                entry_date=entry_date,
                entry_price=entry_price,
                future_prices=future_prices,
                contracts=contracts,
                rank_score=float(signal.get("score", 0.0)),
                option_score=float(signal.get("score", 0.0)),
                pop=0.0,
                liquidity=0.0,
                atm_score=100.0,
            )

            trades.append(trade)

        return trades
