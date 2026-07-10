import math

from trading_ai.database.session import create_session
from trading_ai.options.repository import OptionChainRepository


class HistoricalOptionPricingService:
    def __init__(
        self,
        min_volume=0,
        min_open_interest=0,
        max_spread_pct=1.0,
    ):
        self.min_volume = int(min_volume)
        self.min_open_interest = int(min_open_interest)
        self.max_spread_pct = float(max_spread_pct)

    def find_contract(
        self,
        underlying_symbol,
        quote_date,
        option_type,
        target_strike,
        target_dte,
    ):
        session = create_session()

        try:
            repo = OptionChainRepository(session)

            contract = repo.find_nearest_contract(
                underlying_symbol=underlying_symbol,
                quote_date=quote_date,
                option_type=option_type,
                target_strike=target_strike,
                target_dte=target_dte,
            )

            if not contract:
                return None

            if not self.passes_liquidity(contract):
                return None

            return contract

        finally:
            session.close()

    def price(
        self,
        underlying_symbol,
        quote_date,
        option_type,
        target_strike,
        target_dte,
    ):
        contract = self.find_contract(
            underlying_symbol=underlying_symbol,
            quote_date=quote_date,
            option_type=option_type,
            target_strike=target_strike,
            target_dte=target_dte,
        )

        if not contract:
            return None

        return {
            "source": "historical_chain",
            "option_symbol": contract.option_symbol,
            "price": contract.mid if contract.mid > 0 else contract.last,
            "bid": contract.bid,
            "ask": contract.ask,
            "mid": contract.mid,
            "last": contract.last,
            "strike": contract.strike,
            "expiry": contract.expiry,
            "volume": contract.volume,
            "open_interest": contract.open_interest,
            "implied_volatility": contract.implied_volatility,
            "delta": contract.delta,
            "gamma": contract.gamma,
            "theta": contract.theta,
            "vega": contract.vega,
            "rho": contract.rho,
            "spread_pct": contract.spread_pct,
        }

    def option_price(self, *args, **kwargs):
        """
        Compatibility wrapper.

        Supports BOTH calling styles:

            option_price(
                signal="CALL",
                spot=150,
                strike=150,
                hv20=0.30,
                dte=30,
            )

        and

            option_price(
                option_type="CALL",
                underlying_price=150,
                strike=150,
                volatility=0.30,
                dte=30,
            )
        """

        option_type = (
            kwargs.get("option_type")
            or kwargs.get("signal")
        )

        underlying_price = (
            kwargs.get("underlying_price")
            or kwargs.get("spot")
            or kwargs.get("price")
        )

        strike = kwargs.get("strike")

        volatility = (
            kwargs.get("volatility")
            or kwargs.get("hv20")
            or kwargs.get("implied_volatility")
            or 0.30
        )

        dte = (
            kwargs.get("dte")
            or self.default_dte
        )

        return self._price(
            option_type=option_type,
            underlying_price=underlying_price,
            strike=strike,
            volatility=volatility,
            dte=dte,
        )


        if result is None:
            return None

        return result["price"]

    def option_quote(self, *args, **kwargs):
        """
        Returns full historical option quote metadata.
        Useful for future trade metadata wiring.
        """

        underlying_symbol = (
            kwargs.get("underlying_symbol")
            or kwargs.get("symbol")
        )

        quote_date = (
            kwargs.get("quote_date")
            or kwargs.get("date")
            or kwargs.get("entry_date")
        )

        option_type = (
            kwargs.get("option_type")
            or kwargs.get("signal")
        )

        target_strike = (
            kwargs.get("target_strike")
            or kwargs.get("strike")
        )

        target_dte = (
            kwargs.get("target_dte")
            or kwargs.get("dte")
            or kwargs.get("entry_dte")
            or kwargs.get("pricing_dte")
        )

        if args:
            if underlying_symbol is None and len(args) >= 1:
                underlying_symbol = args[0]
            if quote_date is None and len(args) >= 2:
                quote_date = args[1]
            if option_type is None and len(args) >= 3:
                option_type = args[2]
            if target_strike is None and len(args) >= 5:
                target_strike = args[4]
            if target_dte is None and len(args) >= 6:
                target_dte = args[5]

        if (
            underlying_symbol is None
            or quote_date is None
            or option_type is None
            or target_strike is None
            or target_dte is None
        ):
            return None

        return self.price(
            underlying_symbol=underlying_symbol,
            quote_date=quote_date,
            option_type=option_type,
            target_strike=target_strike,
            target_dte=target_dte,
        )

    def passes_liquidity(self, contract):
        if contract.volume < self.min_volume:
            return False

        if contract.open_interest < self.min_open_interest:
            return False

        if contract.spread_pct > self.max_spread_pct:
            return False

        return True


