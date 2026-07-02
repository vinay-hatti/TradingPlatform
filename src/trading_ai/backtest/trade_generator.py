class HistoricalTradeGenerator:

    def __init__(
        self,
        datasource,
        simulator,
        contracts=1,
        max_hold_days=10,
    ):
        self.datasource = datasource
        self.simulator = simulator
        self.contracts = contracts
        self.max_hold_days = max_hold_days

    def generate(
        self,
        signals,
        price_history,
    ):
        trades = []

        for signal in signals:

            entry_date = signal["date"]
            entry_price = float(signal["close"])

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
                contracts=self.contracts,
                rank_score=float(signal.get("score", 0.0)),
                option_score=float(signal.get("score", 0.0)),
                pop=0.0,
                liquidity=0.0,
                atm_score=100.0,
            )

            trades.append(trade)

        return trades
