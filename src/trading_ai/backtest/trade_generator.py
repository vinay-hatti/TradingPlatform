class HistoricalTradeGenerator:

    def __init__(
        self,
        datasource,
        simulator,
        contracts=1,
        max_hold_days=10,
        position_sizer=None,
        capital=100000.0,
        option_premium_pct=0.08,
    ):
        self.datasource = datasource
        self.simulator = simulator
        self.contracts = contracts
        self.max_hold_days = max_hold_days
        self.position_sizer = position_sizer
        self.capital = float(capital)
        self.option_premium_pct = float(option_premium_pct)

    def _contracts_for_trade(self, entry_price):

        if self.position_sizer is None:
            return int(self.contracts)

        return self.position_sizer.contracts(
            capital=self.capital,
            option_price=entry_price,
        )

    def _option_proxy_price(self, underlying_price):

        return float(underlying_price) * self.option_premium_pct

    def generate(
        self,
        signals,
        price_history,
    ):
        trades = []

        for signal in signals:

            entry_date = signal["date"]
            underlying_price = float(signal["close"])
            entry_price = self._option_proxy_price(underlying_price)

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

            future_prices = [
                {
                    "date": p["date"],
                    "price": self._option_proxy_price(p["price"]),
                }
                for p in future_prices
            ]

            trade = self.simulator.simulate(
                symbol=signal["symbol"],
                signal=signal["signal"],
                strategy=(
                    "LONG_CALL"
                    if signal["signal"] == "CALL"
                    else "LONG_PUT"
                ),
                strike=underlying_price,
                expiry="OPTION_PROXY",
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
