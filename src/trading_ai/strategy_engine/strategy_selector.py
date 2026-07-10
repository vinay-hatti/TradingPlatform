from trading_ai.strategy_engine.strategy_candidate import StrategyCandidate
from trading_ai.strategy_engine.expected_move_strategy_fit import (
    ExpectedMoveStrategyFit,
)


class StrategySelector:
    """
    Institutional rule-based options strategy selector.

    Inputs:
      - direction: CALL / PUT / NEUTRAL
      - market_regime: BULL_TREND / BEAR_TREND / SIDEWAYS / UNKNOWN
      - volatility profile from Phase 1

    Output:
      - ranked list of StrategyCandidate objects
    """

    def __init__(self):
        self.expected_move_fit = ExpectedMoveStrategyFit()

    def select(
        self,
        symbol: str,
        direction: str,
        market_regime: str,
        volatility_profile,
        expected_move_profile=None,
    ) -> list[StrategyCandidate]:
        direction = str(direction or "NEUTRAL").upper()
        market_regime = str(market_regime or "UNKNOWN").upper()
        vol_regime = str(volatility_profile.volatility_regime or "NORMAL_VOL")
        vol_signal = str(volatility_profile.volatility_signal or "NEUTRAL_VOL")

        if expected_move_profile is not None:
            for candidate in candidates:
                expected_move_score = (
                    self.expected_move_fit.score(
                        strategy=candidate.strategy,
                        expected_move_profile=(
                            expected_move_profile
                        ),
                    )
                )

                candidate.score = round(
                    candidate.score * 0.80
                    + expected_move_score * 0.20,
                    2,
                )

                setattr(
                    candidate,
                    "expected_move_score",
                    expected_move_score,
                )

                setattr(
                    candidate,
                    "expected_move_recommendation",
                    self.expected_move_fit.recommendation(
                        expected_move_profile
                    ),
                )

        candidates = []

        if direction == "CALL":
            candidates.extend(
                self._bullish_candidates(
                    symbol=symbol,
                    market_regime=market_regime,
                    vol_regime=vol_regime,
                    vol_signal=vol_signal,
                    volatility_profile=volatility_profile,
                )
            )

        elif direction == "PUT":
            candidates.extend(
                self._bearish_candidates(
                    symbol=symbol,
                    market_regime=market_regime,
                    vol_regime=vol_regime,
                    vol_signal=vol_signal,
                    volatility_profile=volatility_profile,
                )
            )

        else:
            candidates.extend(
                self._neutral_candidates(
                    symbol=symbol,
                    market_regime=market_regime,
                    vol_regime=vol_regime,
                    vol_signal=vol_signal,
                    volatility_profile=volatility_profile,
                )
            )

        candidates = self._apply_common_warnings(candidates, volatility_profile)
        candidates.sort(key=lambda c: c.score, reverse=True)

        return candidates


    def best(
        self,
        symbol: str,
        direction: str,
        market_regime: str,
        volatility_profile,
        expected_move_profile=None,
    ) -> StrategyCandidate | None:
        candidates = self.select(
            symbol=symbol,
            direction=direction,
            market_regime=market_regime,
            volatility_profile=volatility_profile,
            expected_move_profile=(
                expected_move_profile
            ),
        )

        return candidates[0] if candidates else None


    def _bullish_candidates(
        self,
        symbol,
        market_regime,
        vol_regime,
        vol_signal,
        volatility_profile,
    ):
        iv_rank = float(volatility_profile.iv_rank or 0.0)
        iv_hv_ratio = float(volatility_profile.iv_hv_ratio or 0.0)

        candidates = []

        if vol_regime in {"LOW_VOL", "NORMAL_VOL"}:
            candidates.append(
                StrategyCandidate(
                    symbol=symbol,
                    direction="CALL",
                    strategy="LONG_CALL",
                    volatility_regime=vol_regime,
                    volatility_signal=vol_signal,
                    market_regime=market_regime,
                    score=self._score(82, iv_rank, market_regime, preferred="BULL_TREND"),
                    confidence=volatility_profile.confidence,
                    reason="Bullish signal with low/normal volatility favors long premium.",
                    risk_profile="DEFINED_RISK",
                    premium_type="DEBIT",
                )
            )

            candidates.append(
                StrategyCandidate(
                    symbol=symbol,
                    direction="CALL",
                    strategy="BULL_CALL_SPREAD",
                    volatility_regime=vol_regime,
                    volatility_signal=vol_signal,
                    market_regime=market_regime,
                    score=self._score(78, iv_rank, market_regime, preferred="BULL_TREND"),
                    confidence=volatility_profile.confidence,
                    reason="Bullish signal with controlled debit exposure.",
                    risk_profile="DEFINED_RISK",
                    premium_type="DEBIT",
                )
            )

        if vol_regime in {"HIGH_VOL", "EXTREME_HIGH_VOL"}:
            candidates.append(
                StrategyCandidate(
                    symbol=symbol,
                    direction="CALL",
                    strategy="BULL_PUT_SPREAD",
                    volatility_regime=vol_regime,
                    volatility_signal=vol_signal,
                    market_regime=market_regime,
                    score=self._score(86, iv_rank, market_regime, preferred="BULL_TREND"),
                    confidence=volatility_profile.confidence,
                    reason="Bullish signal with elevated IV favors credit collection.",
                    risk_profile="DEFINED_RISK",
                    premium_type="CREDIT",
                )
            )

            candidates.append(
                StrategyCandidate(
                    symbol=symbol,
                    direction="CALL",
                    strategy="SHORT_PUT",
                    volatility_regime=vol_regime,
                    volatility_signal=vol_signal,
                    market_regime=market_regime,
                    score=self._score(72, iv_rank, market_regime, preferred="BULL_TREND"),
                    confidence=volatility_profile.confidence,
                    reason="High IV bullish setup; undefined risk strategy requires strict limits.",
                    risk_profile="UNDEFINED_RISK",
                    premium_type="CREDIT",
                    warnings=["Undefined downside risk"],
                )
            )

        if iv_hv_ratio >= 1.75:
            candidates.append(
                StrategyCandidate(
                    symbol=symbol,
                    direction="CALL",
                    strategy="PUT_RATIO_SPREAD",
                    volatility_regime=vol_regime,
                    volatility_signal=vol_signal,
                    market_regime=market_regime,
                    score=self._score(65, iv_rank, market_regime, preferred="BULL_TREND"),
                    confidence=volatility_profile.confidence,
                    reason="Very elevated IV may support advanced premium structure.",
                    risk_profile="COMPLEX",
                    premium_type="MIXED",
                    warnings=["Complex payoff", "Requires advanced risk controls"],
                )
            )

        return candidates

    def _bearish_candidates(
        self,
        symbol,
        market_regime,
        vol_regime,
        vol_signal,
        volatility_profile,
    ):
        iv_rank = float(volatility_profile.iv_rank or 0.0)
        candidates = []

        if vol_regime in {"LOW_VOL", "NORMAL_VOL"}:
            candidates.append(
                StrategyCandidate(
                    symbol=symbol,
                    direction="PUT",
                    strategy="LONG_PUT",
                    volatility_regime=vol_regime,
                    volatility_signal=vol_signal,
                    market_regime=market_regime,
                    score=self._score(82, iv_rank, market_regime, preferred="BEAR_TREND"),
                    confidence=volatility_profile.confidence,
                    reason="Bearish signal with low/normal volatility favors long premium.",
                    risk_profile="DEFINED_RISK",
                    premium_type="DEBIT",
                )
            )

            candidates.append(
                StrategyCandidate(
                    symbol=symbol,
                    direction="PUT",
                    strategy="BEAR_PUT_SPREAD",
                    volatility_regime=vol_regime,
                    volatility_signal=vol_signal,
                    market_regime=market_regime,
                    score=self._score(78, iv_rank, market_regime, preferred="BEAR_TREND"),
                    confidence=volatility_profile.confidence,
                    reason="Bearish signal with defined debit risk.",
                    risk_profile="DEFINED_RISK",
                    premium_type="DEBIT",
                )
            )

        if vol_regime in {"HIGH_VOL", "EXTREME_HIGH_VOL"}:
            candidates.append(
                StrategyCandidate(
                    symbol=symbol,
                    direction="PUT",
                    strategy="BEAR_CALL_SPREAD",
                    volatility_regime=vol_regime,
                    volatility_signal=vol_signal,
                    market_regime=market_regime,
                    score=self._score(86, iv_rank, market_regime, preferred="BEAR_TREND"),
                    confidence=volatility_profile.confidence,
                    reason="Bearish signal with elevated IV favors call credit spread.",
                    risk_profile="DEFINED_RISK",
                    premium_type="CREDIT",
                )
            )

            candidates.append(
                StrategyCandidate(
                    symbol=symbol,
                    direction="PUT",
                    strategy="SHORT_CALL",
                    volatility_regime=vol_regime,
                    volatility_signal=vol_signal,
                    market_regime=market_regime,
                    score=self._score(60, iv_rank, market_regime, preferred="BEAR_TREND"),
                    confidence=volatility_profile.confidence,
                    reason="High IV bearish setup; undefined upside risk requires strict controls.",
                    risk_profile="UNDEFINED_RISK",
                    premium_type="CREDIT",
                    warnings=["Undefined upside risk"],
                )
            )

        return candidates

    def _neutral_candidates(
        self,
        symbol,
        market_regime,
        vol_regime,
        vol_signal,
        volatility_profile,
    ):
        iv_rank = float(volatility_profile.iv_rank or 0.0)

        candidates = []

        if vol_regime in {"HIGH_VOL", "EXTREME_HIGH_VOL"}:
            candidates.append(
                StrategyCandidate(
                    symbol=symbol,
                    direction="NEUTRAL",
                    strategy="IRON_CONDOR",
                    volatility_regime=vol_regime,
                    volatility_signal=vol_signal,
                    market_regime=market_regime,
                    score=self._score(88, iv_rank, market_regime, preferred="SIDEWAYS"),
                    confidence=volatility_profile.confidence,
                    reason="Neutral signal with high IV favors defined-risk premium selling.",
                    risk_profile="DEFINED_RISK",
                    premium_type="CREDIT",
                )
            )

            candidates.append(
                StrategyCandidate(
                    symbol=symbol,
                    direction="NEUTRAL",
                    strategy="IRON_BUTTERFLY",
                    volatility_regime=vol_regime,
                    volatility_signal=vol_signal,
                    market_regime=market_regime,
                    score=self._score(80, iv_rank, market_regime, preferred="SIDEWAYS"),
                    confidence=volatility_profile.confidence,
                    reason="High IV neutral setup with tighter expected range.",
                    risk_profile="DEFINED_RISK",
                    premium_type="CREDIT",
                )
            )

        if vol_regime in {"LOW_VOL", "NORMAL_VOL"}:
            candidates.append(
                StrategyCandidate(
                    symbol=symbol,
                    direction="NEUTRAL",
                    strategy="LONG_STRADDLE",
                    volatility_regime=vol_regime,
                    volatility_signal=vol_signal,
                    market_regime=market_regime,
                    score=self._score(74, iv_rank, market_regime, preferred="SIDEWAYS"),
                    confidence=volatility_profile.confidence,
                    reason="Low IV neutral/uncertain setup may favor volatility expansion.",
                    risk_profile="DEFINED_RISK",
                    premium_type="DEBIT",
                )
            )

            candidates.append(
                StrategyCandidate(
                    symbol=symbol,
                    direction="NEUTRAL",
                    strategy="LONG_STRANGLE",
                    volatility_regime=vol_regime,
                    volatility_signal=vol_signal,
                    market_regime=market_regime,
                    score=self._score(70, iv_rank, market_regime, preferred="SIDEWAYS"),
                    confidence=volatility_profile.confidence,
                    reason="Lower-cost volatility expansion candidate.",
                    risk_profile="DEFINED_RISK",
                    premium_type="DEBIT",
                )
            )

        return candidates

    def _score(
        self,
        base_score: float,
        iv_rank: float,
        market_regime: str,
        preferred: str,
    ) -> float:
        score = float(base_score)

        if market_regime == preferred:
            score += 8.0

        if preferred == "SIDEWAYS" and market_regime in {"CHOP", "SIDEWAYS", "RANGE"}:
            score += 8.0

        if iv_rank >= 80:
            score += 4.0
        elif iv_rank >= 60:
            score += 2.0
        elif iv_rank <= 20:
            score += 2.0

        return round(max(0.0, min(100.0, score)), 2)

    def _apply_common_warnings(
        self,
        candidates: list[StrategyCandidate],
        volatility_profile,
    ) -> list[StrategyCandidate]:
        for candidate in candidates:
            if volatility_profile.confidence < 50:
                candidate.warnings.append("Low volatility-data confidence")
                candidate.score = max(0.0, candidate.score - 8.0)

            if candidate.risk_profile == "UNDEFINED_RISK":
                candidate.allowed = False
                candidate.score = max(0.0, candidate.score - 15.0)

        return candidates
