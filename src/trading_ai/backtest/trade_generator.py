from trading_ai.options.pricing_service import (
    OptionPricingService,
    HistoricalOptionPricingService,
)


class HistoricalTradeGenerator:
    def __init__(
        self,
        datasource,
        simulator,
        contracts=1,
        max_hold_days=10,
        position_sizer=None,
        capital=100000.0,
        option_premium_pct=0.08,
        pricing_service=None,
        pricing_dte=30,
        min_delta=0.0,
        max_delta=1.0,
        min_vega=0.0,
        max_vega=999.0,
        max_theta=999.0,
        use_historical_options=False,
        fallback_to_black_scholes=True,
        min_option_volume=0,
        min_open_interest=0,
        max_spread_pct=1.0,
    ):
        self.datasource = datasource
        self.simulator = simulator
        self.contracts = contracts
        self.max_hold_days = max_hold_days
        self.position_sizer = position_sizer
        self.capital = float(capital)
        self.option_premium_pct = float(option_premium_pct)

        # Pure Black-Scholes engine. Used for synthetic fallback entries
        # and for mark-to-model exit pricing.
        self.pricing = pricing_service or OptionPricingService()
        self.pricing_dte = int(pricing_dte)

        self.min_delta = float(min_delta)
        self.max_delta = float(max_delta)
        self.min_vega = float(min_vega)
        self.max_vega = float(max_vega)
        self.max_theta = float(max_theta)

        # Historical option-chain behavior is owned by this generator.
        self.use_historical_options = bool(use_historical_options)
        self.fallback_to_black_scholes = bool(fallback_to_black_scholes)

        self.historical_pricing = HistoricalOptionPricingService(
            min_volume=min_option_volume,
            min_open_interest=min_open_interest,
            max_spread_pct=max_spread_pct,
        )

        self.rejected = []

    def _market_regime(self, signal):
        return (
            signal.get("market_regime")
            or signal.get("regime")
            or signal.get("trend_regime")
            or "UNKNOWN"
        )

    def _reject(self, signal, reason, entry_price=0.0):
        from trading_ai.backtest.trade import BacktestTrade

        trade = BacktestTrade(
            symbol=signal.get("symbol", ""),
            entry_date=signal.get("date"),
            exit_date=signal.get("date"),
            strategy=(
                "LONG_CALL"
                if signal.get("signal") == "CALL"
                else "LONG_PUT"
            ),
            signal=signal.get("signal", ""),
            strike=float(signal.get("close", 0.0) or 0.0),
            expiry="NO_CONTRACT",
            entry_price=float(entry_price or 0.0),
            exit_price=0.0,
            contracts=0,
            pnl=0.0,
            pnl_pct=0.0,
            max_profit=0.0,
            max_drawdown=0.0,
            days_held=0,
            exit_reason="REJECTED",
            rank_score=float(signal.get("score", 0.0) or 0.0),
            option_score=float(signal.get("score", 0.0) or 0.0),
            pop=0.0,
            liquidity=0.0,
            atm_score=0.0,
            market_regime=self._market_regime(signal),
            regime=self._market_regime(signal),
            pricing_source="rejected",
            entry_pricing_source="rejected",
            exit_pricing_source="rejected",
            position_size=0.0,
            initial_risk=0.0,
            r_multiple=0.0,
        )

        self.rejected.append({
            "trade": trade,
            "reason": reason,
        })

    def _contracts_for_trade(self, entry_price):
        if self.position_sizer is None:
            return int(self.contracts)

        return self.position_sizer.contracts(
            capital=self.capital,
            option_price=entry_price,
        )

    def _black_scholes_price(
        self,
        signal,
        underlying_price,
        strike,
        hv20,
        dte=None,
    ):
        return self.pricing.option_price(
            signal=signal,
            spot=underlying_price,
            strike=strike,
            hv20=hv20,
            dte=dte or self.pricing_dte,
        )

    def _historical_entry(self, signal, underlying_price):
        if not self.use_historical_options:
            return None

        return self.historical_pricing.price(
            underlying_symbol=signal["symbol"],
            quote_date=signal["date"],
            option_type=signal["signal"],
            target_strike=underlying_price,
            target_dte=self.pricing_dte,
        )

    def _black_scholes_entry(self, signal, underlying_price, hv20):
        greeks = self.pricing.greeks(
            signal=signal["signal"],
            spot=underlying_price,
            strike=underlying_price,
            hv20=hv20,
            dte=self.pricing_dte,
        )

        return {
            "source": "black_scholes_proxy",
            "price": self._black_scholes_price(
                signal=signal["signal"],
                underlying_price=underlying_price,
                strike=underlying_price,
                hv20=hv20,
                dte=self.pricing_dte,
            ),
            "strike": underlying_price,
            "expiry": "BS_ENTRY_PROXY_EXIT",
            "delta": greeks["delta"],
            "gamma": greeks["gamma"],
            "theta": greeks["theta"],
            "vega": greeks["vega"],
            "rho": greeks["rho"],
            "iv": greeks["volatility"],
            "liquidity": 0.0,
            "option_symbol": "",
            "option_volume": 0,
            "option_open_interest": 0,
            "option_spread_pct": 0.0,
        }

    def _entry_price_and_metadata(self, signal, underlying_price, hv20):
        historical = self._historical_entry(signal, underlying_price)

        if historical:
            return {
                "source": "historical_chain",
                "price": float(historical["price"]),
                "strike": float(historical["strike"]),
                "expiry": historical["expiry"],
                "delta": historical.get("delta"),
                "gamma": historical.get("gamma"),
                "theta": historical.get("theta"),
                "vega": historical.get("vega"),
                "rho": historical.get("rho"),
                "iv": historical.get("implied_volatility"),
                "liquidity": float(historical.get("volume") or 0),
                "option_symbol": historical.get("option_symbol", ""),
                "option_volume": int(historical.get("volume") or 0),
                "option_open_interest": int(historical.get("open_interest") or 0),
                "option_spread_pct": float(historical.get("spread_pct") or 0.0),
            }

        if self.use_historical_options and not self.fallback_to_black_scholes:
            return None

        return self._black_scholes_entry(
            signal=signal,
            underlying_price=underlying_price,
            hv20=hv20,
        )

    def generate(self, signals, price_history):
        trades = []
        self.rejected = []

        for signal in signals:
            entry_date = signal["date"]
            underlying_price = float(signal["close"])
            hv20 = float(signal.get("hv20", signal.get("iv", 0.30)) or 0.30)

            entry = self._entry_price_and_metadata(
                signal=signal,
                underlying_price=underlying_price,
                hv20=hv20,
            )

            if not entry:
                self._reject(signal, "NO_HISTORICAL_ENTRY_CONTRACT")
                continue

            entry_price = float(entry["price"])

            if entry_price <= 0:
                self._reject(signal, "INVALID_OPTION_ENTRY_PRICE")
                continue

            abs_delta = abs(float(entry["delta"] or 0.0))
            abs_theta = abs(float(entry["theta"] or 0.0))
            vega = float(entry["vega"] or 0.0)

            if abs_delta < self.min_delta:
                self._reject(signal, "DELTA_BELOW_MIN", entry_price)
                continue

            if abs_delta > self.max_delta:
                self._reject(signal, "DELTA_ABOVE_MAX", entry_price)
                continue

            if vega < self.min_vega:
                self._reject(signal, "VEGA_BELOW_MIN", entry_price)
                continue

            if vega > self.max_vega:
                self._reject(signal, "VEGA_ABOVE_MAX", entry_price)
                continue

            if abs_theta > self.max_theta:
                self._reject(signal, "THETA_ABOVE_MAX", entry_price)
                continue

            contracts = self._contracts_for_trade(entry_price)

            if contracts <= 0:
                self._reject(signal, "POSITION_SIZE_ZERO", entry_price)
                continue

            raw_future_prices = self.datasource.get_next_days(
                price_history,
                entry_date,
                days=self.max_hold_days,
            )

            if not raw_future_prices:
                self._reject(signal, "NO_FUTURE_PRICE_DATA", entry_price)
                continue

            future_prices = []

            for idx, p in enumerate(raw_future_prices, start=1):
                remaining_dte = max(self.pricing_dte - idx, 1)
                future_underlying = float(p["price"])

                option_price = self._black_scholes_price(
                    signal=signal["signal"],
                    underlying_price=future_underlying,
                    strike=float(entry["strike"]),
                    hv20=hv20,
                    dte=remaining_dte,
                )

                if option_price is None or float(option_price) <= 0:
                    continue

                future_prices.append({
                    "date": p["date"],
                    "price": option_price,
                })

            if not future_prices:
                self._reject(signal, "NO_OPTION_EXIT_PRICES", entry_price)
                continue

            market_regime = self._market_regime(signal)
            position_size = float(entry_price) * int(contracts) * 100.0
            initial_risk = position_size

            trade = self.simulator.simulate(
                symbol=signal["symbol"],
                signal=signal["signal"],
                strategy=(
                    "LONG_CALL"
                    if signal["signal"] == "CALL"
                    else "LONG_PUT"
                ),
                strike=float(entry["strike"]),
                expiry=str(entry["expiry"]),
                entry_date=entry_date,
                entry_price=entry_price,
                future_prices=future_prices,
                contracts=contracts,
                rank_score=float(signal.get("score", 0.0)),
                option_score=float(signal.get("score", 0.0)),
                pop=None,
                liquidity=float(entry["liquidity"]),
                atm_score=100.0,
                entry_delta=float(entry["delta"] or 0.0),
                entry_gamma=float(entry["gamma"] or 0.0),
                entry_theta=float(entry["theta"] or 0.0),
                entry_vega=float(entry["vega"] or 0.0),
                entry_rho=float(entry["rho"] or 0.0),
                entry_iv=float(entry["iv"] or hv20),
                entry_volatility=float(entry["iv"] or hv20),
                entry_dte=self.pricing_dte,
            )

            # Preserve the actual model-derived exit price used for reporting.
            exit_model_price = None
            trade_exit_date = str(getattr(trade, "exit_date", ""))
            for fp in future_prices:
                if str(fp.get("date", "")) == trade_exit_date:
                    exit_model_price = fp.get("price")
                    break
            if exit_model_price is None and future_prices:
                exit_model_price = future_prices[-1].get("price")

            # Store the raw model-derived exit premium for reporting.
            # Do not let a missing value masquerade as a real 0.00 premium.
            trade.model_exit_price = (
                float(exit_model_price)
                if exit_model_price not in (None, "")
                else None
            )

            # Attach reporting metadata without requiring simulator signature changes.
            trade.market_regime = market_regime
            trade.regime = market_regime
            trade.pricing_source = entry.get("source", "")
            trade.entry_pricing_source = entry.get("source", "")
            trade.exit_pricing_source = "black_scholes_mark_to_model"
            trade.option_symbol = entry.get("option_symbol", "")
            trade.option_volume = int(entry.get("option_volume", 0) or 0)
            trade.option_open_interest = int(entry.get("option_open_interest", 0) or 0)
            trade.option_spread_pct = float(entry.get("option_spread_pct", 0.0) or 0.0)
            trade.position_size = position_size
            trade.initial_risk = initial_risk
            trade.r_multiple = (float(getattr(trade, "net_pnl", getattr(trade, "pnl", 0.0))) / initial_risk) if initial_risk else 0.0

            trades.append(trade)

        return trades
