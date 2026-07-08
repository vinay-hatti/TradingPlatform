from trading_ai.daily.models import DailyCandidate
from trading_ai.options.pricing_service import OptionPricingService


class DailyScanner:

    def __init__(
        self,
        market_service,
        feature_pipeline,
        live_profile,
        pricing_service=None,
        min_score=60.0,
        pricing_dte=30,
        start="2026-01-01",
        end="2026-06-01",
    ):
        self.market_service = market_service
        self.feature_pipeline = feature_pipeline
        self.live_profile = live_profile
        self.min_score = float(min_score)
        self.pricing_dte = int(pricing_dte)
        self.start = start
        self.end = end

        self.pricing = pricing_service or OptionPricingService(
            risk_free_rate=float(
                live_profile.get("risk_free_rate", 0.04)
            ),
            default_dte=self.pricing_dte,
        )

    def _load_market_data(self, symbol, period="6mo"):

        if hasattr(self.market_service, "get_price_history"):
            return self.market_service.get_price_history(
                symbol,
                period=period,
            )

        if hasattr(self.market_service, "get_history"):
            return self.market_service.get_history(
                symbol,
                period=period,
            )

        if hasattr(self.market_service, "load"):
            return self.market_service.load(
                symbol,
                period=period,
            )

        raise AttributeError(
            "Market data source does not support get_price_history/get_history/load"
        )

    def _latest_feature_row(self, symbol):

        df = self.market_service.get_price_history(
            symbol,
            self.start,
            self.end,
        )

        features = self.feature_pipeline.run(df)

        if features is None or len(features) == 0:
            return None

        return features.iloc[-1]


    def _choose_signal(self, row):

        call_score = float(row.get("call_score", 0.0) or 0.0)
        put_score = float(row.get("put_score", 0.0) or 0.0)

        if call_score < self.min_score and put_score < self.min_score:
            return None, 0.0

        if call_score >= put_score:
            return "CALL", call_score

        return "PUT", put_score

    def _passes_greek_filters(self, greeks):

        abs_delta = abs(float(greeks["delta"]))
        abs_theta = abs(float(greeks["theta"]))
        vega = float(greeks["vega"])

        min_delta = float(self.live_profile.get("min_delta", 0.0))
        max_delta = float(self.live_profile.get("max_delta", 1.0))
        min_vega = float(self.live_profile.get("min_vega", 0.0))
        max_vega = float(self.live_profile.get("max_vega", 999.0))
        max_theta = float(self.live_profile.get("max_theta", 999.0))

        if abs_delta < min_delta:
            return False

        if abs_delta > max_delta:
            return False

        if vega < min_vega:
            return False

        if vega > max_vega:
            return False

        if abs_theta > max_theta:
            return False

        return True

    def _final_score(self, signal_score, greeks):

        delta = abs(float(greeks["delta"]))
        vega = float(greeks["vega"])
        theta = abs(float(greeks["theta"]))

        delta_score = max(
            0.0,
            100.0 - abs(delta - 0.55) * 200.0,
        )

        vega_score = max(
            0.0,
            100.0 - abs(vega - 0.25) * 200.0,
        )

        theta_score = max(
            0.0,
            100.0 - theta * 1000.0,
        )

        return (
            signal_score * 0.55
            + delta_score * 0.20
            + vega_score * 0.15
            + theta_score * 0.10
        )

    def scan_symbol(self, symbol):

        row = self._latest_feature_row(symbol)

        if row is None:
            return None

        signal, score = self._choose_signal(row)

        if signal is None:
            return None

        close = float(row.get("close", 0.0) or 0.0)

        if close <= 0:
            return None

        hv20 = float(
            row.get(
                "hv20",
                row.get("iv", 0.30),
            )
            or 0.30
        )

        strike = close

        option_price = self.pricing.option_price(
            signal=signal,
            spot=close,
            strike=strike,
            hv20=hv20,
            dte=self.pricing_dte,
        )

        greeks = self.pricing.greeks(
            signal=signal,
            spot=close,
            strike=strike,
            hv20=hv20,
            dte=self.pricing_dte,
        )

        if not self._passes_greek_filters(greeks):
            return None

        final_score = self._final_score(
            score,
            greeks,
        )

        return DailyCandidate(
            symbol=symbol,
            signal=signal,
            strategy=(
                "LONG_CALL"
                if signal == "CALL"
                else "LONG_PUT"
            ),
            close=close,
            score=score,
            call_score=float(row.get("call_score", 0.0) or 0.0),
            put_score=float(row.get("put_score", 0.0) or 0.0),
            market_regime=str(row.get("market_regime", "")),
            strike=strike,
            expiry=f"{self.pricing_dte}DTE_PROXY",
            option_price=float(option_price),
            delta=float(greeks["delta"]),
            gamma=float(greeks["gamma"]),
            theta=float(greeks["theta"]),
            vega=float(greeks["vega"]),
            rho=float(greeks["rho"]),
            volatility=float(greeks["volatility"]),
            dte=int(greeks["dte"]),
            final_score=float(final_score),
        )

    def scan(self, symbols):

        candidates = []

        for symbol in symbols:
            try:
                candidate = self.scan_symbol(symbol)

                if candidate is not None:
                    candidates.append(candidate)

            except Exception as exc:
                print(f"Skipping {symbol}: {exc}")

        return sorted(
            candidates,
            key=lambda c: c.final_score,
            reverse=True,
        )
