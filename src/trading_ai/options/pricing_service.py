import math

from trading_ai.database.session import create_session
from trading_ai.options.repository import OptionChainRepository


class HistoricalOptionPricingService:
    """
    Historical option-chain lookup service.

    Ownership note:
    - HistoricalTradeGenerator uses this service for historical ENTRY selection.
    - OptionPricingService below intentionally does NOT use this service.
      OptionPricingService is kept as a pure Black-Scholes pricing engine.
    """

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

    def option_quote(self, *args, **kwargs):
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

    def option_price(self, *args, **kwargs):
        quote = self.option_quote(*args, **kwargs)
        if quote is None:
            return None
        return quote["price"]

    def passes_liquidity(self, contract):
        if contract.volume < self.min_volume:
            return False

        if contract.open_interest < self.min_open_interest:
            return False

        if contract.spread_pct > self.max_spread_pct:
            return False

        return True


class OptionPricingService:
    """
    Pure Black-Scholes option pricing engine.

    This class intentionally does not perform historical option-chain lookup.
    Historical entry lookup is owned by HistoricalTradeGenerator via
    HistoricalOptionPricingService.
    """

    def __init__(
        self,
        risk_free_rate=0.04,
        default_dte=30,
        **_deprecated_kwargs,
    ):
        # _deprecated_kwargs is accepted only to avoid breaking older callers.
        # Historical option flags are intentionally ignored here.
        self.risk_free_rate = float(risk_free_rate)
        self.default_dte = int(default_dte)

    def _norm_cdf(self, x):
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def _norm_pdf(self, x):
        return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

    def _extract_inputs(self, *args, **kwargs):
        option_type = (
            kwargs.get("option_type")
            or kwargs.get("signal")
        )

        underlying_price = (
            kwargs.get("underlying_price")
            or kwargs.get("spot")
            or kwargs.get("price")
        )

        strike = (
            kwargs.get("strike")
            or kwargs.get("target_strike")
        )

        volatility = (
            kwargs.get("volatility")
            or kwargs.get("hv20")
            or kwargs.get("implied_volatility")
            or kwargs.get("iv")
            or 0.30
        )

        dte = (
            kwargs.get("dte")
            or kwargs.get("target_dte")
            or kwargs.get("entry_dte")
            or kwargs.get("pricing_dte")
            or self.default_dte
        )

        # Positional compatibility:
        # option_type, underlying_price, strike, volatility, dte
        if args:
            if option_type is None and len(args) >= 1:
                option_type = args[0]
            if underlying_price is None and len(args) >= 2:
                underlying_price = args[1]
            if strike is None and len(args) >= 3:
                strike = args[2]
            if len(args) >= 4:
                volatility = args[3]
            if len(args) >= 5:
                dte = args[4]

        return option_type, underlying_price, strike, volatility, dte

    def _d1_d2(self, underlying_price, strike, volatility, dte=None):
        if (
            underlying_price is None
            or strike is None
            or volatility is None
        ):
            return None, None, None

        s = float(underlying_price)
        k = float(strike)
        sigma = float(volatility)
        r = self.risk_free_rate
        days = int(dte or self.default_dte)

        if s <= 0 or k <= 0 or sigma <= 0 or days <= 0:
            return None, None, None

        t = days / 365.0
        d1 = (
            math.log(s / k) + (r + 0.5 * sigma * sigma) * t
        ) / (sigma * math.sqrt(t))
        d2 = d1 - sigma * math.sqrt(t)

        return d1, d2, t

    def _price(self, option_type, underlying_price, strike, volatility, dte=None):
        d1, d2, t = self._d1_d2(
            underlying_price=underlying_price,
            strike=strike,
            volatility=volatility,
            dte=dte,
        )

        if d1 is None:
            return 0.0

        s = float(underlying_price)
        k = float(strike)
        r = self.risk_free_rate
        option_type = str(option_type).upper()

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
        option_type, underlying_price, strike, volatility, dte = self._extract_inputs(
            *args,
            **kwargs,
        )

        return self._price(
            option_type=option_type,
            underlying_price=underlying_price,
            strike=strike,
            volatility=volatility,
            dte=dte,
        )

    def greeks(self, *args, **kwargs):
        option_type, underlying_price, strike, volatility, dte = self._extract_inputs(
            *args,
            **kwargs,
        )

        d1, d2, t = self._d1_d2(
            underlying_price=underlying_price,
            strike=strike,
            volatility=volatility,
            dte=dte,
        )

        if d1 is None:
            return {
                "delta": 0.0,
                "gamma": 0.0,
                "theta": 0.0,
                "vega": 0.0,
                "rho": 0.0,
                "volatility": float(volatility or 0.0),
            }

        s = float(underlying_price)
        k = float(strike)
        sigma = float(volatility)
        r = self.risk_free_rate
        option_type = str(option_type).upper()

        pdf_d1 = self._norm_pdf(d1)
        gamma = pdf_d1 / (s * sigma * math.sqrt(t))
        vega = s * pdf_d1 * math.sqrt(t) / 100.0

        if option_type == "CALL":
            delta = self._norm_cdf(d1)
            theta = (
                -s * pdf_d1 * sigma / (2.0 * math.sqrt(t))
                - r * k * math.exp(-r * t) * self._norm_cdf(d2)
            ) / 365.0
            rho = k * t * math.exp(-r * t) * self._norm_cdf(d2) / 100.0
        else:
            delta = self._norm_cdf(d1) - 1.0
            theta = (
                -s * pdf_d1 * sigma / (2.0 * math.sqrt(t))
                + r * k * math.exp(-r * t) * self._norm_cdf(-d2)
            ) / 365.0
            rho = -k * t * math.exp(-r * t) * self._norm_cdf(-d2) / 100.0

        return {
            "delta": delta,
            "gamma": gamma,
            "theta": theta,
            "vega": vega,
            "rho": rho,
            "volatility": sigma,
        }

    def option_quote(self, *args, **kwargs):
        option_type, underlying_price, strike, volatility, dte = self._extract_inputs(
            *args,
            **kwargs,
        )

        price = self._price(
            option_type=option_type,
            underlying_price=underlying_price,
            strike=strike,
            volatility=volatility,
            dte=dte,
        )

        greek_values = self.greeks(
            option_type=option_type,
            underlying_price=underlying_price,
            strike=strike,
            volatility=volatility,
            dte=dte,
        )

        return {
            "source": "black_scholes_proxy",
            "option_symbol": "",
            "price": price,
            "bid": 0.0,
            "ask": 0.0,
            "mid": price,
            "last": price,
            "strike": strike,
            "expiry": "BS_ENTRY_PROXY_EXIT",
            "volume": 0,
            "open_interest": 0,
            "implied_volatility": volatility,
            "delta": greek_values["delta"],
            "gamma": greek_values["gamma"],
            "theta": greek_values["theta"],
            "vega": greek_values["vega"],
            "rho": greek_values["rho"],
            "spread_pct": 0.0,
        }
