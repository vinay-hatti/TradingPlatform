import math
from typing import Any

from trading_ai.strategy_engine.institutional_opportunity import (
    InstitutionalOpportunity,
)


class OpportunityFactory:
    """
    Converts Phase 8 scoring output and Phase 1-7 analytics into a
    complete InstitutionalOpportunity.
    """

    def create(
        self,
        symbol: str,
        strategy_scoring_result,
        strategy_candidate=None,
        strike_candidate=None,
        expiration_candidate=None,
        greeks_profile=None,
        liquidity_profile=None,
        expected_move_profile=None,
        volatility_profile=None,
        expected_return_pct: float | None = None,
        expected_profit: float | None = None,
        maximum_loss: float | None = None,
        capital_required: float | None = None,
        probability_of_profit: float | None = None,
        portfolio_fit_score: float = 50.0,
        sector: str = "UNKNOWN",
        industry: str = "UNKNOWN",
        correlation_group: str = "",
        contracts: int = 1,
        metadata: dict | None = None,
    ) -> InstitutionalOpportunity:
        result = strategy_scoring_result

        strategy = str(
            getattr(result, "strategy", "")
            or getattr(strategy_candidate, "strategy", "")
            or ""
        ).upper()

        direction = str(
            getattr(result, "direction", "")
            or getattr(strategy_candidate, "direction", "")
            or ""
        ).upper()

        market_regime = str(
            getattr(result, "market_regime", "UNKNOWN")
            or "UNKNOWN"
        ).upper()

        strategy_score = self._safe_float(
            getattr(result, "composite_score", 0.0)
        )

        allowed = bool(
            getattr(result, "allowed", False)
        )

        readiness = str(
            getattr(result, "readiness", "RESEARCH_ONLY")
            or "RESEARCH_ONLY"
        ).upper()

        recommendation = str(
            getattr(result, "recommendation", "RESEARCH_ONLY")
            or "RESEARCH_ONLY"
        ).upper()

        breakdown = getattr(result, "breakdown", None)

        liquidity_score = self._first_score(
            liquidity_profile,
            [
                "package_liquidity_score",
                "liquidity_score",
            ],
        )

        if liquidity_score <= 0 and breakdown is not None:
            liquidity_score = self._safe_float(
                getattr(breakdown, "liquidity_score", 0.0)
            )

        execution_score = self._first_score(
            liquidity_profile,
            ["execution_score"],
        )

        if execution_score <= 0 and breakdown is not None:
            execution_score = self._safe_float(
                getattr(breakdown, "execution_score", 0.0)
            )

        greeks_score = self._first_score(
            greeks_profile,
            [
                "composite_score",
                "balance_score",
            ],
        )

        if greeks_score <= 0 and breakdown is not None:
            greeks_score = self._safe_float(
                getattr(breakdown, "greeks_score", 0.0)
            )

        expected_move_score = 0.0

        if strategy_candidate is not None:
            expected_move_score = self._safe_float(
                getattr(
                    strategy_candidate,
                    "expected_move_score",
                    0.0,
                )
            )

        if expected_move_score <= 0 and breakdown is not None:
            expected_move_score = self._safe_float(
                getattr(
                    breakdown,
                    "expected_move_score",
                    0.0,
                )
            )

        data_confidence_score = 0.0

        if breakdown is not None:
            data_confidence_score = self._safe_float(
                getattr(
                    breakdown,
                    "data_confidence_score",
                    0.0,
                )
            )

        risk_reward_score = 0.0

        if breakdown is not None:
            risk_reward_score = self._safe_float(
                getattr(
                    breakdown,
                    "risk_reward_score",
                    0.0,
                )
            )

        if expected_return_pct is None:
            expected_return_pct = self._derive_expected_return_pct(
                expected_profit=expected_profit,
                capital_required=capital_required,
                strike_candidate=strike_candidate,
            )

        if expected_profit is None:
            expected_profit = self._derive_expected_profit(
                strike_candidate
            )

        if maximum_loss is None:
            maximum_loss = self._derive_maximum_loss(
                strike_candidate
            )

        if capital_required is None:
            capital_required = self._derive_capital_required(
                strike_candidate=strike_candidate,
                maximum_loss=maximum_loss,
                contracts=contracts,
            )

        if probability_of_profit is None:
            probability_of_profit = self._derive_probability_of_profit(
                strategy_candidate=strategy_candidate,
                expected_move_profile=expected_move_profile,
                strike_candidate=strike_candidate,
            )

        strike = self._optional_float(
            getattr(strike_candidate, "strike", None)
            if strike_candidate is not None
            else None
        )

        long_strike = self._optional_float(
            getattr(strike_candidate, "long_strike", None)
            if strike_candidate is not None
            else None
        )

        short_strike = self._optional_float(
            getattr(strike_candidate, "short_strike", None)
            if strike_candidate is not None
            else None
        )

        expiry = ""

        if expiration_candidate is not None:
            expiry = str(
                getattr(expiration_candidate, "expiry", "")
                or ""
            )

        if not expiry and strike_candidate is not None:
            expiry = str(
                getattr(strike_candidate, "expiry", "")
                or ""
            )

        dte = 0

        if expiration_candidate is not None:
            dte = int(
                self._safe_float(
                    getattr(expiration_candidate, "dte", 0)
                )
            )

        if dte <= 0 and strike_candidate is not None:
            dte = int(
                self._safe_float(
                    getattr(strike_candidate, "dte", 0)
                )
            )

        option_symbol = ""

        if strike_candidate is not None:
            option_symbol = str(
                getattr(
                    strike_candidate,
                    "option_symbol",
                    "",
                )
                or ""
            )

        result_metadata = getattr(
            result,
            "metadata",
            {},
        ) or {}

        premium_type = str(
            getattr(strategy_candidate, "premium_type", "")
            or result_metadata.get("premium_type", "")
            or ""
        ).upper()

        risk_profile = str(
            getattr(
                strategy_candidate,
                "risk_profile",
                "",
            )
            or result_metadata.get(
                "risk_profile",
                "DEFINED_RISK",
            )
            or "DEFINED_RISK"
        ).upper()

        complexity = str(
            result_metadata.get(
                "complexity",
                "STANDARD",
            )
            or "STANDARD"
        ).upper()

        rejection_reasons = list(
            getattr(result, "rejection_reasons", [])
            or []
        )

        warnings = list(
            getattr(result, "warnings", [])
            or []
        )

        rank_eligible = (
            allowed
            and strategy_score > 0
            and not rejection_reasons
        )

        return InstitutionalOpportunity(
            symbol=symbol,
            strategy=strategy,
            direction=direction,
            market_regime=market_regime,
            strategy_score=round(strategy_score, 2),
            allowed=allowed,
            readiness=readiness,
            recommendation=recommendation,
            expected_return_pct=round(
                self._safe_float(expected_return_pct),
                4,
            ),
            expected_profit=round(
                self._safe_float(expected_profit),
                2,
            ),
            maximum_loss=round(
                self._safe_float(maximum_loss),
                2,
            ),
            capital_required=round(
                self._safe_float(capital_required),
                2,
            ),
            probability_of_profit=self._normalize_probability(
                probability_of_profit
            ),
            liquidity_score=round(liquidity_score, 2),
            execution_score=round(execution_score, 2),
            greeks_score=round(greeks_score, 2),
            expected_move_score=round(
                expected_move_score,
                2,
            ),
            data_confidence_score=round(
                data_confidence_score,
                2,
            ),
            risk_reward_score=round(
                risk_reward_score,
                2,
            ),
            portfolio_fit_score=round(
                self._bound_score(portfolio_fit_score),
                2,
            ),
            strike=strike,
            long_strike=long_strike,
            short_strike=short_strike,
            expiry=expiry,
            dte=dte,
            premium_type=premium_type,
            risk_profile=risk_profile,
            complexity=complexity,
            sector=sector,
            industry=industry,
            correlation_group=correlation_group,
            option_symbol=option_symbol,
            contracts=contracts,
            rank_eligible=rank_eligible,
            rejection_reasons=rejection_reasons,
            warnings=warnings,
            strategy_scoring_result=result,
            strategy_candidate=strategy_candidate,
            strike_candidate=strike_candidate,
            expiration_candidate=expiration_candidate,
            greeks_profile=greeks_profile,
            liquidity_profile=liquidity_profile,
            expected_move_profile=expected_move_profile,
            volatility_profile=volatility_profile,
            metadata=dict(metadata or {}),
        )

    def _derive_expected_return_pct(
        self,
        expected_profit,
        capital_required,
        strike_candidate,
    ) -> float:
        direct_value = self._first_score(
            strike_candidate,
            [
                "expected_return_pct",
                "expected_return",
            ],
            bound=False,
        )

        if direct_value > 0:
            return direct_value

        profit = self._safe_float(expected_profit)
        capital = self._safe_float(capital_required)

        if profit > 0 and capital > 0:
            return profit / capital

        return 0.0

    def _derive_expected_profit(self, strike_candidate) -> float:
        return self._first_score(
            strike_candidate,
            [
                "expected_profit",
                "max_profit",
            ],
            bound=False,
        )

    def _derive_maximum_loss(self, strike_candidate) -> float:
        return self._first_score(
            strike_candidate,
            [
                "maximum_loss",
                "max_loss",
                "initial_risk",
            ],
            bound=False,
        )

    def _derive_capital_required(
        self,
        strike_candidate,
        maximum_loss,
        contracts,
    ) -> float:
        direct_value = self._first_score(
            strike_candidate,
            [
                "capital_required",
                "position_size",
            ],
            bound=False,
        )

        if direct_value > 0:
            return direct_value

        maximum_loss = self._safe_float(maximum_loss)

        if maximum_loss > 0:
            return maximum_loss * max(int(contracts or 1), 1)

        mid = self._safe_float(
            getattr(strike_candidate, "mid", 0.0)
            if strike_candidate is not None
            else 0.0
        )

        if mid > 0:
            return (
                mid
                * max(int(contracts or 1), 1)
                * 100.0
            )

        return 0.0

    def _derive_probability_of_profit(
        self,
        strategy_candidate,
        expected_move_profile,
        strike_candidate,
    ) -> float | None:
        for obj in [
            strategy_candidate,
            strike_candidate,
        ]:
            if obj is None:
                continue

            for field in [
                "probability_of_profit",
                "pop",
            ]:
                value = getattr(obj, field, None)

                if value is not None:
                    return self._normalize_probability(
                        value
                    )

        return None

    def _first_score(
        self,
        obj: Any,
        fields: list[str],
        bound: bool = True,
    ) -> float:
        if obj is None:
            return 0.0

        for field in fields:
            value = (
                obj.get(field)
                if isinstance(obj, dict)
                else getattr(obj, field, None)
            )

            parsed = self._safe_float(value)

            if parsed != 0:
                return (
                    self._bound_score(parsed)
                    if bound
                    else parsed
                )

        return 0.0

    def _normalize_probability(
        self,
        value,
    ) -> float | None:
        if value is None:
            return None

        probability = self._safe_float(value)

        if probability > 1.0:
            probability /= 100.0

        return round(
            max(0.0, min(1.0, probability)),
            4,
        )

    def _optional_float(self, value) -> float | None:
        if value is None:
            return None

        return self._safe_float(value)

    def _bound_score(self, value) -> float:
        return max(
            0.0,
            min(100.0, self._safe_float(value)),
        )

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
