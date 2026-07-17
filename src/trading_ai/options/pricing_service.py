from __future__ import annotations

import math


class OptionPricingService:
    def __init__(self, risk_free_rate=0.04, default_dte=30, **_deprecated):
        self.risk_free_rate = float(risk_free_rate)
        self.default_dte = int(default_dte)

    @staticmethod
    def _norm_cdf(x):
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    @staticmethod
    def _norm_pdf(x):
        return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

    def _extract_inputs(self, *args, **kwargs):
        option_type = kwargs.get("option_type") or kwargs.get("signal")
        spot = kwargs.get("underlying_price") or kwargs.get("spot") or kwargs.get("price")
        strike = kwargs.get("strike") or kwargs.get("target_strike")
        volatility = (
            kwargs.get("volatility") or kwargs.get("hv20")
            or kwargs.get("implied_volatility") or kwargs.get("iv") or 0.30
        )
        dte = (
            kwargs.get("dte") or kwargs.get("target_dte")
            or kwargs.get("entry_dte") or kwargs.get("pricing_dte")
            or self.default_dte
        )
        if args:
            if option_type is None and len(args) >= 1:
                option_type = args[0]
            if spot is None and len(args) >= 2:
                spot = args[1]
            if strike is None and len(args) >= 3:
                strike = args[2]
            if len(args) >= 4:
                volatility = args[3]
            if len(args) >= 5:
                dte = args[4]
        return option_type, spot, strike, float(volatility), int(dte)

    def _d1_d2(self, spot, strike, volatility, dte):
        if spot is None or strike is None:
            return None, None, None
        s, k, sigma, days = float(spot), float(strike), float(volatility), int(dte)
        if min(s, k, sigma, days) <= 0:
            return None, None, None
        t = days / 365.0
        d1 = (math.log(s / k) + (self.risk_free_rate + 0.5 * sigma * sigma) * t) / (sigma * math.sqrt(t))
        return d1, d1 - sigma * math.sqrt(t), t

    def _price(self, option_type, spot, strike, volatility, dte):
        d1, d2, t = self._d1_d2(spot, strike, volatility, dte)
        if d1 is None:
            return 0.0
        s, k, r = float(spot), float(strike), self.risk_free_rate
        if str(option_type).upper() == "CALL":
            return max(0.0, s * self._norm_cdf(d1) - k * math.exp(-r * t) * self._norm_cdf(d2))
        return max(0.0, k * math.exp(-r * t) * self._norm_cdf(-d2) - s * self._norm_cdf(-d1))

    def price_call(self, underlying_price, strike, volatility, dte=None):
        return self._price("CALL", underlying_price, strike, volatility, int(dte or self.default_dte))

    def price_put(self, underlying_price, strike, volatility, dte=None):
        return self._price("PUT", underlying_price, strike, volatility, int(dte or self.default_dte))

    def price(self, option_type, underlying_price, strike, volatility, dte=None):
        return self._price(option_type, underlying_price, strike, volatility, int(dte or self.default_dte))

    def option_price(self, *args, **kwargs):
        option_type, spot, strike, volatility, dte = self._extract_inputs(*args, **kwargs)
        return self._price(option_type, spot, strike, volatility, dte)

    def greeks(self, *args, **kwargs):
        option_type, spot, strike, volatility, dte = self._extract_inputs(*args, **kwargs)
        d1, d2, t = self._d1_d2(spot, strike, volatility, dte)
        if d1 is None:
            return {
                "delta": 0.0, "gamma": 0.0, "theta": 0.0,
                "vega": 0.0, "rho": 0.0,
                "volatility": float(volatility), "dte": int(dte),
            }
        s, k, sigma, r = float(spot), float(strike), float(volatility), self.risk_free_rate
        pdf = self._norm_pdf(d1)
        gamma = pdf / (s * sigma * math.sqrt(t))
        vega = s * pdf * math.sqrt(t) / 100.0
        if str(option_type).upper() == "CALL":
            delta = self._norm_cdf(d1)
            theta = (-s * pdf * sigma / (2 * math.sqrt(t)) - r * k * math.exp(-r * t) * self._norm_cdf(d2)) / 365.0
            rho = k * t * math.exp(-r * t) * self._norm_cdf(d2) / 100.0
        else:
            delta = self._norm_cdf(d1) - 1.0
            theta = (-s * pdf * sigma / (2 * math.sqrt(t)) + r * k * math.exp(-r * t) * self._norm_cdf(-d2)) / 365.0
            rho = -k * t * math.exp(-r * t) * self._norm_cdf(-d2) / 100.0
        return {
            "delta": delta, "gamma": gamma, "theta": theta,
            "vega": vega, "rho": rho,
            "volatility": sigma, "dte": int(dte),
        }

    def option_quote(self, *args, **kwargs):
        option_type, spot, strike, volatility, dte = self._extract_inputs(*args, **kwargs)
        price = self._price(option_type, spot, strike, volatility, dte)
        g = self.greeks(option_type=option_type, spot=spot, strike=strike, volatility=volatility, dte=dte)
        return {
            "source": "black_scholes_proxy", "option_symbol": "",
            "price": price, "bid": 0.0, "ask": 0.0, "mid": price, "last": price,
            "strike": strike, "expiry": f"{dte}DTE_PROXY",
            "volume": 0, "open_interest": 0,
            "implied_volatility": volatility,
            "delta": g["delta"], "gamma": g["gamma"], "theta": g["theta"],
            "vega": g["vega"], "rho": g["rho"], "spread_pct": 0.0,
            "dte": int(dte),
        }


