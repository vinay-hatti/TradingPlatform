from trading_ai.backtest.trade import BacktestTrade


class OptionTradeSimulator:

    def __init__(
        self,
        take_profit_pct=0.25,
        stop_loss_pct=-0.12,
        max_hold_days=10,
        commission_per_contract=0.65,
        slippage_per_contract=0.05,
    ):
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.max_hold_days = max_hold_days
        self.commission_per_contract = commission_per_contract
        self.slippage_per_contract = slippage_per_contract

    def simulate(
        self,
        symbol,
        signal,
        strategy,
        strike,
        expiry,
        entry_date,
        entry_price,
        future_prices,
        contracts=1,
        rank_score=0.0,
        option_score=0.0,
        pop=0.0,
        liquidity=0.0,
        atm_score=0.0,
        entry_delta=0.0,
        entry_gamma=0.0,
        entry_theta=0.0,
        entry_vega=0.0,
        entry_rho=0.0,
        entry_iv=0.0,
        entry_volatility=0.0,
        entry_dte=0,
    ):
        entry_price = float(entry_price)
        contracts = int(contracts)

        # future_prices contains OPTION PREMIUMS, not underlying stock prices.
        # For long calls and long puts, PnL is based on option premium movement:
        #   PnL = exit premium - entry premium
        # Do not invert PUT trades here.
        signal = str(signal).upper()

        max_profit = 0.0
        max_drawdown = 0.0

        exit_price = entry_price
        exit_date = entry_date
        exit_reason = "TIME_STOP"

        for idx, price_point in enumerate(future_prices, start=1):
            current_date = price_point["date"]
            current_price = float(price_point["price"])

            gross_pnl = (
                (current_price - entry_price)
                * contracts
                * 100.0
            )

            pnl_pct = (
                (current_price - entry_price)
                / max(entry_price, 0.01)
            )

            max_profit = max(max_profit, gross_pnl)
            max_drawdown = min(max_drawdown, gross_pnl)

            exit_price = current_price
            exit_date = current_date

            if pnl_pct >= self.take_profit_pct:
                exit_reason = "TAKE_PROFIT"
                break

            if pnl_pct <= self.stop_loss_pct:
                exit_reason = "STOP_LOSS"
                break

            if idx >= self.max_hold_days:
                exit_reason = "TIME_STOP"
                break

        gross_pnl = (
            (exit_price - entry_price)
            * contracts
            * 100.0
        )

        fees = (
            self.commission_per_contract
            + self.slippage_per_contract
        ) * contracts * 2.0

        net_pnl = gross_pnl - fees

        pnl_pct = (
            net_pnl
            / max(entry_price * contracts * 100.0, 0.01)
        )

        days_held = max(
            (exit_date - entry_date).days,
            0,
        )

        return BacktestTrade(
            symbol=symbol,
            entry_date=entry_date,
            exit_date=exit_date,
            strategy=strategy,
            signal=signal,
            strike=float(strike),
            expiry=str(expiry),
            entry_price=entry_price,
            exit_price=exit_price,
            entry_delta=entry_delta,
            entry_gamma=entry_gamma,
            entry_theta=entry_theta,
            entry_vega=entry_vega,
            entry_rho=entry_rho,
            entry_iv=entry_iv,
            entry_volatility=entry_volatility,
            entry_dte=entry_dte,
            contracts=contracts,
            pnl=net_pnl,
            pnl_pct=pnl_pct,
            max_profit=max_profit,
            max_drawdown=max_drawdown,
            days_held=days_held,
            exit_reason=exit_reason,
            rank_score=rank_score,
            option_score=option_score,
            pop=pop,
            liquidity=liquidity,
            atm_score=atm_score,
            gross_pnl=gross_pnl,
            fees=fees,
            net_pnl=net_pnl,
        )
