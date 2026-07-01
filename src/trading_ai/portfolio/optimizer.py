from dataclasses import dataclass


@dataclass
class OptimizedTrade:
    symbol: str
    signal: str
    strategy: str
    confidence: str
    rank_score: float
    win_probability: float
    reward_risk: float
    kelly_fraction: float
    option_price_estimate: float
    contract_cost: float
    requested_allocation: float
    final_allocation: float
    recommended_contracts: int
    status: str
    reason: str
    strike: float
    expiry: str
    iv: float

class PortfolioOptimizer:

    def __init__(
        self,
        capital: float = 100000.0,
        max_position_pct: float = 0.05,
        max_total_allocation_pct: float = 0.20,
        cash_reserve_pct: float = 0.15,
    ):
        self.capital = capital
        self.max_position_pct = max_position_pct
        self.max_total_allocation_pct = max_total_allocation_pct
        self.cash_reserve_pct = cash_reserve_pct

    def _weight(self, row):

        rank = float(row.get("rank_score", 0.0))
        win_prob = float(row.get("win_probability", 0.0))
        reward_risk = float(row.get("reward_risk", 0.0))
        kelly = float(row.get("kelly_fraction", 0.0))

        return max(rank * win_prob * reward_risk * max(kelly, 0.01), 0.0)

    def optimize(self, rows):

        if not rows:
            return []

        tradable_rows = [
            r for r in rows
            if str(r.get("affordability_status", "OK")) == "OK"
            and int(float(r.get("recommended_contracts", 0))) > 0
        ]

        if not tradable_rows:
            return []

        weights = [self._weight(r) for r in tradable_rows]
        total_weight = sum(weights)

        if total_weight <= 0:
            return []

        total_allocation_budget = self.capital * self.max_total_allocation_pct
        max_position_value = self.capital * self.max_position_pct

        max_spendable = self.capital * (1.0 - self.cash_reserve_pct)
        total_allocation_budget = min(total_allocation_budget, max_spendable)

        optimized = []

        used_capital = 0.0

        for row, weight in zip(tradable_rows, weights):

            symbol = row["symbol"]
            signal = row["signal"]
            strategy = row["strategy"]

            option_price = float(row.get("option_price_estimate", 0.0))
            contract_cost = float(row.get("estimated_contract_cost", option_price * 100.0))

            requested_allocation = total_allocation_budget * (weight / total_weight)
            final_allocation = min(requested_allocation, max_position_value)

            remaining_budget = max(total_allocation_budget - used_capital, 0.0)
            final_allocation = min(final_allocation, remaining_budget)

            if contract_cost <= 0:
                contracts = 0
                status = "REJECTED"
                reason = "INVALID_CONTRACT_COST"
            else:
                contracts = int(final_allocation / contract_cost)

                if contracts <= 0:
                    contracts = 0
                    status = "REJECTED"
                    reason = "ALLOCATION_TOO_SMALL"
                else:
                    status = "ACCEPTED"
                    reason = "OK"

            actual_allocation = contracts * contract_cost

            if status == "ACCEPTED":
                used_capital += actual_allocation

            optimized.append(
                OptimizedTrade(
                    symbol=symbol,
                    signal=signal,
                    strategy=strategy,
                    confidence=str(row.get("confidence", "")),
                    rank_score=float(row.get("rank_score", 0.0)),
                    win_probability=float(row.get("win_probability", 0.0)),
                    reward_risk=float(row.get("reward_risk", 0.0)),
                    kelly_fraction=float(row.get("kelly_fraction", 0.0)),
                    option_price_estimate=option_price,
                    contract_cost=contract_cost,
                    requested_allocation=requested_allocation,
                    final_allocation=actual_allocation,
                    recommended_contracts=contracts,
                    status=status,
                    reason=reason,
                    strike=float(row.get("strike", 0.0) or 0.0),
                    expiry=str(row.get("expiry", "")),
                    iv=float(row.get("iv", 0.25) or 0.25),
                )
            )

        return optimized
