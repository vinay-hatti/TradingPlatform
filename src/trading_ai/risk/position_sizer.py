from math import floor


class PositionSizer:

    def __init__(
        self,
        risk_per_trade_pct=0.01,
        max_position_pct=0.10,
        min_contracts=1,
    ):
        self.risk_per_trade_pct = float(risk_per_trade_pct)
        self.max_position_pct = float(max_position_pct)
        self.min_contracts = int(min_contracts)

    def contracts(
        self,
        capital,
        option_price,
    ):
        capital = float(capital)
        option_price = float(option_price)

        contract_cost = option_price * 100.0

        if capital <= 0 or contract_cost <= 0:
            return 0

        risk_budget = capital * self.risk_per_trade_pct

        risk_contracts = floor(risk_budget / contract_cost)

        max_contracts = floor(
            capital * self.max_position_pct / contract_cost
        )

        contracts = min(
            risk_contracts,
            max_contracts,
        )

        if contracts <= 0:
            return 0

        return max(
            self.min_contracts,
            contracts,
        )
