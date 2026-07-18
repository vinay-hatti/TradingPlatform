from trading_ai.daily.trade_candidate import LiveTradeCandidate


class LiveTradeRecommender:

    def __init__(
        self,
        capital=100000.0,
        risk_per_trade_pct=0.02,
        max_position_pct=0.05,
        take_profit_pct=0.30,
        stop_loss_pct=0.15,
        contract_multiplier=100,
        minimum_option_price=0.25,
        maximum_contracts=50,
    ):
        self.capital = float(capital)
        self.risk_per_trade_pct = float(risk_per_trade_pct)
        self.max_position_pct = float(max_position_pct)
        self.take_profit_pct = float(take_profit_pct)
        self.stop_loss_pct = float(stop_loss_pct)
        self.contract_multiplier = int(contract_multiplier)
        self.minimum_option_price = float(minimum_option_price)
        self.maximum_contracts = int(maximum_contracts)

    def confidence(self, ai_score):

        ai_score = float(ai_score)

        if ai_score >= 85:
            return "HIGH"

        if ai_score >= 70:
            return "MEDIUM"

        if ai_score >= 55:
            return "LOW"

        return "AVOID"

    def _contracts(self, option_price):

        option_price = float(option_price)

        if option_price <= 0:
            return 0

        max_risk_dollars = self.capital * self.risk_per_trade_pct
        max_position_dollars = self.capital * self.max_position_pct

        max_alloc = min(
            max_risk_dollars,
            max_position_dollars,
        )

        cost_per_contract = option_price * self.contract_multiplier

        return int(max_alloc // cost_per_contract)

    def build(self, candidate):

        entry = float(candidate.option_price)

        target = entry * (1.0 + self.take_profit_pct)
        stop = entry * (1.0 - self.stop_loss_pct)

        if entry < self.minimum_option_price:

            contracts = 0

        else:

            contracts = min(

                self._contracts(entry),

                self.maximum_contracts,

            )
        estimated_cost = (
            contracts
            * entry
            * self.contract_multiplier
        )

        max_risk = (
            contracts
            * max(entry - stop, 0.0)
            * self.contract_multiplier
        )

        estimated_reward = (
            contracts
            * max(target - entry, 0.0)
            * self.contract_multiplier
        )

        reward_risk_ratio = (
            estimated_reward / max_risk
            if max_risk > 0
            else 0.0
        )

        notes = []
        if getattr(candidate, "contract_ticker", ""):
            notes.append(f"Live contract: {candidate.contract_ticker}.")
            notes.append(f"Entry source: {candidate.price_source}; quote time: {candidate.quote_timestamp or 'unavailable'}.")
        else:
            notes.append("Synthetic proxy data; not a live listed contract.")
        if entry < self.minimum_option_price:
            notes.append(
                "Rejected for sizing: option proxy price "
                "is below the minimum tradable proxy premium."
            )

        if contracts <= 0:
            notes.append("Position size is zero under current risk limits.")

        if candidate.ai_score >= 85:
            notes.append("High AI score candidate.")
        elif candidate.ai_score >= 70:
            notes.append("Medium AI score candidate.")
        else:
            notes.append("Lower-confidence candidate; review carefully.")

        if candidate.portfolio_penalty > 0:
            notes.append("Portfolio exposure penalty applied.")

        if candidate.signal == "CALL":
            notes.append("Bullish options candidate.")
        elif candidate.signal == "PUT":
            notes.append("Bearish options candidate.")

        if getattr(candidate, "expiry_source", "") == "STANDARD_FRIDAY_PROXY":
            notes.append(
                "Expiration is a standard-Friday proxy; "
                "verify the listed contract with the broker."
            )

        return LiveTradeCandidate(
            symbol=candidate.symbol,
            signal=candidate.signal,
            strategy=candidate.strategy,
            sector=candidate.sector,
            ai_score=float(candidate.ai_score),
            confidence=self.confidence(candidate.ai_score),
            ranking_reason=candidate.ranking_reason,
            underlying_price=float(candidate.close),
            strike=float(candidate.strike),
            expiry=candidate.expiry,
            dte=int(candidate.dte),
            expiry_source=getattr(
                candidate,
                "expiry_source",
                "STANDARD_FRIDAY_PROXY",
            ),
            option_entry=entry,
            target_price=target,
            stop_price=stop,
            contracts=contracts,
            estimated_cost=estimated_cost,
            max_risk=max_risk,
            estimated_reward=estimated_reward,
            reward_risk_ratio=reward_risk_ratio,
            delta=float(candidate.delta),
            gamma=float(candidate.gamma),
            theta=float(candidate.theta),
            vega=float(candidate.vega),
            rho=float(candidate.rho),
            volatility=float(candidate.volatility),
            market_regime=candidate.market_regime,
            technical_score=float(candidate.technical_score),
            greeks_score=float(candidate.greeks_score),
            regime_score=float(candidate.regime_score),
            volatility_score=float(candidate.volatility_score),
            risk_score=float(candidate.risk_score),
            contract_ticker=getattr(candidate, "contract_ticker", ""),
            bid=float(getattr(candidate, "bid", 0.0)),
            ask=float(getattr(candidate, "ask", 0.0)),
            last_price=float(getattr(candidate, "last_price", 0.0)),
            price_source=getattr(candidate, "price_source", ""),
            option_data_source=getattr(candidate, "option_data_source", ""),
            quote_timestamp=getattr(candidate, "quote_timestamp", ""),
            open_interest=int(getattr(candidate, "open_interest", 0)),
            option_volume=int(getattr(candidate, "option_volume", 0)),
            spread_pct=float(getattr(candidate, "spread_pct", 0.0)),
            contract_selection_score=float(getattr(candidate, "contract_selection_score", 0.0)),
            liquidity_score=float(getattr(candidate, "liquidity_score", 0.0)),
            delta_selection_score=float(getattr(candidate, "delta_selection_score", 0.0)),
            expiration_selection_score=float(getattr(candidate, "expiration_selection_score", 0.0)),
            strike_selection_score=float(getattr(candidate, "strike_selection_score", 0.0)),
            spread_selection_score=float(getattr(candidate, "spread_selection_score", 0.0)),
            open_interest_selection_score=float(getattr(candidate, "open_interest_selection_score", 0.0)),
            volume_selection_score=float(getattr(candidate, "volume_selection_score", 0.0)),
            portfolio_penalty=float(candidate.portfolio_penalty),
            portfolio_notes=list(candidate.portfolio_notes),
            trade_notes=notes,
        )

    def build_many(self, candidates):

        return [
            self.build(candidate)
            for candidate in candidates
        ]
