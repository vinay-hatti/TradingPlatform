class AITradeRanker:

    def __init__(
        self,
        technical_weight=0.40,
        greeks_weight=0.25,
        regime_weight=0.15,
        volatility_weight=0.10,
        risk_weight=0.10,
    ):
        self.technical_weight = float(technical_weight)
        self.greeks_weight = float(greeks_weight)
        self.regime_weight = float(regime_weight)
        self.volatility_weight = float(volatility_weight)
        self.risk_weight = float(risk_weight)

    def _clamp(self, value, low=0.0, high=100.0):
        return max(low, min(float(value), high))

    def technical_score(self, signal_score):
        return self._clamp(signal_score)

    def greeks_score(
        self,
        delta,
        theta,
        vega,
    ):
        abs_delta = abs(float(delta))
        abs_theta = abs(float(theta))
        vega = float(vega)

        delta_score = max(
            0.0,
            100.0 - abs(abs_delta - 0.55) * 250.0,
        )

        theta_score = max(
            0.0,
            100.0 - abs_theta * 900.0,
        )

        vega_score = max(
            0.0,
            100.0 - abs(vega - 0.25) * 250.0,
        )

        return self._clamp(
            delta_score * 0.45
            + theta_score * 0.25
            + vega_score * 0.30
        )

    def regime_score(
        self,
        signal,
        market_regime,
    ):
        signal = str(signal).upper()
        regime = str(market_regime).upper()

        if signal == "CALL":
            if "BULL" in regime:
                return 100.0
            if "CHOP" in regime:
                return 60.0
            if "BEAR" in regime:
                return 20.0

        if signal == "PUT":
            if "BEAR" in regime:
                return 100.0
            if "CHOP" in regime:
                return 60.0
            if "BULL" in regime:
                return 20.0

        return 50.0

    def volatility_score(
        self,
        volatility,
    ):
        volatility = float(volatility)

        # Preferred range for this current system:
        # 10% to 45% annualized volatility.
        if volatility < 0.10:
            return 40.0

        if volatility <= 0.45:
            return 100.0

        if volatility <= 0.75:
            return 70.0

        return 40.0

    def risk_score(
        self,
        portfolio_penalty,
    ):
        penalty = float(portfolio_penalty)

        return self._clamp(
            100.0 - penalty,
        )

    def score(
        self,
        signal_score,
        signal,
        market_regime,
        delta,
        theta,
        vega,
        volatility,
        portfolio_penalty=0.0,
    ):
        technical = self.technical_score(signal_score)

        greeks = self.greeks_score(
            delta=delta,
            theta=theta,
            vega=vega,
        )

        regime = self.regime_score(
            signal=signal,
            market_regime=market_regime,
        )

        vol = self.volatility_score(
            volatility=volatility,
        )

        risk = self.risk_score(
            portfolio_penalty=portfolio_penalty,
        )

        total = (
            technical * self.technical_weight
            + greeks * self.greeks_weight
            + regime * self.regime_weight
            + vol * self.volatility_weight
            + risk * self.risk_weight
        )

        reasons = []

        reasons.append(f"Technical={technical:.1f}")
        reasons.append(f"Greeks={greeks:.1f}")
        reasons.append(f"Regime={regime:.1f}")
        reasons.append(f"Volatility={vol:.1f}")
        reasons.append(f"Risk={risk:.1f}")

        if regime >= 90:
            reasons.append("Signal aligned with market regime.")

        if greeks >= 80:
            reasons.append("Greeks are in preferred range.")

        if risk < 90:
            reasons.append("Portfolio exposure penalty applied.")

        return {
            "ai_score": self._clamp(total),
            "technical_score": technical,
            "greeks_score": greeks,
            "regime_score": regime,
            "volatility_score": vol,
            "risk_score": risk,
            "ranking_reason": " | ".join(reasons),
        }
