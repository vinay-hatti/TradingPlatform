from dataclasses import dataclass, field


@dataclass
class PortfolioPosition:
    symbol: str
    strategy: str
    signal: str
    quantity: int
    option_price: float
    contract_value: float
    market_value: float
    sector: str = "UNKNOWN"


@dataclass
class PortfolioSnapshot:
    initial_capital: float
    cash: float
    market_value: float
    net_liquidation: float
    positions: list[PortfolioPosition] = field(default_factory=list)
    sector_exposure: dict[str, float] = field(default_factory=dict)
    strategy_exposure: dict[str, float] = field(default_factory=dict)


class PortfolioManager:

    def __init__(
        self,
        initial_capital: float = 100000.0,
        max_symbol_exposure_pct: float = 0.05,
        max_sector_exposure_pct: float = 0.30,
        max_strategy_exposure_pct: float = 0.50,
    ):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions = []

        self.max_symbol_exposure_pct = max_symbol_exposure_pct
        self.max_sector_exposure_pct = max_sector_exposure_pct
        self.max_strategy_exposure_pct = max_strategy_exposure_pct

    def add_position(
        self,
        symbol: str,
        strategy: str,
        signal: str,
        quantity: int,
        option_price: float,
        sector: str = "UNKNOWN",
    ):

        contract_value = option_price * 100.0
        market_value = contract_value * quantity

        if market_value > self.cash:
            return False

        position = PortfolioPosition(
            symbol=symbol,
            strategy=strategy,
            signal=signal,
            quantity=quantity,
            option_price=option_price,
            contract_value=contract_value,
            market_value=market_value,
            sector=sector,
        )

        self.positions.append(position)
        self.cash -= market_value

        return True

    def total_market_value(self) -> float:
        return sum(p.market_value for p in self.positions)

    def net_liquidation(self) -> float:
        return self.cash + self.total_market_value()

    def symbol_exposure(self) -> dict[str, float]:

        exposure = {}

        for p in self.positions:
            exposure[p.symbol] = exposure.get(p.symbol, 0.0) + p.market_value

        return exposure

    def sector_exposure(self) -> dict[str, float]:

        exposure = {}

        for p in self.positions:
            exposure[p.sector] = exposure.get(p.sector, 0.0) + p.market_value

        return exposure

    def strategy_exposure(self) -> dict[str, float]:

        exposure = {}

        for p in self.positions:
            exposure[p.strategy] = exposure.get(p.strategy, 0.0) + p.market_value

        return exposure

    def can_add_trade(
        self,
        symbol: str,
        strategy: str,
        quantity: int,
        option_price: float,
        sector: str = "UNKNOWN",
    ):

        contract_value = option_price * 100.0
        trade_value = contract_value * quantity

        if quantity <= 0:
            return False, "NO_QUANTITY"

        if trade_value > self.cash:
            return False, "INSUFFICIENT_CASH"

        max_symbol_value = self.initial_capital * self.max_symbol_exposure_pct
        max_sector_value = self.initial_capital * self.max_sector_exposure_pct
        max_strategy_value = self.initial_capital * self.max_strategy_exposure_pct

        symbol_current = self.symbol_exposure().get(symbol, 0.0)
        sector_current = self.sector_exposure().get(sector, 0.0)
        strategy_current = self.strategy_exposure().get(strategy, 0.0)

        if symbol_current + trade_value > max_symbol_value:
            return False, "MAX_SYMBOL_EXPOSURE"

        if sector_current + trade_value > max_sector_value:
            return False, "MAX_SECTOR_EXPOSURE"

        if strategy_current + trade_value > max_strategy_value:
            return False, "MAX_STRATEGY_EXPOSURE"

        return True, "OK"

    def snapshot(self) -> PortfolioSnapshot:

        market_value = self.total_market_value()

        return PortfolioSnapshot(
            initial_capital=self.initial_capital,
            cash=self.cash,
            market_value=market_value,
            net_liquidation=self.cash + market_value,
            positions=self.positions,
            sector_exposure=self.sector_exposure(),
            strategy_exposure=self.strategy_exposure(),
        )
