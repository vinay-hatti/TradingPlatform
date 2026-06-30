class SpreadBuilder:

    def build_debit_spread(self, calls):
        """
        Choose 2 strikes:
        - buy ITM/ATM
        - sell OTM
        """

        if len(calls) < 2:
            return None

        buy = calls.iloc[0]
        sell = calls.iloc[1]

        return {
            "buy_strike": float(buy["strike"]),
            "sell_strike": float(sell["strike"]),
            "type": "CALL_DEBIT_SPREAD",
        }
