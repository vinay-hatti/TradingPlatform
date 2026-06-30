from trading_ai.domain.context import TradeContext
from trading_ai.backtest.portfolio import Portfolio
from trading_ai.backtest.exit_engine import ExitEngine


class BacktestEngine:

    def __init__(self, strategy_engine, market, pipeline, config=None):
        self.strategy_engine = strategy_engine
        self.market = market
        self.pipeline = pipeline
        self.config = config

        if config:
            self.exit_engine = ExitEngine(
                stop_loss_pct=config.stop_loss_pct,
                take_profit_pct=config.take_profit_pct,
                max_holding_bars=config.max_holding_bars,
            )
        else:
            self.exit_engine = ExitEngine()

    def run(self, symbols, start, end):

        start_date = str(start)
        end_date = str(end)

        portfolio = Portfolio(
            initial_capital=self.config.initial_capital if self.config else 100000.0,
            risk_per_trade_pct=self.config.risk_per_trade_pct if self.config else 0.01,
            max_contracts=self.config.max_contracts if self.config else 5,
            min_abs_delta=self.config.min_abs_delta if self.config else 0.30,
            max_abs_delta=self.config.max_abs_delta if self.config else 0.70,
            max_open_positions=self.config.max_open_positions if self.config else 2,
            max_daily_loss_pct=self.config.max_daily_loss_pct if self.config else 0.03,
            max_drawdown_pct=0.05,
        )

        for symbol in symbols:

#            print(f"Running {symbol}")

            df = self.market.get_history(symbol, start_date, end_date)
            df = df.reset_index(drop=True)
            df = self.pipeline.run(df)

#            print("Rows:", len(df))

            analytics = self.market.provider.get_analytics(symbol)

            for i in range(50, len(df)):

                row = df.iloc[i]

                ctx = TradeContext(
                    symbol=str(row.get("symbol", symbol)),
                    close=float(row.get("close", 0.0)),
                    ema20=float(row.get("ema20", 0.0)),
                    ema50=float(row.get("ema50", 0.0)),
                    ema200=float(row.get("ema200", 0.0)),
                    rsi14=float(row.get("rsi14", 0.0)),
                    atr14=float(row.get("atr14", 0.0)),
                    market_regime=str(row.get("market_regime", "CHOP")),
                    call_score=float(row.get("call_score", 0.0)),
                    put_score=float(row.get("put_score", 0.0)),
                    expected_move_1d=float(row.get("expected_move_1d", 0.0)),
                    em_ratio=float(row.get("em_ratio", 0.0)),
                    iv=float(row.get("iv", 0.0)),
                    iv_rank=float(row.get("iv_rank", 0.5)),
                    option=None,
                )

                if portfolio.has_open_position(symbol):

                    position = portfolio.open_positions[symbol]

                    current_option_price = portfolio.price_option(
                        stock_price=ctx.close,
                        strike=position.strike,
                        signal=position.signal,
                        volatility=max(ctx.iv, 0.25),
                    )

                    should_exit, reason = self.exit_engine.check_exit(
                        position,
                        i,
                        current_option_price,
                    )

                    if should_exit:
                        portfolio.close_position(
                            symbol,
                            i,
                            ctx.close,
                            reason,
                    )

                    portfolio.mark_to_market({symbol: ctx.close})
                    continue

                recommendation = self.strategy_engine.recommend(
                    symbol,
                    ctx,
                    analytics,
                )

                if recommendation is None:
                    portfolio.mark_to_market({symbol: ctx.close})
                    continue

                if recommendation.signal == "CALL":
                    min_score = self.config.min_call_score if self.config else 60.0
                    if recommendation.score < min_score:
                        portfolio.mark_to_market({symbol: ctx.close})
                        continue

                allowed_strategies = self.config.allowed_strategies if self.config else None

                if allowed_strategies is not None:
                    if recommendation.strategy not in allowed_strategies:
                        portfolio.mark_to_market({symbol: ctx.close})
                        continue

                if recommendation.signal == "PUT":
                    min_score = self.config.min_put_score if self.config else 60.0
                    if recommendation.score < min_score:
                        portfolio.mark_to_market({symbol: ctx.close})
                        continue

                allowed_regimes = self.config.allowed_regimes if self.config else None

                if allowed_regimes is not None:
                    if ctx.market_regime not in allowed_regimes:
                        portfolio.mark_to_market({symbol: ctx.close})
                        continue

                portfolio.open_position(
                    recommendation,
                    ctx,
                    i,
                )

                portfolio.mark_to_market({symbol: ctx.close})

        return {
            "open_positions": portfolio.open_positions,
            "closed_positions": portfolio.closed_positions,
            "equity_curve": portfolio.equity_curve,
        }
