from dataclasses import dataclass, field

from trading_ai.strategy_engine.option_leg import (
    OptionLeg,
)


@dataclass
class StrategyStructure:
    symbol: str
    strategy: str

    legs: list[OptionLeg]

    underlying_price: float
    contracts: int = 1

    direction: str = "NEUTRAL"
    premium_type: str = ""
    risk_profile: str = "DEFINED_RISK"
    complexity: str = "MULTI_LEG"

    description: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        self.symbol = str(
            self.symbol or ""
        ).upper()

        self.strategy = str(
            self.strategy or ""
        ).upper()

        self.direction = str(
            self.direction or "NEUTRAL"
        ).upper()

        self.premium_type = str(
            self.premium_type or ""
        ).upper()

        self.risk_profile = str(
            self.risk_profile or "DEFINED_RISK"
        ).upper()

        self.complexity = str(
            self.complexity or "MULTI_LEG"
        ).upper()

        self.underlying_price = float(
            self.underlying_price or 0.0
        )

        self.contracts = max(
            int(self.contracts or 1),
            1,
        )

        if not self.legs:
            raise ValueError(
                "StrategyStructure requires at least one leg"
            )

    @property
    def expiries(self) -> list[str]:
        return sorted(
            set(
                leg.expiry
                for leg in self.legs
            )
        )

    @property
    def strikes(self) -> list[float]:
        return sorted(
            set(
                leg.strike
                for leg in self.legs
            )
        )

    @property
    def is_multi_expiration(self) -> bool:
        return len(self.expiries) > 1

    @property
    def net_cash_flow_per_share(self) -> float:
        return sum(
            leg.cash_flow_per_share
            for leg in self.legs
        )

    @property
    def net_cash_flow_dollars(self) -> float:
        return (
            self.net_cash_flow_per_share
            * 100.0
            * self.contracts
        )

    @property
    def net_debit_per_share(self) -> float:
        return max(
            -self.net_cash_flow_per_share,
            0.0,
        )

    @property
    def net_credit_per_share(self) -> float:
        return max(
            self.net_cash_flow_per_share,
            0.0,
        )

    @property
    def net_delta(self) -> float:
        return sum(
            leg.sign
            * leg.delta
            * leg.quantity
            for leg in self.legs
        )

    @property
    def net_gamma(self) -> float:
        return sum(
            leg.sign
            * leg.gamma
            * leg.quantity
            for leg in self.legs
        )

    @property
    def net_theta(self) -> float:
        return sum(
            leg.sign
            * leg.theta
            * leg.quantity
            for leg in self.legs
        )

    @property
    def net_vega(self) -> float:
        return sum(
            leg.sign
            * leg.vega
            * leg.quantity
            for leg in self.legs
        )

    @property
    def net_rho(self) -> float:
        return sum(
            leg.sign
            * leg.rho
            * leg.quantity
            for leg in self.legs
        )
