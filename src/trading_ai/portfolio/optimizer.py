from dataclasses import dataclass

from trading_ai.risk.portfolio_risk import PortfolioRiskManager


@dataclass
class OptimizedTrade:
    symbol: str
    signal: str
    strategy: str
    confidence: str
    strike: float
    expiry: str
    iv: float
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
    risk_metrics: dict
    option_score: float
    probability_of_profit: float
    liquidity_score: float
    delta_score: float
    iv_score: float

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

        self.risk = PortfolioRiskManager(
            capital=capital,
            max_portfolio_heat=max_total_allocation_pct,
            max_symbol_exposure=max_position_pct,
            max_sector_exposure=0.30,
            max_strategy_exposure=0.70,
            min_cash_reserve=cash_reserve_pct,
            max_net_delta=2.0,
        )

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
        accepted_positions = []
        used_capital = 0.0
        cash = self.capital

        for row, weight in zip(tradable_rows, weights):

            symbol = row["symbol"]
            signal = row["signal"]
            strategy = row["strategy"]

            option_price = float(row.get("option_price_estimate", 0.0))
            contract_cost = float(
                row.get("estimated_contract_cost", option_price * 100.0)
            )

            requested_allocation = total_allocation_budget * (weight / total_weight)
            final_allocation = min(requested_allocation, max_position_value)

            remaining_budget = max(total_allocation_budget - used_capital, 0.0)
            final_allocation = min(final_allocation, remaining_budget)

            if contract_cost <= 0:
                contracts = 0
                status = "REJECTED"
                reason = "INVALID_CONTRACT_COST"
                actual_allocation = 0.0
                risk_metrics = {}
            else:
                contracts = int(final_allocation / contract_cost)

                if contracts <= 0:
                    contracts = 0
                    status = "REJECTED"
                    reason = "ALLOCATION_TOO_SMALL"
                    actual_allocation = 0.0
                    risk_metrics = {}
                else:
                    candidate_trade = {
                        "symbol": symbol,
                        "signal": signal,
                        "strategy": strategy,
                        "option_price_estimate": option_price,
                        "recommended_contracts": contracts,
                        "delta": float(row.get("delta", 0.45)),
                    }

                    risk_result = self.risk.evaluate(
                        current_positions=accepted_positions,
                        candidate_trade=candidate_trade,
                        sector=row.get("sector", "UNKNOWN"),
                        cash=cash,
                    )

                    risk_metrics = risk_result.metrics

                    if not risk_result.allowed:
                        contracts = 0
                        status = "REJECTED"
                        reason = risk_result.reason
                        actual_allocation = 0.0
                    else:
                        status = "ACCEPTED"
                        reason = "OK"
                        actual_allocation = contracts * contract_cost

                        used_capital += actual_allocation
                        cash -= actual_allocation

                        accepted_positions.append({
                            "symbol": symbol,
                            "signal": signal,
                            "strategy": strategy,
                            "current_price": option_price,
                            "quantity": contracts,
                            "delta": float(row.get("delta", 0.45)),
                            "sector": row.get("sector", "UNKNOWN"),
                        })

            optimized.append(
                OptimizedTrade(
                    symbol=symbol,
                    signal=signal,
                    strategy=strategy,
                    confidence=str(row.get("confidence", "")),
                    strike=float(row.get("strike", 0.0) or 0.0),
                    expiry=str(row.get("expiry", "")),
                    iv=float(row.get("iv", 0.25) or 0.25),
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
                    risk_metrics=risk_metrics,
                    option_score=float(row.get("option_score", 0.0) or 0.0),
                    probability_of_profit=float(row.get("probability_of_profit", 0.0) or 0.0),
                    liquidity_score=float(row.get("liquidity_score", 0.0) or 0.0),
                    delta_score=float(row.get("delta_score", 0.0) or 0.0),
                    iv_score=float(row.get("iv_score", 0.0) or 0.0),
                )
            )

        return optimized