class HistoricalOptionPricingService:
    def __init__(self, min_volume=0, min_open_interest=0, max_spread_pct=1.0):
        self.min_volume = int(min_volume)
        self.min_open_interest = int(min_open_interest)
        self.max_spread_pct = float(max_spread_pct)

    def _dependencies(self):
        from trading_ai.database.session import create_session
        from trading_ai.options.repository import OptionChainRepository
        return create_session, OptionChainRepository

    def find_contract(self, underlying_symbol, quote_date, option_type, target_strike, target_dte):
        create_session, repository_class = self._dependencies()
        session = create_session()
        try:
            contract = repository_class(session).find_nearest_contract(
                underlying_symbol=underlying_symbol,
                quote_date=quote_date,
                option_type=option_type,
                target_strike=target_strike,
                target_dte=target_dte,
            )
            return contract if contract and self.passes_liquidity(contract) else None
        finally:
            session.close()

    def price(self, underlying_symbol, quote_date, option_type, target_strike, target_dte):
        contract = self.find_contract(underlying_symbol, quote_date, option_type, target_strike, target_dte)
        if not contract:
            return None
        return {
            "source": "historical_chain",
            "option_symbol": contract.option_symbol,
            "price": contract.mid if contract.mid > 0 else contract.last,
            "bid": contract.bid, "ask": contract.ask, "mid": contract.mid,
            "last": contract.last, "strike": contract.strike,
            "expiry": contract.expiry, "volume": contract.volume,
            "open_interest": contract.open_interest,
            "implied_volatility": contract.implied_volatility,
            "delta": contract.delta, "gamma": contract.gamma,
            "theta": contract.theta, "vega": contract.vega,
            "rho": contract.rho, "spread_pct": contract.spread_pct,
            "dte": int(target_dte),
        }

    def option_quote(self, *args, **kwargs):
        symbol = kwargs.get("underlying_symbol") or kwargs.get("symbol")
        quote_date = kwargs.get("quote_date") or kwargs.get("date") or kwargs.get("entry_date")
        option_type = kwargs.get("option_type") or kwargs.get("signal")
        strike = kwargs.get("target_strike") or kwargs.get("strike")
        dte = kwargs.get("target_dte") or kwargs.get("dte") or kwargs.get("entry_dte") or kwargs.get("pricing_dte")
        if args:
            if symbol is None and len(args) >= 1: symbol = args[0]
            if quote_date is None and len(args) >= 2: quote_date = args[1]
            if option_type is None and len(args) >= 3: option_type = args[2]
            if strike is None and len(args) >= 5: strike = args[4]
            if dte is None and len(args) >= 6: dte = args[5]
        if None in (symbol, quote_date, option_type, strike, dte):
            return None
        return self.price(symbol, quote_date, option_type, strike, dte)

    def option_price(self, *args, **kwargs):
        quote = self.option_quote(*args, **kwargs)
        return None if quote is None else quote["price"]

    def passes_liquidity(self, contract):
        return (
            contract.volume >= self.min_volume
            and contract.open_interest >= self.min_open_interest
            and contract.spread_pct <= self.max_spread_pct
        )
