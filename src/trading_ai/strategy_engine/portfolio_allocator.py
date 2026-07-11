import math

from trading_ai.strategy_engine.portfolio_position import (
    PortfolioPosition,
)
from trading_ai.strategy_engine.portfolio_risk_limits import (
    PortfolioRiskLimits,
)


class PortfolioAllocator:
    """
    Converts one ranked opportunity into a proposed portfolio position.

    Contract quantity is constrained by:

      - Maximum risk per trade
      - Maximum position size
      - Maximum contracts
      - Remaining portfolio exposure
      - Remaining portfolio risk
      - Ranking-score multiplier
    """

    def __init__(
        self,
        limits: PortfolioRiskLimits,
    ):
        self.limits = limits
        self.limits.validate()

    def allocate(
        self,
        ranked_opportunity,
        remaining_exposure_dollars: float,
        remaining_risk_dollars: float,
    ) -> PortfolioPosition | None:
        opportunity = ranked_opportunity.opportunity

        per_contract_capital = self._per_contract_capital(
            opportunity
        )

        per_contract_risk = self._per_contract_risk(
            opportunity
        )

        if per_contract_capital <= 0:
            return None

        if (
            per_contract_risk <= 0
            and not self.limits.allow_zero_maximum_loss
        ):
            return None

        max_by_position = int(
            self.limits.maximum_position_dollars
            // per_contract_capital
        )

        max_by_remaining_exposure = int(
            max(remaining_exposure_dollars, 0.0)
            // per_contract_capital
        )

        if per_contract_risk > 0:
            max_by_trade_risk = int(
                self.limits.maximum_risk_per_trade_dollars
                // per_contract_risk
            )

            max_by_remaining_risk = int(
                max(remaining_risk_dollars, 0.0)
                // per_contract_risk
            )
        else:
            max_by_trade_risk = (
                self.limits.maximum_contracts_per_position
            )

            max_by_remaining_risk = (
                self.limits.maximum_contracts_per_position
            )

        raw_contracts = min(
            max_by_position,
            max_by_remaining_exposure,
            max_by_trade_risk,
            max_by_remaining_risk,
            self.limits.maximum_contracts_per_position,
        )

        if raw_contracts <= 0:
            return None

        contracts = raw_contracts

        if self.limits.use_score_scaling:
            multiplier = self._score_multiplier(
                ranked_opportunity.ranking_score
            )

            contracts = max(
                int(math.floor(
                    raw_contracts * multiplier
                )),
                1,
            )

            contracts = min(
                contracts,
                raw_contracts,
            )

        total_capital = (
            per_contract_capital * contracts
        )

        total_risk = (
            per_contract_risk * contracts
        )

        if (
            total_capital
            < self.limits.minimum_position_dollars
        ):
            return None

        expected_profit_per_contract = self._per_contract_expected_profit(
            opportunity
        )

        expected_profit = (
            expected_profit_per_contract
            * contracts
        )

        expected_return_pct = (
            expected_profit / total_capital
            if total_capital > 0
            else 0.0
        )

        greeks = self._per_contract_greeks(
            opportunity
        )

        return PortfolioPosition(
            symbol=opportunity.symbol,
            strategy=opportunity.strategy,
            direction=opportunity.direction,
            contracts=contracts,
            capital_required=round(
                total_capital,
                2,
            ),
            maximum_loss=round(
                total_risk,
                2,
            ),
            expected_profit=round(
                expected_profit,
                2,
            ),
            expected_return_pct=round(
                expected_return_pct,
                4,
            ),
            allocation_pct=round(
                total_capital
                / self.limits.initial_capital,
                4,
            ),
            risk_pct=round(
                total_risk
                / self.limits.initial_capital,
                4,
            ),
            delta=round(
                greeks["delta"] * contracts,
                4,
            ),
            gamma=round(
                greeks["gamma"] * contracts,
                5,
            ),
            theta=round(
                greeks["theta"] * contracts,
                4,
            ),
            vega=round(
                greeks["vega"] * contracts,
                4,
            ),
            rho=round(
                greeks["rho"] * contracts,
                4,
            ),
            sector=opportunity.sector,
            industry=opportunity.industry,
            correlation_group=(
                opportunity.correlation_group
            ),
            ranking_score=(
                ranked_opportunity.ranking_score
            ),
            strategy_score=(
                opportunity.strategy_score
            ),
            portfolio_fit_score=(
                opportunity.portfolio_fit_score
            ),
            readiness=opportunity.readiness,
            action=ranked_opportunity.action,
            expiry=opportunity.expiry,
            dte=opportunity.dte,
            strike=opportunity.strike,
            long_strike=opportunity.long_strike,
            short_strike=opportunity.short_strike,
            option_symbol=opportunity.option_symbol,
            premium_type=opportunity.premium_type,
            risk_profile=opportunity.risk_profile,
            complexity=opportunity.complexity,
            source_opportunity=opportunity,
            source_ranked_opportunity=(
                ranked_opportunity
            ),
            warnings=list(
                ranked_opportunity.warnings
            ),
            metadata={
                "per_contract_capital": (
                    per_contract_capital
                ),
                "per_contract_risk": (
                    per_contract_risk
                ),
                "raw_contract_capacity": (
                    raw_contracts
                ),
            },
        )

    def _score_multiplier(
        self,
        ranking_score: float,
    ) -> float:
        score = max(
            0.0,
            min(100.0, float(ranking_score or 0.0)),
        )

        normalized = score / 100.0

        multiplier = (
            self.limits.minimum_score_multiplier
            + normalized
            * (
                self.limits.maximum_score_multiplier
                - self.limits.minimum_score_multiplier
            )
        )

        return max(
            self.limits.minimum_score_multiplier,
            min(
                self.limits.maximum_score_multiplier,
                multiplier,
            ),
        )

    def _per_contract_capital(
        self,
        opportunity,
    ) -> float:
        contracts = max(
            int(opportunity.contracts or 1),
            1,
        )

        capital = float(
            opportunity.capital_required or 0.0
        )

        if capital > 0:
            return capital / contracts

        maximum_loss = float(
            opportunity.maximum_loss or 0.0
        )

        if maximum_loss > 0:
            return maximum_loss / contracts

        return 0.0

    def _per_contract_risk(
        self,
        opportunity,
    ) -> float:
        contracts = max(
            int(opportunity.contracts or 1),
            1,
        )

        maximum_loss = float(
            opportunity.maximum_loss or 0.0
        )

        if maximum_loss > 0:
            return maximum_loss / contracts

        return 0.0

    def _per_contract_expected_profit(
        self,
        opportunity,
    ) -> float:
        contracts = max(
            int(opportunity.contracts or 1),
            1,
        )

        expected_profit = float(
            opportunity.expected_profit or 0.0
        )

        if expected_profit > 0:
            return expected_profit / contracts

        expected_return = float(
            opportunity.expected_return_pct or 0.0
        )

        if expected_return > 1:
            expected_return /= 100.0

        return (
            self._per_contract_capital(opportunity)
            * expected_return
        )

    def _per_contract_greeks(
        self,
        opportunity,
    ) -> dict[str, float]:
        profile = opportunity.greeks_profile

        if profile is None:
            return {
                "delta": 0.0,
                "gamma": 0.0,
                "theta": 0.0,
                "vega": 0.0,
                "rho": 0.0,
            }

        return {
            "delta": float(
                getattr(profile, "net_delta", 0.0)
                or 0.0
            ),
            "gamma": float(
                getattr(profile, "net_gamma", 0.0)
                or 0.0
            ),
            "theta": float(
                getattr(profile, "net_theta", 0.0)
                or 0.0
            ),
            "vega": float(
                getattr(profile, "net_vega", 0.0)
                or 0.0
            ),
            "rho": float(
                getattr(profile, "net_rho", 0.0)
                or 0.0
            ),
        }
