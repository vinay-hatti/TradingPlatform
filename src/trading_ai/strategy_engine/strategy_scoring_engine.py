import math
from typing import Any

from trading_ai.strategy_engine.strategy_score_breakdown import (
    StrategyScoreBreakdown,
)
from trading_ai.strategy_engine.strategy_score_policy import (
    StrategyScorePolicy,
)
from trading_ai.strategy_engine.strategy_score_weights import (
    StrategyScoreWeights,
)
from trading_ai.strategy_engine.strategy_scoring_context import (
    StrategyScoringContext,
)
from trading_ai.strategy_engine.strategy_scoring_result import (
    StrategyScoringResult,
)


class StrategyScoringEngine:
    """
    Institutional multi-factor strategy scoring engine.

    It converts all Phase 1-7 analytics into one score while preserving
    the individual score components for transparency and reporting.
    """

    def __init__(
        self,
        weights: StrategyScoreWeights | None = None,
        policy: StrategyScorePolicy | None = None,
    ):
        self.weights = weights or StrategyScoreWeights()
        self.policy = policy or StrategyScorePolicy()

        self.weights.validate()

    # ---------------------------------------------------------
    # Primary scoring API
    # ---------------------------------------------------------

    def score(
        self,
        context: StrategyScoringContext,
    ) -> StrategyScoringResult:
        normalized = self._normalize_context(context)

        weighted = self._weighted_components(normalized)

        raw_composite = sum(weighted.values())

        rejection_reasons = self._rejection_reasons(normalized)

        penalties, warnings = self._penalties(normalized)

        total_penalty = min(
            sum(penalty for _, penalty in penalties),
            self.policy.maximum_total_penalty,
        )

        final_score = max(
            0.0,
            min(100.0, raw_composite - total_penalty),
        )

        allowed = (
            not rejection_reasons
            and final_score >= self.policy.minimum_composite_score
        )

        strengths = self._strengths(normalized)
        weaknesses = self._weaknesses(normalized)

        grade = self._grade(final_score)
        confidence_label = self._confidence_label(
            normalized.data_confidence_score
        )
        readiness = self._readiness(
            score=final_score,
            allowed=allowed,
            data_confidence=normalized.data_confidence_score,
        )

        breakdown = StrategyScoreBreakdown(
            technical_score=normalized.technical_score,
            volatility_score=normalized.volatility_score,
            expected_move_score=normalized.expected_move_score,
            strategy_selection_score=(
                normalized.strategy_selection_score
            ),
            strike_score=normalized.strike_score,
            expiration_score=normalized.expiration_score,
            greeks_score=normalized.greeks_score,
            liquidity_score=normalized.liquidity_score,
            execution_score=normalized.execution_score,
            risk_reward_score=normalized.risk_reward_score,
            data_confidence_score=(
                normalized.data_confidence_score
            ),
            portfolio_fit_score=normalized.portfolio_fit_score,
            weighted_technical=weighted["technical"],
            weighted_volatility=weighted["volatility"],
            weighted_expected_move=weighted["expected_move"],
            weighted_strategy_selection=(
                weighted["strategy_selection"]
            ),
            weighted_strike=weighted["strike"],
            weighted_expiration=weighted["expiration"],
            weighted_greeks=weighted["greeks"],
            weighted_liquidity=weighted["liquidity"],
            weighted_execution=weighted["execution"],
            weighted_risk_reward=weighted["risk_reward"],
            weighted_data_confidence=(
                weighted["data_confidence"]
            ),
            weighted_portfolio_fit=weighted["portfolio_fit"],
            raw_composite_score=round(raw_composite, 2),
            total_penalty=round(total_penalty, 2),
            final_composite_score=round(final_score, 2),
        )

        return StrategyScoringResult(
            symbol=normalized.symbol,
            strategy=normalized.strategy,
            direction=normalized.direction,
            market_regime=normalized.market_regime,
            composite_score=round(final_score, 2),
            raw_composite_score=round(raw_composite, 2),
            total_penalty=round(total_penalty, 2),
            grade=grade,
            confidence_label=confidence_label,
            readiness=readiness,
            allowed=allowed,
            rejection_reasons=rejection_reasons,
            strengths=strengths,
            weaknesses=weaknesses,
            warnings=warnings,
            primary_reason=self._primary_reason(
                normalized,
                final_score,
                allowed,
                rejection_reasons,
            ),
            recommendation=self._recommendation(
                final_score,
                allowed,
                normalized.data_confidence_score,
                rejection_reasons,
            ),
            breakdown=breakdown,
            metadata=self._metadata(normalized, penalties),
        )

    def rank(
        self,
        contexts: list[StrategyScoringContext],
        allowed_only: bool = False,
    ) -> list[StrategyScoringResult]:
        results = [
            self.score(context)
            for context in contexts
        ]

        if allowed_only:
            results = [
                result
                for result in results
                if result.allowed
            ]

        results.sort(
            key=lambda result: (
                result.allowed,
                result.composite_score,
                result.raw_composite_score,
            ),
            reverse=True,
        )

        return results

    def best(
        self,
        contexts: list[StrategyScoringContext],
        allowed_only: bool = True,
    ) -> StrategyScoringResult | None:
        results = self.rank(
            contexts=contexts,
            allowed_only=allowed_only,
        )

        return results[0] if results else None

    # ---------------------------------------------------------
    # Context construction helpers
    # ---------------------------------------------------------

    def build_context(
        self,
        symbol: str,
        strategy_candidate,
        market_regime: str,
        technical_score: float = 0.0,
        strike_candidate=None,
        expiration_candidate=None,
        greeks_profile=None,
        liquidity_profile=None,
        expected_move_profile=None,
        volatility_profile=None,
        portfolio_fit_score: float = 50.0,
        risk_reward_score: float | None = None,
    ) -> StrategyScoringContext:
        strategy = str(
            getattr(strategy_candidate, "strategy", "")
            or ""
        ).upper()

        direction = str(
            getattr(strategy_candidate, "direction", "")
            or ""
        ).upper()

        strategy_selection_score = self._score_from(
            strategy_candidate,
            [
                "score",
                "composite_score",
            ],
        )

        volatility_score = self._volatility_score(
            volatility_profile=volatility_profile,
            strategy_candidate=strategy_candidate,
        )

        expected_move_score = self._score_from(
            strategy_candidate,
            ["expected_move_score"],
        )

        if expected_move_score <= 0 and expected_move_profile is not None:
            expected_move_score = self._expected_move_confidence_score(
                expected_move_profile
            )

        strike_score = self._score_from(
            strike_candidate,
            [
                "institutional_composite_score",
                "composite_score",
            ],
        )

        expiration_score = self._score_from(
            expiration_candidate,
            ["composite_score"],
        )

        greeks_score = self._score_from(
            greeks_profile,
            [
                "composite_score",
                "balance_score",
            ],
        )

        liquidity_score = self._score_from(
            liquidity_profile,
            [
                "package_liquidity_score",
                "liquidity_score",
            ],
        )

        execution_score = self._score_from(
            liquidity_profile,
            ["execution_score"],
        )

        if risk_reward_score is None:
            risk_reward_score = self._derive_risk_reward_score(
                strike_candidate
            )

        confidence_score = self._combined_data_confidence(
            volatility_profile=volatility_profile,
            expected_move_profile=expected_move_profile,
        )

        return StrategyScoringContext(
            symbol=symbol,
            strategy=strategy,
            direction=direction,
            market_regime=str(market_regime or "UNKNOWN").upper(),
            technical_score=self._bound_score(technical_score),
            volatility_score=self._bound_score(volatility_score),
            expected_move_score=self._bound_score(expected_move_score),
            strategy_selection_score=self._bound_score(
                strategy_selection_score
            ),
            strike_score=self._bound_score(strike_score),
            expiration_score=self._bound_score(expiration_score),
            greeks_score=self._bound_score(greeks_score),
            liquidity_score=self._bound_score(liquidity_score),
            execution_score=self._bound_score(execution_score),
            risk_reward_score=self._bound_score(
                risk_reward_score
            ),
            data_confidence_score=self._bound_score(
                confidence_score
            ),
            portfolio_fit_score=self._bound_score(
                portfolio_fit_score
            ),
            strategy_allowed=bool(
                getattr(strategy_candidate, "allowed", True)
            ),
            strike_allowed=bool(
                getattr(strike_candidate, "allowed", True)
                if strike_candidate is not None
                else True
            ),
            expiration_allowed=bool(
                getattr(expiration_candidate, "allowed", True)
                if expiration_candidate is not None
                else True
            ),
            greeks_allowed=bool(
                getattr(greeks_profile, "allowed", True)
                if greeks_profile is not None
                else True
            ),
            liquidity_allowed=bool(
                getattr(liquidity_profile, "allowed", True)
                if liquidity_profile is not None
                else True
            ),
            risk_profile=str(
                getattr(
                    strategy_candidate,
                    "risk_profile",
                    "DEFINED_RISK",
                )
                or "DEFINED_RISK"
            ).upper(),
            premium_type=str(
                getattr(strategy_candidate, "premium_type", "")
                or ""
            ).upper(),
            complexity=self._strategy_complexity(strategy),
            strategy_candidate=strategy_candidate,
            strike_candidate=strike_candidate,
            expiration_candidate=expiration_candidate,
            greeks_profile=greeks_profile,
            liquidity_profile=liquidity_profile,
            expected_move_profile=expected_move_profile,
            volatility_profile=volatility_profile,
            notes=[],
        )

    # ---------------------------------------------------------
    # Normalization and weighting
    # ---------------------------------------------------------

    def _normalize_context(
        self,
        context: StrategyScoringContext,
    ) -> StrategyScoringContext:
        score_fields = [
            "technical_score",
            "volatility_score",
            "expected_move_score",
            "strategy_selection_score",
            "strike_score",
            "expiration_score",
            "greeks_score",
            "liquidity_score",
            "execution_score",
            "risk_reward_score",
            "data_confidence_score",
            "portfolio_fit_score",
        ]

        for field_name in score_fields:
            value = getattr(context, field_name)
            setattr(
                context,
                field_name,
                self._bound_score(value),
            )

        context.symbol = str(context.symbol or "").upper()
        context.strategy = str(context.strategy or "").upper()
        context.direction = str(context.direction or "").upper()
        context.market_regime = str(
            context.market_regime or "UNKNOWN"
        ).upper()

        return context

    def _weighted_components(
        self,
        context: StrategyScoringContext,
    ) -> dict[str, float]:
        weights = self.weights.as_dict()

        components = {
            "technical": context.technical_score,
            "volatility": context.volatility_score,
            "expected_move": context.expected_move_score,
            "strategy_selection": (
                context.strategy_selection_score
            ),
            "strike": context.strike_score,
            "expiration": context.expiration_score,
            "greeks": context.greeks_score,
            "liquidity": context.liquidity_score,
            "execution": context.execution_score,
            "risk_reward": context.risk_reward_score,
            "data_confidence": context.data_confidence_score,
            "portfolio_fit": context.portfolio_fit_score,
        }

        return {
            name: round(
                components[name] * weights[name],
                4,
            )
            for name in components
        }

    # ---------------------------------------------------------
    # Rejections and penalties
    # ---------------------------------------------------------

    def _rejection_reasons(
        self,
        context: StrategyScoringContext,
    ) -> list[str]:
        reasons = []

        if (
            self.policy.reject_disallowed_strategy
            and not context.strategy_allowed
        ):
            reasons.append("STRATEGY_NOT_ALLOWED")

        if (
            self.policy.reject_disallowed_strike
            and not context.strike_allowed
        ):
            reasons.append("STRIKE_NOT_ALLOWED")

        if (
            self.policy.reject_disallowed_expiration
            and not context.expiration_allowed
        ):
            reasons.append("EXPIRATION_NOT_ALLOWED")

        if (
            self.policy.reject_disallowed_greeks
            and not context.greeks_allowed
        ):
            reasons.append("GREEKS_NOT_ALLOWED")

        if (
            self.policy.reject_disallowed_liquidity
            and not context.liquidity_allowed
        ):
            reasons.append("LIQUIDITY_NOT_ALLOWED")

        if (
            context.liquidity_score
            < self.policy.minimum_liquidity_score
        ):
            reasons.append("LIQUIDITY_SCORE_BELOW_MINIMUM")

        if (
            context.execution_score
            < self.policy.minimum_execution_score
        ):
            reasons.append("EXECUTION_SCORE_BELOW_MINIMUM")

        if (
            context.greeks_score
            < self.policy.minimum_greeks_score
        ):
            reasons.append("GREEKS_SCORE_BELOW_MINIMUM")

        return list(dict.fromkeys(reasons))

    def _penalties(
        self,
        context: StrategyScoringContext,
    ) -> tuple[list[tuple[str, float]], list[str]]:
        penalties = []
        warnings = []

        if (
            context.data_confidence_score
            < self.policy.minimum_data_confidence
        ):
            penalties.append(
                (
                    "LOW_DATA_CONFIDENCE",
                    self.policy.low_confidence_penalty,
                )
            )
            warnings.append("Low data confidence")

        if (
            context.execution_score
            < self.policy.minimum_execution_score
        ):
            penalties.append(
                (
                    "POOR_EXECUTION",
                    self.policy.poor_execution_penalty,
                )
            )
            warnings.append("Execution quality below minimum")

        if (
            context.liquidity_score
            < self.policy.minimum_liquidity_score
        ):
            penalties.append(
                (
                    "WEAK_LIQUIDITY",
                    self.policy.weak_liquidity_penalty,
                )
            )
            warnings.append("Liquidity quality below minimum")

        if (
            context.greeks_score
            < self.policy.minimum_greeks_score
        ):
            penalties.append(
                (
                    "WEAK_GREEKS",
                    self.policy.weak_greeks_penalty,
                )
            )
            warnings.append("Greeks profile below minimum")

        if context.risk_profile == "UNDEFINED_RISK":
            penalties.append(
                (
                    "UNDEFINED_RISK",
                    self.policy.undefined_risk_penalty,
                )
            )
            warnings.append("Undefined-risk strategy")

        if context.complexity == "COMPLEX":
            penalties.append(
                (
                    "COMPLEX_STRATEGY",
                    self.policy.complex_strategy_penalty,
                )
            )
            warnings.append("Complex multi-leg strategy")

        component_values = {
            "technical": context.technical_score,
            "volatility": context.volatility_score,
            "expected_move": context.expected_move_score,
            "strategy_selection": (
                context.strategy_selection_score
            ),
            "strike": context.strike_score,
            "expiration": context.expiration_score,
            "greeks": context.greeks_score,
            "liquidity": context.liquidity_score,
            "execution": context.execution_score,
            "risk_reward": context.risk_reward_score,
        }

        missing_components = [
            name
            for name, value in component_values.items()
            if value <= 0
        ]

        if missing_components:
            penalty = min(
                len(missing_components)
                * self.policy.missing_component_penalty,
                15.0,
            )

            penalties.append(
                ("MISSING_COMPONENTS", penalty)
            )

            warnings.append(
                "Missing score components: "
                + ", ".join(missing_components)
            )

        return penalties, warnings

    # ---------------------------------------------------------
    # Descriptive outputs
    # ---------------------------------------------------------

    def _strengths(
        self,
        context: StrategyScoringContext,
    ) -> list[str]:
        score_map = self._score_map(context)

        ranked = sorted(
            score_map.items(),
            key=lambda item: item[1],
            reverse=True,
        )

        strengths = [
            self._label(name)
            for name, score in ranked
            if score >= 80
        ]

        return strengths[:4]

    def _weaknesses(
        self,
        context: StrategyScoringContext,
    ) -> list[str]:
        score_map = self._score_map(context)

        ranked = sorted(
            score_map.items(),
            key=lambda item: item[1],
        )

        weaknesses = [
            self._label(name)
            for name, score in ranked
            if score < 60
        ]

        return weaknesses[:4]

    def _primary_reason(
        self,
        context: StrategyScoringContext,
        final_score: float,
        allowed: bool,
        rejection_reasons: list[str],
    ) -> str:
        if rejection_reasons:
            return (
                f"{context.strategy} rejected because "
                + ", ".join(rejection_reasons)
            )

        strengths = self._strengths(context)

        if allowed:
            strength_text = (
                ", ".join(strengths)
                if strengths
                else "balanced multi-factor quality"
            )

            return (
                f"{context.strategy} scored {final_score:.2f} "
                f"with strengths in {strength_text}."
            )

        return (
            f"{context.strategy} scored {final_score:.2f}, "
            "below the minimum institutional threshold."
        )

    def _recommendation(
        self,
        final_score: float,
        allowed: bool,
        data_confidence: float,
        rejection_reasons: list[str],
    ) -> str:
        if rejection_reasons:
            return "REJECT"

        if not allowed:
            return "RESEARCH_ONLY"

        if data_confidence < 60:
            return "PAPER_TRADE_ONLY"

        if final_score >= self.policy.live_candidate_score:
            return "LIVE_CANDIDATE"

        if final_score >= self.policy.preferred_composite_score:
            return "PAPER_TRADE_CANDIDATE"

        return "WATCHLIST"

    def _grade(self, score: float) -> str:
        if score >= 95:
            return "A+"

        if score >= 90:
            return "A"

        if score >= 85:
            return "A-"

        if score >= 80:
            return "B+"

        if score >= 75:
            return "B"

        if score >= 70:
            return "B-"

        if score >= 65:
            return "C+"

        if score >= 60:
            return "C"

        if score >= 50:
            return "D"

        return "F"

    def _confidence_label(self, score: float) -> str:
        if score >= 85:
            return "HIGH"

        if score >= 65:
            return "MODERATE"

        if score >= 40:
            return "LOW"

        return "INSUFFICIENT"

    def _readiness(
        self,
        score: float,
        allowed: bool,
        data_confidence: float,
    ) -> str:
        if not allowed:
            return "REJECTED"

        if data_confidence < 40:
            return "INSUFFICIENT_DATA"

        if score >= self.policy.live_candidate_score:
            return "LIVE_CANDIDATE"

        if score >= self.policy.preferred_composite_score:
            return "PAPER_TRADING"

        if score >= self.policy.minimum_composite_score:
            return "RESEARCH_READY"

        return "RESEARCH_ONLY"

    # ---------------------------------------------------------
    # Input extraction helpers
    # ---------------------------------------------------------

    def _volatility_score(
        self,
        volatility_profile,
        strategy_candidate,
    ) -> float:
        if volatility_profile is None:
            return 0.0

        confidence = self._score_from(
            volatility_profile,
            ["confidence"],
        )

        iv_rank = self._safe_float(
            getattr(volatility_profile, "iv_rank", 0.0)
        )

        regime = str(
            getattr(
                volatility_profile,
                "volatility_regime",
                "",
            )
        ).upper()

        premium_type = str(
            getattr(strategy_candidate, "premium_type", "")
        ).upper()

        fit_score = 60.0

        if premium_type == "CREDIT":
            if regime in {"HIGH_VOL", "EXTREME_HIGH_VOL"}:
                fit_score = 95.0
            elif regime == "NORMAL_VOL":
                fit_score = 70.0
            else:
                fit_score = 45.0

        elif premium_type == "DEBIT":
            if regime == "LOW_VOL":
                fit_score = 95.0
            elif regime == "NORMAL_VOL":
                fit_score = 80.0
            elif regime == "HIGH_VOL":
                fit_score = 55.0
            else:
                fit_score = 35.0

        if iv_rank >= 80 and premium_type == "CREDIT":
            fit_score += 5.0

        if iv_rank <= 20 and premium_type == "DEBIT":
            fit_score += 5.0

        combined = (
            self._bound_score(fit_score) * 0.70
            + self._bound_score(confidence) * 0.30
        )

        return round(combined, 2)

    def _expected_move_confidence_score(
        self,
        expected_move_profile,
    ) -> float:
        confidence = self._score_from(
            expected_move_profile,
            ["confidence_score"],
        )

        agreement = self._score_from(
            expected_move_profile,
            ["source_agreement_score"],
        )

        return round(
            confidence * 0.60
            + agreement * 0.40,
            2,
        )

    def _combined_data_confidence(
        self,
        volatility_profile,
        expected_move_profile,
    ) -> float:
        values = []

        if volatility_profile is not None:
            values.append(
                self._score_from(
                    volatility_profile,
                    ["confidence"],
                )
            )

        if expected_move_profile is not None:
            values.append(
                self._score_from(
                    expected_move_profile,
                    ["confidence_score"],
                )
            )

        values = [
            value
            for value in values
            if value > 0
        ]

        if not values:
            return 0.0

        return round(
            sum(values) / len(values),
            2,
        )

    def _derive_risk_reward_score(
        self,
        candidate,
    ) -> float:
        if candidate is None:
            return 0.0

        direct_score = self._score_from(
            candidate,
            ["risk_reward_score", "risk_score"],
        )

        if direct_score > 0:
            return direct_score

        max_profit = self._safe_float(
            getattr(candidate, "max_profit", 0.0)
        )

        max_loss = self._safe_float(
            getattr(candidate, "max_loss", 0.0)
        )

        if max_profit <= 0 or max_loss <= 0:
            return 50.0

        ratio = max_profit / max_loss

        if ratio >= 2.0:
            return 100.0

        if ratio >= 1.0:
            return 90.0

        if ratio >= 0.50:
            return 75.0

        if ratio >= 0.33:
            return 65.0

        if ratio >= 0.20:
            return 50.0

        return 30.0

    def _strategy_complexity(self, strategy: str) -> str:
        strategy = str(strategy or "").upper()

        if strategy in {
            "IRON_CONDOR",
            "IRON_BUTTERFLY",
            "CALENDAR",
            "DIAGONAL",
            "RATIO_SPREAD",
            "PUT_RATIO_SPREAD",
            "CALL_RATIO_SPREAD",
        }:
            return "COMPLEX"

        if strategy in {
            "BULL_CALL_SPREAD",
            "BEAR_PUT_SPREAD",
            "BULL_PUT_SPREAD",
            "BEAR_CALL_SPREAD",
            "LONG_STRADDLE",
            "LONG_STRANGLE",
        }:
            return "MULTI_LEG"

        return "STANDARD"

    # ---------------------------------------------------------
    # Utility helpers
    # ---------------------------------------------------------

    def _score_from(
        self,
        obj: Any,
        fields: list[str],
    ) -> float:
        if obj is None:
            return 0.0

        for field_name in fields:
            if isinstance(obj, dict):
                value = obj.get(field_name)
            else:
                value = getattr(obj, field_name, None)

            parsed = self._safe_float(value)

            if parsed > 0:
                return self._bound_score(parsed)

        return 0.0

    def _safe_float(
        self,
        value,
        default: float = 0.0,
    ) -> float:
        try:
            result = float(value)

            if math.isnan(result) or math.isinf(result):
                return float(default)

            return result

        except (TypeError, ValueError):
            return float(default)

    def _bound_score(self, value) -> float:
        return round(
            max(
                0.0,
                min(100.0, self._safe_float(value)),
            ),
            2,
        )

    def _score_map(
        self,
        context: StrategyScoringContext,
    ) -> dict[str, float]:
        return {
            "technical": context.technical_score,
            "volatility": context.volatility_score,
            "expected_move": context.expected_move_score,
            "strategy_selection": (
                context.strategy_selection_score
            ),
            "strike": context.strike_score,
            "expiration": context.expiration_score,
            "greeks": context.greeks_score,
            "liquidity": context.liquidity_score,
            "execution": context.execution_score,
            "risk_reward": context.risk_reward_score,
            "data_confidence": context.data_confidence_score,
            "portfolio_fit": context.portfolio_fit_score,
        }

    def _label(self, key: str) -> str:
        return key.replace("_", " ").title()

    def _metadata(
        self,
        context: StrategyScoringContext,
        penalties: list[tuple[str, float]],
    ) -> dict:
        return {
            "premium_type": context.premium_type,
            "risk_profile": context.risk_profile,
            "complexity": context.complexity,
            "penalties": [
                {
                    "reason": reason,
                    "value": value,
                }
                for reason, value in penalties
            ],
        }
