from trading_ai.options.pricing import BlackScholesPricingEngine


class OptionPricingService:

    def __init__(
        self,
        risk_free_rate=0.04,
        default_dte=30,
        min_volatility=0.10,
        max_volatility=1.50,
    ):
        self.engine = BlackScholesPricingEngine(
            risk_free_rate=risk_free_rate,
        )

        self.default_dte = int(default_dte)
        self.min_volatility = float(min_volatility)
        self.max_volatility = float(max_volatility)

    def _volatility(self, hv20):

        try:
            vol = float(hv20)
        except Exception:
            vol = self.min_volatility

        if vol <= 0:
            vol = self.min_volatility

        # If volatility is accidentally passed as percent, convert it.
        if vol > 2.0:
            vol = vol / 100.0

        return max(
            self.min_volatility,
            min(vol, self.max_volatility),
        )

    def option_price(
        self,
        signal,
        spot,
        strike=None,
        hv20=0.30,
        dte=None,
    ):
        signal = str(signal).upper()

        spot = float(spot)

        if strike is None:
            strike = spot

        strike = float(strike)

        dte = self.default_dte if dte is None else int(dte)

        volatility = self._volatility(hv20)

        return self.engine.price(
            option_type=signal,
            spot=spot,
            strike=strike,
            volatility=volatility,
            days_to_expiry=dte,
        )

    def greeks(
        self,
        signal,
        spot,
        strike=None,
        hv20=0.30,
        dte=None,
    ):
        signal = str(signal).upper()

        spot = float(spot)

        if strike is None:
            strike = spot

        strike = float(strike)

        dte = self.default_dte if dte is None else int(dte)

        volatility = self._volatility(hv20)

        return {
            "delta": self.engine.delta(
                signal,
                spot,
                strike,
                volatility,
                dte,
            ),
            "gamma": self.engine.gamma(
                spot,
                strike,
                volatility,
                dte,
            ),
            "theta": self.engine.theta(
                signal,
                spot,
                strike,
                volatility,
                dte,
            ),
            "vega": self.engine.vega(
                spot,
                strike,
                volatility,
                dte,
            ),
            "rho": self.engine.rho(
                signal,
                spot,
                strike,
                volatility,
                dte,
            ),
            "volatility": volatility,
            "dte": dte,
        }
