class StrikeScoring:
    def liquidity_score(
        self,
        volume: int,
        open_interest: int,
        spread_pct: float,
    ) -> float:
        volume = int(volume or 0)
        open_interest = int(open_interest or 0)
        spread_pct = float(spread_pct or 0.0)

        volume_score = min(volume / 1000.0, 1.0) * 35.0
        oi_score = min(open_interest / 2500.0, 1.0) * 35.0

        if spread_pct <= 0.05:
            spread_score = 30.0
        elif spread_pct <= 0.10:
            spread_score = 24.0
        elif spread_pct <= 0.20:
            spread_score = 16.0
        elif spread_pct <= 0.35:
            spread_score = 8.0
        else:
            spread_score = 0.0

        return round(volume_score + oi_score + spread_score, 2)

    def single_leg_greek_score(
        self,
        strategy: str,
        option_type: str,
        delta: float,
        gamma: float,
        theta: float,
        vega: float,
    ) -> float:
        strategy = str(strategy or "").upper()
        option_type = str(option_type or "").upper()

        delta_abs = abs(float(delta or 0.0))
        gamma = abs(float(gamma or 0.0))
        theta_abs = abs(float(theta or 0.0))
        vega = abs(float(vega or 0.0))

        score = 0.0

        if strategy in {"LONG_CALL", "LONG_PUT"}:
            if 0.45 <= delta_abs <= 0.65:
                score += 45
            elif 0.35 <= delta_abs <= 0.75:
                score += 32
            else:
                score += 15

            if gamma <= 0.08:
                score += 20
            elif gamma <= 0.15:
                score += 12
            else:
                score += 5

            if theta_abs <= 0.08:
                score += 20
            elif theta_abs <= 0.15:
                score += 12
            else:
                score += 4

            if vega >= 0.20:
                score += 15
            else:
                score += 8

        elif strategy in {"SHORT_PUT", "SHORT_CALL"}:
            if 0.15 <= delta_abs <= 0.35:
                score += 45
            elif 0.10 <= delta_abs <= 0.45:
                score += 30
            else:
                score += 12

            if theta_abs >= 0.03:
                score += 25
            else:
                score += 10

            if vega <= 0.50:
                score += 20
            else:
                score += 8

            if gamma <= 0.08:
                score += 10
            else:
                score += 4

        else:
            if 0.25 <= delta_abs <= 0.60:
                score += 50
            else:
                score += 25

            score += 25 if theta_abs <= 0.20 else 10
            score += 25 if vega <= 1.00 else 10

        return round(min(score, 100.0), 2)

    def moneyness_score(
        self,
        strategy: str,
        option_type: str,
        strike: float,
        underlying_price: float,
    ) -> float:
        strategy = str(strategy or "").upper()
        option_type = str(option_type or "").upper()

        strike = float(strike or 0.0)
        underlying_price = float(underlying_price or 0.0)

        if strike <= 0 or underlying_price <= 0:
            return 0.0

        distance = abs(strike - underlying_price) / underlying_price

        if strategy in {"LONG_CALL", "LONG_PUT"}:
            if distance <= 0.02:
                return 100.0
            if distance <= 0.05:
                return 85.0
            if distance <= 0.10:
                return 65.0
            return 35.0

        if strategy in {"SHORT_PUT", "SHORT_CALL"}:
            if 0.03 <= distance <= 0.12:
                return 100.0
            if 0.01 <= distance <= 0.18:
                return 75.0
            return 35.0

        if distance <= 0.08:
            return 85.0

        return 50.0

    def value_score(
        self,
        mid: float,
        intrinsic_value: float,
        extrinsic_value: float,
        implied_volatility: float,
    ) -> float:
        mid = float(mid or 0.0)
        intrinsic_value = float(intrinsic_value or 0.0)
        extrinsic_value = float(extrinsic_value or 0.0)
        implied_volatility = float(implied_volatility or 0.0)

        if mid <= 0:
            return 0.0

        extrinsic_ratio = extrinsic_value / mid if mid > 0 else 0.0

        score = 50.0

        if 0.25 <= extrinsic_ratio <= 0.90:
            score += 25.0
        elif extrinsic_ratio > 0.90:
            score += 10.0
        else:
            score += 5.0

        if 0.10 <= implied_volatility <= 0.80:
            score += 25.0
        elif implied_volatility > 0.80:
            score += 10.0

        return round(min(score, 100.0), 2)

    def risk_score(
        self,
        strategy: str,
        mid: float,
        underlying_price: float,
        max_spread_pct: float,
        spread_pct: float,
    ) -> float:
        mid = float(mid or 0.0)
        underlying_price = float(underlying_price or 0.0)
        max_spread_pct = float(max_spread_pct or 1.0)
        spread_pct = float(spread_pct or 0.0)

        score = 100.0

        if underlying_price > 0:
            premium_pct = mid / underlying_price

            if premium_pct > 0.10:
                score -= 20
            elif premium_pct > 0.05:
                score -= 10

        if spread_pct > max_spread_pct:
            score -= 40

        return round(max(0.0, min(100.0, score)), 2)
