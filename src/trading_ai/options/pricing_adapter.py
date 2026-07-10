from trading_ai.options.pricing_service import HistoricalOptionPricingService


class OptionPricingAdapter:

    def __init__(
        self,
        black_scholes_pricer,
        use_historical_chain=False,
        fallback_to_black_scholes=True,
        min_volume=0,
        min_open_interest=0,
        max_spread_pct=1.0,
    ):
        self.black_scholes_pricer = black_scholes_pricer
        self.use_historical_chain = bool(use_historical_chain)
        self.fallback_to_black_scholes = bool(fallback_to_black_scholes)

        self.historical_service = HistoricalOptionPricingService(
            min_volume=min_volume,
            min_open_interest=min_open_interest,
            max_spread_pct=max_spread_pct,
        )

    def price(
        self,
        symbol,
        quote_date,
        option_type,
        underlying_price,
        strike,
        dte,
        risk_free_rate,
        volatility,
    ):
        if self.use_historical_chain:
            historical = self.historical_service.price(
                underlying_symbol=symbol,
                quote_date=quote_date,
                option_type=option_type,
                target_strike=strike,
                target_dte=dte,
            )

            if historical:
                return historical

            if not self.fallback_to_black_scholes:
                return None

        bs = self.black_scholes_pricer.price(
            option_type=option_type,
            underlying_price=underlying_price,
            strike=strike,
            dte=dte,
            risk_free_rate=risk_free_rate,
            volatility=volatility,
        )

        return {
            "source": "black_scholes_proxy",
            "option_symbol": "",
            "price": bs.price,
            "bid": 0.0,
            "ask": 0.0,
            "mid": bs.price,
            "last": bs.price,
            "strike": strike,
            "expiry": "BS_ENTRY_PROXY_EXIT",
            "volume": 0,
            "open_interest": 0,
            "implied_volatility": volatility,
            "delta": bs.delta,
            "gamma": bs.gamma,
            "theta": bs.theta,
            "vega": bs.vega,
            "rho": bs.rho,
            "spread_pct": 0.0,
        }
