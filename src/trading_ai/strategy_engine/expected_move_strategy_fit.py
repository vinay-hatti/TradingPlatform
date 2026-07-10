class ExpectedMoveStrategyFit:
    """
    Scores how well a strategy fits the expected-move environment.
    """

    LONG_PREMIUM = {
        "LONG_CALL",
        "LONG_PUT",
        "LONG_STRADDLE",
        "LONG_STRANGLE",
        "BULL_CALL_SPREAD",
        "BEAR_PUT_SPREAD",
    }

    SHORT_PREMIUM = {
        "SHORT_CALL",
        "SHORT_PUT",
        "BULL_PUT_SPREAD",
        "BEAR_CALL_SPREAD",
        "IRON_CONDOR",
        "IRON_BUTTERFLY",
    }

    def score(
        self,
        strategy: str,
        expected_move_profile,
    ) -> float:
        strategy = str(strategy or "").upper()

        move_regime = str(
            getattr(
                expected_move_profile,
                "move_regime",
                "NORMAL_MOVE",
            )
        ).upper()

        expansion_signal = str(
            getattr(
                expected_move_profile,
                "expansion_signal",
                "INSUFFICIENT_DATA",
            )
        ).upper()

        confidence = float(
            getattr(
                expected_move_profile,
                "confidence_score",
                0.0,
            )
            or 0.0
        )

        score = 60.0

        if strategy in self.LONG_PREMIUM:
            if move_regime in {
                "HIGH_MOVE",
                "EXTREME_MOVE",
            }:
                score += 20.0

            if (
                expansion_signal
                == "IMPLIED_MOVE_UNDERPRICED"
            ):
                score += 20.0

            if (
                expansion_signal
                == "IMPLIED_MOVE_OVERPRICED"
            ):
                score -= 25.0

        elif strategy in self.SHORT_PREMIUM:
            if move_regime in {
                "LOW_MOVE",
                "NORMAL_MOVE",
            }:
                score += 15.0

            if (
                expansion_signal
                == "IMPLIED_MOVE_OVERPRICED"
            ):
                score += 25.0

            if (
                expansion_signal
                == "IMPLIED_MOVE_UNDERPRICED"
            ):
                score -= 25.0

        if confidence < 50:
            score -= 15.0
        elif confidence >= 80:
            score += 5.0

        return round(
            max(0.0, min(100.0, score)),
            2,
        )

    def recommendation(
        self,
        expected_move_profile,
    ) -> str:
        signal = str(
            getattr(
                expected_move_profile,
                "expansion_signal",
                "",
            )
        ).upper()

        regime = str(
            getattr(
                expected_move_profile,
                "move_regime",
                "",
            )
        ).upper()

        if signal == "IMPLIED_MOVE_UNDERPRICED":
            return "FAVOR_LONG_PREMIUM"

        if signal == "IMPLIED_MOVE_OVERPRICED":
            return "FAVOR_SHORT_PREMIUM"

        if regime in {"HIGH_MOVE", "EXTREME_MOVE"}:
            return "FAVOR_DIRECTIONAL_OR_LONG_GAMMA"

        if regime == "LOW_MOVE":
            return "FAVOR_DEFINED_RISK_PREMIUM_SELLING"

        return "NEUTRAL_EXPECTED_MOVE"
