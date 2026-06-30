from trading_ai.backtest.position import Position
from trading_ai.options.pricing import BlackScholesPricer


class Portfolio:

    def __init__(
        self,
        initial_capital=100000.0,
        risk_per_trade_pct=0.01,
        max_contracts=5,
        min_option_price=0.50,
        min_abs_delta=0.30,
        max_abs_delta=0.70,
    ):
        self.open_positions = {}
        self.closed_positions = []
        self.equity_curve = []

        self.initial_capital = initial_capital
        self.realized_pnl = 0.0
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_contracts = max_contracts
        self.min_option_price = min_option_price
        self.pricer = BlackScholesPricer()
        self.min_abs_delta = min_abs_delta
        self.max_abs_delta = max_abs_delta

    def has_open_position(self, symbol: str) -> bool:
        return symbol in self.open_positions

    def price_option(
        self,
        stock_price: float,
        strike: float,
        signal: str,
        volatility: float = 0.25,
        time_to_expiry: float = 30 / 365,
    ) -> float:

        return self.pricer.price(
            spot=stock_price,
            strike=strike,
            time_to_expiry=time_to_expiry,
            volatility=volatility,
            option_type=signal,
        )

    def open_position(self, recommendation, ctx, index: int):

        if self.has_open_position(recommendation.symbol):
            return None

        if recommendation.signal == "HOLD":
            return None

        entry_option_price = self.price_option(
            stock_price=ctx.close,
            strike=recommendation.strike,
            signal=recommendation.signal,
            volatility=max(ctx.iv, 0.25),
        )

        min_option_price = getattr(self, "min_option_price", 0.50)
        if entry_option_price < min_option_price:
            return None

        min_abs_delta = getattr(self, "min_abs_delta", 0.30)
        max_abs_delta = getattr(self, "max_abs_delta", 0.70)

        abs_delta = abs(recommendation.delta)

        if abs_delta < min_abs_delta or abs_delta > max_abs_delta:
            return None

        position = Position(
            symbol=recommendation.symbol,
            signal=recommendation.signal,
            strategy=recommendation.strategy,
            entry_index=index,
            stock_entry_price=ctx.close,
            option_entry_price=entry_option_price,
            strike=recommendation.strike,
            expiry=recommendation.expiry,
            delta=recommendation.delta,
            size=self._position_size(ctx, entry_option_price),
            score=recommendation.score,
            regime=ctx.market_regime,
        )

        self.open_positions[position.symbol] = position

        return position

    def close_position(self, symbol: str, index: int, price: float, reason: str):

        position = self.open_positions.get(symbol)

        if position is None:
            return None

        current_option_price = self.price_option(
            stock_price=price,
            strike=position.strike,
            signal=position.signal,
            volatility=0.25,
        )

        position.close(
            index=index,
            stock_price=price,
            option_price=current_option_price,
            reason=reason,
        )

        self.realized_pnl += position.pnl

        self.closed_positions.append(position)

        del self.open_positions[symbol]

        return position

    def mark_to_market(self, prices: dict):

        unrealized_pnl = 0.0

        for symbol, position in self.open_positions.items():

            price = prices.get(symbol)

            if price is None:
                continue

            current_option_price = self.price_option(
                stock_price=price,
                strike=position.strike,
                signal=position.signal,
                volatility=0.25,
            )

            unrealized_pnl += position.mark_pnl(current_option_price)

        total_equity_pnl = self.realized_pnl + unrealized_pnl

        self.equity_curve.append(total_equity_pnl)

        return total_equity_pnl

    def _position_size(self, ctx, option_price=None):

        account_equity = self.initial_capital + self.realized_pnl

        dollars_at_risk = account_equity * self.risk_per_trade_pct

        option_price = max(option_price or 0.0, 0.01)

        contract_value = option_price * 100

        qty = int(dollars_at_risk / contract_value)

        qty = max(1, qty)
        qty = min(qty, self.max_contracts)

        return qty

