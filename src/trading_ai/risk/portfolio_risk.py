from dataclasses import dataclass, field


@dataclass
class RiskResult:
    allowed: bool
    reason: str
    metrics: dict = field(default_factory=dict)


class PortfolioRiskManager:

    def __init__(
        self,
        capital: float = 100000.0,
        max_portfolio_heat: float = 0.25,
        max_symbol_exposure: float = 0.10,
        max_sector_exposure: float = 0.30,
        max_strategy_exposure: float = 0.70,
        min_cash_reserve: float = 0.20,
        max_net_delta: float = 0.60,
    ):
        self.capital = capital
        self.max_portfolio_heat = max_portfolio_heat
        self.max_symbol_exposure = max_symbol_exposure
        self.max_sector_exposure = max_sector_exposure
        self.max_strategy_exposure = max_strategy_exposure
        self.min_cash_reserve = min_cash_reserve
        self.max_net_delta = max_net_delta

    def _position_value(self, p):
        return (
            float(p.get("current_price", p.get("option_price_estimate", 0.0)))
            * int(p.get("quantity", p.get("recommended_contracts", 0)))
            * 100.0
        )

    def _candidate_value(self, trade):
        return (
            float(trade.get("option_price_estimate", 0.0))
            * int(trade.get("recommended_contracts", 0))
            * 100.0
        )

    def _net_delta(self, positions, candidate):

        total_delta = 0.0

        for p in positions:
            signal = str(p.get("signal", "")).upper()
            qty = int(p.get("quantity", p.get("recommended_contracts", 0)))
            delta = float(p.get("delta", 0.45))

            if signal == "PUT":
                delta = -abs(delta)
            else:
                delta = abs(delta)

            total_delta += delta * qty

        signal = str(candidate.get("signal", "")).upper()
        qty = int(candidate.get("recommended_contracts", 0))
        delta = float(candidate.get("delta", 0.45))

        if signal == "PUT":
            delta = -abs(delta)
        else:
            delta = abs(delta)

        total_delta += delta * qty

        return total_delta

    def evaluate(
        self,
        current_positions,
        candidate_trade,
        sector="UNKNOWN",
        cash=None,
    ):
        cash = self.capital if cash is None else float(cash)

        candidate_value = self._candidate_value(candidate_trade)

        if candidate_value <= 0:
            return RiskResult(False, "NO_TRADE_VALUE")

        projected_positions = list(current_positions)

        total_current_value = sum(
            self._position_value(p)
            for p in current_positions
        )

        projected_value = total_current_value + candidate_value
        portfolio_heat = projected_value / self.capital

        projected_cash = cash - candidate_value
        cash_reserve = projected_cash / self.capital

        symbol = candidate_trade.get("symbol")
        strategy = candidate_trade.get("strategy")

        symbol_value = candidate_value
        sector_value = candidate_value
        strategy_value = candidate_value

        for p in current_positions:
            value = self._position_value(p)

            if p.get("symbol") == symbol:
                symbol_value += value

            if p.get("sector", "UNKNOWN") == sector:
                sector_value += value

            if p.get("strategy") == strategy:
                strategy_value += value

        symbol_exposure = symbol_value / self.capital
        sector_exposure = sector_value / self.capital
        strategy_exposure = strategy_value / self.capital

        net_delta = self._net_delta(current_positions, candidate_trade)

        metrics = {
            "candidate_value": candidate_value,
            "projected_value": projected_value,
            "portfolio_heat": portfolio_heat,
            "cash_reserve": cash_reserve,
            "symbol_exposure": symbol_exposure,
            "sector_exposure": sector_exposure,
            "strategy_exposure": strategy_exposure,
            "net_delta": net_delta,
        }

        if portfolio_heat > self.max_portfolio_heat:
            return RiskResult(False, "PORTFOLIO_HEAT", metrics)

        if symbol_exposure > self.max_symbol_exposure:
            return RiskResult(False, "SYMBOL_EXPOSURE", metrics)

        if sector_exposure > self.max_sector_exposure:
            return RiskResult(False, "SECTOR_EXPOSURE", metrics)

        if strategy_exposure > self.max_strategy_exposure:
            return RiskResult(False, "STRATEGY_EXPOSURE", metrics)

        if cash_reserve < self.min_cash_reserve:
            return RiskResult(False, "CASH_RESERVE", metrics)

        if abs(net_delta) > self.max_net_delta:
            return RiskResult(False, "NET_DELTA", metrics)

        return RiskResult(True, "OK", metrics)
