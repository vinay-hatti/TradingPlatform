from dataclasses import dataclass, field
from typing import Any


@dataclass
class DecisionRequest:
    """
    Input for one Institutional Decision Engine execution.

    Most per-symbol values use dictionaries keyed by uppercase symbol.
    """

    symbols: list[str]

    price_history_by_symbol: dict[str, Any]
    option_chain_by_symbol: dict[str, Any]

    signal_by_symbol: dict[str, str]
    market_regime_by_symbol: dict[str, str]
    technical_score_by_symbol: dict[str, float]

    underlying_price_by_symbol: dict[str, float] = field(
        default_factory=dict
    )

    atr_by_symbol: dict[str, float] = field(
        default_factory=dict
    )

    sector_by_symbol: dict[str, str] = field(
        default_factory=dict
    )

    industry_by_symbol: dict[str, str] = field(
        default_factory=dict
    )

    correlation_group_by_symbol: dict[str, str] = field(
        default_factory=dict
    )

    portfolio_fit_by_symbol: dict[str, float] = field(
        default_factory=dict
    )

    existing_positions: list[Any] = field(
        default_factory=list
    )

    strategy_limit_per_symbol: int = 3
    expiration_limit_per_strategy: int = 2
    strike_limit_per_expiration: int = 3

    target_dte: int = 30

    initial_capital: float = 100000.0

    include_rejected: bool = True
    construct_portfolio: bool = True

    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        self.symbols = [
            str(symbol).upper()
            for symbol in self.symbols
            if str(symbol or "").strip()
        ]

        self.symbols = list(
            dict.fromkeys(self.symbols)
        )

        self.strategy_limit_per_symbol = max(
            int(self.strategy_limit_per_symbol or 1),
            1,
        )

        self.expiration_limit_per_strategy = max(
            int(self.expiration_limit_per_strategy or 1),
            1,
        )

        self.strike_limit_per_expiration = max(
            int(self.strike_limit_per_expiration or 1),
            1,
        )

        self.target_dte = max(
            int(self.target_dte or 30),
            1,
        )

        self.initial_capital = float(
            self.initial_capital or 0.0
        )

        if self.initial_capital <= 0:
            raise ValueError(
                "initial_capital must be greater than zero"
            )
