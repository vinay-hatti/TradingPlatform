class ExpirationScoring:
    def dte_score(self, strategy: str, dte: int) -> float:
        strategy = str(strategy or "").upper()
        dte = int(dte or 0)

        if dte <= 0:
            return 0.0

        if strategy in {"LONG_CALL", "LONG_PUT"}:
            return self._score_ranges(dte, [
                ((21, 45), 100),
                ((14, 60), 85),
                ((7, 90), 65),
            ])

        if strategy in {"BULL_CALL_SPREAD", "BEAR_PUT_SPREAD"}:
            return self._score_ranges(dte, [
                ((21, 60), 100),
                ((14, 75), 85),
                ((7, 90), 65),
            ])

        if strategy in {"BULL_PUT_SPREAD", "BEAR_CALL_SPREAD"}:
            return self._score_ranges(dte, [
                ((21, 45), 100),
                ((14, 60), 85),
                ((7, 75), 65),
            ])

        if strategy in {"IRON_CONDOR", "IRON_BUTTERFLY"}:
            return self._score_ranges(dte, [
                ((21, 45), 100),
                ((14, 60), 85),
                ((7, 75), 65),
            ])

        if strategy in {"LONG_STRADDLE", "LONG_STRANGLE"}:
            return self._score_ranges(dte, [
                ((14, 45), 100),
                ((7, 60), 85),
                ((1, 90), 60),
            ])

        return self._score_ranges(dte, [
            ((21, 60), 100),
            ((14, 90), 75),
        ])

    def liquidity_score(
        self,
        avg_volume: float,
        avg_open_interest: float,
        avg_spread_pct: float,
        contracts_available: int,
    ) -> float:
        avg_volume = float(avg_volume or 0.0)
        avg_open_interest = float(avg_open_interest or 0.0)
        avg_spread_pct = float(avg_spread_pct or 1.0)
        contracts_available = int(contracts_available or 0)

        volume_score = min(avg_volume / 500.0, 1.0) * 30.0
        oi_score = min(avg_open_interest / 1500.0, 1.0) * 30.0
        depth_score = min(contracts_available / 20.0, 1.0) * 15.0

        if avg_spread_pct <= 0.05:
            spread_score = 25.0
        elif avg_spread_pct <= 0.10:
            spread_score = 20.0
        elif avg_spread_pct <= 0.20:
            spread_score = 12.0
        elif avg_spread_pct <= 0.35:
            spread_score = 6.0
        else:
            spread_score = 0.0

        return round(volume_score + oi_score + depth_score + spread_score, 2)

    def theta_score(self, strategy: str, dte: int, avg_abs_theta: float) -> float:
        strategy = str(strategy or "").upper()
        dte = int(dte or 0)
        avg_abs_theta = float(avg_abs_theta or 0.0)

        if strategy in {
            "BULL_PUT_SPREAD",
            "BEAR_CALL_SPREAD",
            "IRON_CONDOR",
            "IRON_BUTTERFLY",
            "SHORT_PUT",
            "SHORT_CALL",
        }:
            score = 50.0

            if 14 <= dte <= 45:
                score += 30.0
            elif 7 <= dte <= 60:
                score += 20.0

            if avg_abs_theta >= 0.03:
                score += 20.0
            else:
                score += 8.0

            return round(min(score, 100.0), 2)

        if strategy in {
            "LONG_CALL",
            "LONG_PUT",
            "LONG_STRADDLE",
            "LONG_STRANGLE",
            "BULL_CALL_SPREAD",
            "BEAR_PUT_SPREAD",
        }:
            score = 100.0

            if dte < 14:
                score -= 25.0

            if avg_abs_theta > 0.12:
                score -= 25.0
            elif avg_abs_theta > 0.08:
                score -= 10.0

            return round(max(0.0, min(100.0, score)), 2)

        return 70.0

    def volatility_score(self, strategy: str, avg_iv: float, volatility_profile=None) -> float:
        strategy = str(strategy or "").upper()
        avg_iv = float(avg_iv or 0.0)

        vol_regime = (
            str(getattr(volatility_profile, "volatility_regime", "") or "")
            if volatility_profile is not None
            else ""
        )

        score = 70.0

        if strategy in {
            "BULL_PUT_SPREAD",
            "BEAR_CALL_SPREAD",
            "IRON_CONDOR",
            "IRON_BUTTERFLY",
            "SHORT_PUT",
            "SHORT_CALL",
        }:
            if vol_regime in {"HIGH_VOL", "EXTREME_HIGH_VOL"}:
                score += 20.0

            if avg_iv >= 0.30:
                score += 10.0

        elif strategy in {
            "LONG_CALL",
            "LONG_PUT",
            "LONG_STRADDLE",
            "LONG_STRANGLE",
        }:
            if vol_regime in {"LOW_VOL", "NORMAL_VOL"}:
                score += 20.0

            if avg_iv <= 0.45:
                score += 10.0

        return round(max(0.0, min(100.0, score)), 2)

    def expected_move_score(
        self,
        strategy: str,
        expected_move_pct: float,
    ) -> float:
        strategy = str(strategy or "").upper()
        expected_move_pct = float(expected_move_pct or 0.0)

        if expected_move_pct <= 0:
            return 0.0

        if strategy in {"LONG_CALL", "LONG_PUT", "LONG_STRADDLE", "LONG_STRANGLE"}:
            if expected_move_pct >= 0.08:
                return 100.0
            if expected_move_pct >= 0.05:
                return 85.0
            if expected_move_pct >= 0.03:
                return 70.0
            return 45.0

        if strategy in {
            "BULL_PUT_SPREAD",
            "BEAR_CALL_SPREAD",
            "IRON_CONDOR",
            "IRON_BUTTERFLY",
        }:
            if 0.02 <= expected_move_pct <= 0.08:
                return 100.0
            if expected_move_pct <= 0.12:
                return 75.0
            return 45.0

        return 70.0

    def _score_ranges(self, dte: int, ranges: list[tuple[tuple[int, int], float]]) -> float:
        for (low, high), score in ranges:
            if low <= dte <= high:
                return float(score)

        if dte < 7:
            return 35.0

        if dte > 120:
            return 30.0

        return 50.0