class OptionPricingService:
    def __init__(
        self,
        risk_free_rate=0.04,
        default_dte=30,
        use_historical_options=False,
        fallback_to_black_scholes=True,
        min_option_volume=0,
        min_open_interest=0,
        max_spread_pct=1.0,
    ):
        self.risk_free_rate = float(risk_free_rate)
        self.default_dte = int(default_dte)

        self.use_historical_options = bool(use_historical_options)
        self.fallback_to_black_scholes = bool(fallback_to_black_scholes)

        self.historical = HistoricalOptionPricingService(
            min_volume=min_option_volume,
            min_open_interest=min_open_interest,
            max_spread_pct=max_spread_pct,
        )

    def _norm_cdf(self, x):
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def _price(self, option_type, underlying_price, strike, volatility, dte=None):
        s = float(underlying_price)
        k = float(strike)
        sigma = float(volatility)
        r = self.risk_free_rate
        days = int(dte or self.default_dte)

        if s <= 0 or k <= 0 or sigma <= 0 or days <= 0:
            return 0.0

        t = days / 365.0

        d1 = (
            math.log(s / k) + (r + 0.5 * sigma * sigma) * t
        ) / (sigma * math.sqrt(t))
        d2 = d1 - sigma * math.sqrt(t)

        option_type = option_type.upper()

        if option_type == "CALL":
            return max(
                0.0,
                s * self._norm_cdf(d1)
                - k * math.exp(-r * t) * self._norm_cdf(d2),
            )

        return max(
            0.0,
            k * math.exp(-r * t) * self._norm_cdf(-d2)
            - s * self._norm_cdf(-d1),
        )

    def price_call(self, underlying_price, strike, volatility, dte=None):
        return self._price(
            "CALL",
            underlying_price=underlying_price,
            strike=strike,
            volatility=volatility,
            dte=dte,
        )

    def price_put(self, underlying_price, strike, volatility, dte=None):
        return self._price(
            "PUT",
            underlying_price=underlying_price,
            strike=strike,
            volatility=volatility,
            dte=dte,
        )

    def price(self, option_type, underlying_price, strike, volatility, dte=None):
        return self._price(
            option_type=option_type,
            underlying_price=underlying_price,
            strike=strike,
            volatility=volatility,
            dte=dte,
        )

    def option_price(self, *args, **kwargs):
        """
        Compatibility method used by trade_generator.py.

        If historical options are enabled, try historical chain first.
        If not found and fallback is allowed, use Black-Scholes proxy.
        """

        option_type = (
            kwargs.get("option_type")
            or kwargs.get("signal")
        )

        underlying_price = (
            kwargs.get("underlying_price")
            or kwargs.get("price")
        )

        strike = (
            kwargs.get("strike")
            or kwargs.get("target_strike")
        )

        volatility = (
            kwargs.get("volatility")
            or kwargs.get("implied_volatility")
            or 0.10
        )

        dte = (
            kwargs.get("dte")
            or kwargs.get("target_dte")
            or kwargs.get("entry_dte")
            or kwargs.get("pricing_dte")
            or self.default_dte
        )

        symbol = (
            kwargs.get("symbol")
            or kwargs.get("underlying_symbol")
        )

        quote_date = (
            kwargs.get("quote_date")
            or kwargs.get("date")
            or kwargs.get("entry_date")
        )

        # Positional fallback support.
        # Common old style may be:
        # option_type, underlying_price, strike, volatility, dte
        if args:
            if option_type is None and len(args) >= 1:
                option_type = args[0]
            if underlying_price is None and len(args) >= 2:
                underlying_price = args[1]
            if strike is None and len(args) >= 3:
                strike = args[2]
            if volatility in (None, 0.10) and len(args) >= 4:
                volatility = args[3]
            if dte is None and len(args) >= 5:
                dte = args[4]

        if self.use_historical_options and symbol and quote_date:
            historical = self.historical.option_quote(
                underlying_symbol=symbol,
                quote_date=quote_date,
                option_type=option_type,
                target_strike=strike,
                target_dte=dte,
            )

            if historical is not None:
                return historical["price"]

            if not self.fallback_to_black_scholes:
                return None

        return self._price(
            option_type=option_type,
            underlying_price=underlying_price,
            strike=strike,
            volatility=volatility,
            dte=dte,
        )

    def option_quote(self, *args, **kwargs):
        """
        Returns full quote metadata when historical data is available.
        Falls back to synthetic BS metadata when allowed.
        """

        option_type = (
            kwargs.get("option_type")
            or kwargs.get("signal")
        )

        underlying_price = (
            kwargs.get("underlying_price")
            or kwargs.get("price")
        )

        strike = (
            kwargs.get("strike")
            or kwargs.get("target_strike")
        )

        volatility = (
            kwargs.get("volatility")
            or kwargs.get("implied_volatility")
            or 0.10
        )

        dte = (
            kwargs.get("dte")
            or kwargs.get("target_dte")
            or kwargs.get("entry_dte")
            or kwargs.get("pricing_dte")
            or self.default_dte
        )

        symbol = (
            kwargs.get("symbol")
            or kwargs.get("underlying_symbol")
        )

        quote_date = (
            kwargs.get("quote_date")
            or kwargs.get("date")
            or kwargs.get("entry_date")
        )

        if self.use_historical_options and symbol and quote_date:
            historical = self.historical.option_quote(
                underlying_symbol=symbol,
                quote_date=quote_date,
                option_type=option_type,
                target_strike=strike,
                target_dte=dte,
            )

            if historical is not None:
                return historical

            if not self.fallback_to_black_scholes:
                return None

        bs_price = self._price(
            option_type=option_type,
            underlying_price=underlying_price,
            strike=strike,
            volatility=volatility,
            dte=dte,
        )

        return {
            "source": "black_scholes_proxy",
            "option_symbol": "",
            "price": bs_price,
            "bid": 0.0,
            "ask": 0.0,
            "mid": bs_price,
            "last": bs_price,
            "strike": strike,
            "expiry": "BS_ENTRY_PROXY_EXIT",
            "volume": 0,
            "open_interest": 0,
            "implied_volatility": volatility,
            "delta": 0.0,
            "gamma": 0.0,
            "theta": 0.0,
            "vega": 0.0,
            "rho": 0.0,
            "spread_pct": 0.0,
        }
