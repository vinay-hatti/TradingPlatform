from trading_ai.strategy_engine.option_leg import (
    OptionLeg,
)
from trading_ai.strategy_engine.strategy_catalog import (
    StrategyCatalog,
)
from trading_ai.strategy_engine.strategy_structure import (
    StrategyStructure,
)


class MultiStrategyBuilder:
    def build(
        self,
        symbol: str,
        strategy: str,
        underlying_price: float,
        legs: list,
        contracts: int = 1,
        description: str = "",
        metadata: dict | None = None,
    ) -> StrategyStructure:
        strategy = str(
            strategy or ""
        ).upper()

        if not StrategyCatalog.is_supported(
            strategy
        ):
            raise ValueError(
                f"Unsupported strategy: {strategy}"
            )

        option_legs = [
            self._to_leg(
                symbol=symbol,
                value=value,
            )
            for value in legs
        ]

        net_cash_flow = sum(
            leg.cash_flow_per_share
            for leg in option_legs
        )

        premium_type = (
            "CREDIT"
            if net_cash_flow > 0
            else "DEBIT"
        )

        risk_profile = (
            "DEFINED_RISK"
            if strategy
            not in {
                "SHORT_CALL",
                "SHORT_PUT",
            }
            else "UNDEFINED_RISK"
        )

        return StrategyStructure(
            symbol=symbol,
            strategy=strategy,
            legs=option_legs,
            underlying_price=underlying_price,
            contracts=contracts,
            direction=StrategyCatalog.default_direction(
                strategy
            ),
            premium_type=premium_type,
            risk_profile=risk_profile,
            complexity=StrategyCatalog.default_complexity(
                strategy
            ),
            description=description,
            metadata=dict(metadata or {}),
        )

    def bull_call_spread(
        self,
        symbol: str,
        underlying_price: float,
        expiry: str,
        long_strike: float,
        short_strike: float,
        long_premium: float,
        short_premium: float,
        contracts: int = 1,
    ) -> StrategyStructure:
        return self.build(
            symbol=symbol,
            strategy="BULL_CALL_SPREAD",
            underlying_price=underlying_price,
            contracts=contracts,
            legs=[
                {
                    "option_type": "CALL",
                    "action": "BUY",
                    "strike": long_strike,
                    "expiry": expiry,
                    "premium": long_premium,
                },
                {
                    "option_type": "CALL",
                    "action": "SELL",
                    "strike": short_strike,
                    "expiry": expiry,
                    "premium": short_premium,
                },
            ],
        )

    def bear_put_spread(
        self,
        symbol: str,
        underlying_price: float,
        expiry: str,
        long_strike: float,
        short_strike: float,
        long_premium: float,
        short_premium: float,
        contracts: int = 1,
    ) -> StrategyStructure:
        return self.build(
            symbol=symbol,
            strategy="BEAR_PUT_SPREAD",
            underlying_price=underlying_price,
            contracts=contracts,
            legs=[
                {
                    "option_type": "PUT",
                    "action": "BUY",
                    "strike": long_strike,
                    "expiry": expiry,
                    "premium": long_premium,
                },
                {
                    "option_type": "PUT",
                    "action": "SELL",
                    "strike": short_strike,
                    "expiry": expiry,
                    "premium": short_premium,
                },
            ],
        )

    def bull_put_spread(
        self,
        symbol: str,
        underlying_price: float,
        expiry: str,
        short_strike: float,
        long_strike: float,
        short_premium: float,
        long_premium: float,
        contracts: int = 1,
    ) -> StrategyStructure:
        return self.build(
            symbol=symbol,
            strategy="BULL_PUT_SPREAD",
            underlying_price=underlying_price,
            contracts=contracts,
            legs=[
                {
                    "option_type": "PUT",
                    "action": "SELL",
                    "strike": short_strike,
                    "expiry": expiry,
                    "premium": short_premium,
                },
                {
                    "option_type": "PUT",
                    "action": "BUY",
                    "strike": long_strike,
                    "expiry": expiry,
                    "premium": long_premium,
                },
            ],
        )

    def bear_call_spread(
        self,
        symbol: str,
        underlying_price: float,
        expiry: str,
        short_strike: float,
        long_strike: float,
        short_premium: float,
        long_premium: float,
        contracts: int = 1,
    ) -> StrategyStructure:
        return self.build(
            symbol=symbol,
            strategy="BEAR_CALL_SPREAD",
            underlying_price=underlying_price,
            contracts=contracts,
            legs=[
                {
                    "option_type": "CALL",
                    "action": "SELL",
                    "strike": short_strike,
                    "expiry": expiry,
                    "premium": short_premium,
                },
                {
                    "option_type": "CALL",
                    "action": "BUY",
                    "strike": long_strike,
                    "expiry": expiry,
                    "premium": long_premium,
                },
            ],
        )

    def iron_condor(
        self,
        symbol: str,
        underlying_price: float,
        expiry: str,
        long_put_strike: float,
        short_put_strike: float,
        short_call_strike: float,
        long_call_strike: float,
        long_put_premium: float,
        short_put_premium: float,
        short_call_premium: float,
        long_call_premium: float,
        contracts: int = 1,
    ) -> StrategyStructure:
        return self.build(
            symbol=symbol,
            strategy="IRON_CONDOR",
            underlying_price=underlying_price,
            contracts=contracts,
            legs=[
                {
                    "option_type": "PUT",
                    "action": "BUY",
                    "strike": long_put_strike,
                    "expiry": expiry,
                    "premium": long_put_premium,
                },
                {
                    "option_type": "PUT",
                    "action": "SELL",
                    "strike": short_put_strike,
                    "expiry": expiry,
                    "premium": short_put_premium,
                },
                {
                    "option_type": "CALL",
                    "action": "SELL",
                    "strike": short_call_strike,
                    "expiry": expiry,
                    "premium": short_call_premium,
                },
                {
                    "option_type": "CALL",
                    "action": "BUY",
                    "strike": long_call_strike,
                    "expiry": expiry,
                    "premium": long_call_premium,
                },
            ],
        )

    def long_straddle(
        self,
        symbol: str,
        underlying_price: float,
        expiry: str,
        strike: float,
        call_premium: float,
        put_premium: float,
        contracts: int = 1,
    ) -> StrategyStructure:
        return self.build(
            symbol=symbol,
            strategy="LONG_STRADDLE",
            underlying_price=underlying_price,
            contracts=contracts,
            legs=[
                {
                    "option_type": "CALL",
                    "action": "BUY",
                    "strike": strike,
                    "expiry": expiry,
                    "premium": call_premium,
                },
                {
                    "option_type": "PUT",
                    "action": "BUY",
                    "strike": strike,
                    "expiry": expiry,
                    "premium": put_premium,
                },
            ],
        )

    def long_strangle(
        self,
        symbol: str,
        underlying_price: float,
        expiry: str,
        put_strike: float,
        call_strike: float,
        put_premium: float,
        call_premium: float,
        contracts: int = 1,
    ) -> StrategyStructure:
        return self.build(
            symbol=symbol,
            strategy="LONG_STRANGLE",
            underlying_price=underlying_price,
            contracts=contracts,
            legs=[
                {
                    "option_type": "PUT",
                    "action": "BUY",
                    "strike": put_strike,
                    "expiry": expiry,
                    "premium": put_premium,
                },
                {
                    "option_type": "CALL",
                    "action": "BUY",
                    "strike": call_strike,
                    "expiry": expiry,
                    "premium": call_premium,
                },
            ],
        )

    def calendar(
        self,
        symbol: str,
        option_type: str,
        underlying_price: float,
        strike: float,
        short_expiry: str,
        long_expiry: str,
        short_premium: float,
        long_premium: float,
        contracts: int = 1,
    ) -> StrategyStructure:
        option_type = str(
            option_type or ""
        ).upper()

        strategy = (
            "CALENDAR_CALL"
            if option_type == "CALL"
            else "CALENDAR_PUT"
        )

        return self.build(
            symbol=symbol,
            strategy=strategy,
            underlying_price=underlying_price,
            contracts=contracts,
            legs=[
                {
                    "option_type": option_type,
                    "action": "SELL",
                    "strike": strike,
                    "expiry": short_expiry,
                    "premium": short_premium,
                },
                {
                    "option_type": option_type,
                    "action": "BUY",
                    "strike": strike,
                    "expiry": long_expiry,
                    "premium": long_premium,
                },
            ],
        )

    def diagonal(
        self,
        symbol: str,
        option_type: str,
        underlying_price: float,
        short_strike: float,
        long_strike: float,
        short_expiry: str,
        long_expiry: str,
        short_premium: float,
        long_premium: float,
        contracts: int = 1,
    ) -> StrategyStructure:
        option_type = str(
            option_type or ""
        ).upper()

        strategy = (
            "DIAGONAL_CALL"
            if option_type == "CALL"
            else "DIAGONAL_PUT"
        )

        return self.build(
            symbol=symbol,
            strategy=strategy,
            underlying_price=underlying_price,
            contracts=contracts,
            legs=[
                {
                    "option_type": option_type,
                    "action": "SELL",
                    "strike": short_strike,
                    "expiry": short_expiry,
                    "premium": short_premium,
                },
                {
                    "option_type": option_type,
                    "action": "BUY",
                    "strike": long_strike,
                    "expiry": long_expiry,
                    "premium": long_premium,
                },
            ],
        )

    def _to_leg(
        self,
        symbol: str,
        value,
    ) -> OptionLeg:
        if isinstance(value, OptionLeg):
            return value

        return OptionLeg(
            symbol=symbol,
            option_symbol=str(
                value.get(
                    "option_symbol",
                    "",
                )
            ),
            option_type=value["option_type"],
            action=value["action"],
            strike=value["strike"],
            expiry=value["expiry"],
            quantity=value.get(
                "quantity",
                1,
            ),
            premium=value.get(
                "premium",
                value.get(
                    "mid",
                    0.0,
                ),
            ),
            delta=value.get("delta", 0.0),
            gamma=value.get("gamma", 0.0),
            theta=value.get("theta", 0.0),
            vega=value.get("vega", 0.0),
            rho=value.get("rho", 0.0),
            implied_volatility=value.get(
                "implied_volatility",
                value.get("iv", 0.0),
            ),
            bid=value.get("bid", 0.0),
            ask=value.get("ask", 0.0),
            mid=value.get("mid", 0.0),
            volume=value.get("volume", 0),
            open_interest=value.get(
                "open_interest",
                0,
            ),
        )
