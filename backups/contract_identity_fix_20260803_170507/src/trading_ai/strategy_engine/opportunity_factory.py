import math
from typing import Any

from trading_ai.strategy_engine.institutional_opportunity import (
    InstitutionalOpportunity,
)


class OpportunityFactory:
    """
    Converts strategy scoring and analytical profiles into a complete
    InstitutionalOpportunity.
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
        payoff_profile=None,
        probability_profile=None,
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
            or getattr(
                strategy_candidate,
                "strategy",
                "",
            )
            or ""
        ).upper()

        direction = str(
            getattr(result, "direction", "")
            or getattr(
                strategy_candidate,
                "direction",
                "",
            )
            or ""
        ).upper()

        market_regime = str(
            getattr(
                result,
                "market_regime",
                "UNKNOWN",
            )
            or "UNKNOWN"
        ).upper()

        strategy_score = self._safe_float(
            getattr(
                result,
                "composite_score",
                0.0,
            )
        )

        allowed = bool(
            getattr(
                result,
                "allowed",
                False,
            )
        )

        readiness = str(
            getattr(
                result,
                "readiness",
                "RESEARCH_ONLY",
            )
            or "RESEARCH_ONLY"
        ).upper()

        recommendation = str(
            getattr(
                result,
                "recommendation",
                "RESEARCH_ONLY",
            )
            or "RESEARCH_ONLY"
        ).upper()

        breakdown = getattr(
            result,
            "breakdown",
            None,
        )

        liquidity_score = self._first_value(
            liquidity_profile,
            [
                "package_liquidity_score",
                "liquidity_score",
            ],
        )

        if liquidity_score <= 0:
            liquidity_score = self._first_value(
                breakdown,
                ["liquidity_score"],
            )

        execution_score = self._first_value(
            liquidity_profile,
            ["execution_score"],
        )

        if execution_score <= 0:
            execution_score = self._first_value(
                breakdown,
                ["execution_score"],
            )

        greeks_score = self._first_value(
            greeks_profile,
            [
                "composite_score",
                "balance_score",
            ],
        )

        if greeks_score <= 0:
            greeks_score = self._first_value(
                breakdown,
                ["greeks_score"],
            )

        expected_move_score = self._first_value(
            strategy_candidate,
            ["expected_move_score"],
        )

        if expected_move_score <= 0:
            expected_move_score = self._first_value(
                breakdown,
                ["expected_move_score"],
            )

        data_confidence_score = self._first_value(
            breakdown,
            ["data_confidence_score"],
        )

        risk_reward_score = self._first_value(
            breakdown,
            ["risk_reward_score"],
        )

        # -------------------------------------------------
        # Payoff profile values
        # -------------------------------------------------

        if payoff_profile is not None:
            if expected_profit is None:
                expected_profit = self._optional_numeric(
                    getattr(
                        payoff_profile,
                        "expected_profit",
                        None,
                    )
                )

            if maximum_loss is None:
                maximum_loss = self._optional_numeric(
                    getattr(
                        payoff_profile,
                        "maximum_loss",
                        None,
                    )
                )

            if capital_required is None:
                capital_required = self._optional_numeric(
                    getattr(
                        payoff_profile,
                        "capital_required",
                        None,
                    )
                )

            if expected_return_pct is None:
                expected_return_pct = self._optional_numeric(
                    getattr(
                        payoff_profile,
                        "expected_return_pct",
                        None,
                    )
                )

        # -------------------------------------------------
        # Probability profile values
        # -------------------------------------------------

        probability_valid = bool(
            probability_profile is not None
            and getattr(
                probability_profile,
                "valid",
                False,
            )
        )

        if (
            probability_of_profit is None
            and probability_valid
        ):
            probability_of_profit = getattr(
                probability_profile,
                "probability_of_profit",
                None,
            )

        if (
            probability_valid
            and expected_profit is None
        ):
            expected_profit = self._optional_numeric(
                getattr(
                    probability_profile,
                    "expected_value",
                    None,
                )
            )

        if (
            probability_valid
            and expected_return_pct is None
        ):
            expected_return_pct = self._optional_numeric(
                getattr(
                    probability_profile,
                    "expected_return_on_capital",
                    None,
                )
            )

        # -------------------------------------------------
        # Candidate-derived fallbacks
        # -------------------------------------------------

        if expected_profit is None:
            expected_profit = self._first_value(
                strike_candidate,
                [
                    "expected_profit",
                    "max_profit",
                ],
                bound=False,
            )

        if maximum_loss is None:
            maximum_loss = self._first_value(
                strike_candidate,
                [
                    "maximum_loss",
                    "max_loss",
                    "initial_risk",
                ],
                bound=False,
            )

        if capital_required is None:
            capital_required = self._first_value(
                strike_candidate,
                [
                    "capital_required",
                    "position_size",
                ],
                bound=False,
            )

        contracts = max(
            int(contracts or 1),
            1,
        )

        if (
            not capital_required
            and maximum_loss
        ):
            capital_required = float(
                maximum_loss
            )

        if not capital_required:
            mid = self._safe_float(
                getattr(
                    strike_candidate,
                    "mid",
                    0.0,
                )
                if strike_candidate is not None
                else 0.0
            )

            if mid > 0:
                capital_required = (
                    mid
                    * contracts
                    * 100.0
                )

        if expected_return_pct is None:
            if (
                self._safe_float(
                    expected_profit
                )
                != 0
                and self._safe_float(
                    capital_required
                )
                > 0
            ):
                expected_return_pct = (
                    self._safe_float(
                        expected_profit
                    )
                    / self._safe_float(
                        capital_required
                    )
                )
            else:
                expected_return_pct = 0.0

        if probability_of_profit is None:
            probability_of_profit = (
                self._derive_probability_of_profit(
                    strategy_candidate,
                    strike_candidate,
                )
            )

        strike = self._optional_float(
            getattr(
                strike_candidate,
                "strike",
                None,
            )
            if strike_candidate is not None
            else None
        )

        long_strike = self._optional_float(
            getattr(
                strike_candidate,
                "long_strike",
                None,
            )
            if strike_candidate is not None
            else None
        )

        short_strike = self._optional_float(
            getattr(
                strike_candidate,
                "short_strike",
                None,
            )
            if strike_candidate is not None
            else None
        )

        expiry = ""

        if expiration_candidate is not None:
            expiry = str(
                getattr(
                    expiration_candidate,
                    "expiry",
                    "",
                )
                or ""
            )

        if not expiry and strike_candidate is not None:
            expiry = str(
                getattr(
                    strike_candidate,
                    "expiry",
                    "",
                )
                or ""
            )

        dte = 0

        if expiration_candidate is not None:
            dte = int(
                self._safe_float(
                    getattr(
                        expiration_candidate,
                        "dte",
                        0,
                    )
                )
            )

        if dte <= 0 and strike_candidate is not None:
            dte = int(
                self._safe_float(
                    getattr(
                        strike_candidate,
                        "dte",
                        0,
                    )
                )
            )

        option_symbol = str(
            getattr(
                strike_candidate,
                "option_symbol",
                "",
            )
            or ""
        ) if strike_candidate is not None else ""

        result_metadata = dict(
            getattr(
                result,
                "metadata",
                {},
            )
            or {}
        )

        premium_type = str(
            getattr(
                strategy_candidate,
                "premium_type",
                "",
            )
            or result_metadata.get(
                "premium_type",
                "",
            )
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
            getattr(
                result,
                "rejection_reasons",
                [],
            )
            or []
        )

        warnings = list(
            getattr(
                result,
                "warnings",
                [],
            )
            or []
        )

        rank_eligible = (
            allowed
            and strategy_score > 0
            and not rejection_reasons
        )

        combined_metadata = {
            **dict(metadata or {}),
            "payoff_profile": payoff_profile,
            "probability_profile": probability_profile,
        }

        return InstitutionalOpportunity(
            symbol=symbol,
            strategy=strategy,
            direction=direction,
            market_regime=market_regime,
            strategy_score=round(
                strategy_score,
                2,
            ),
            allowed=allowed,
            readiness=readiness,
            recommendation=recommendation,
            expected_return_pct=round(
                self._safe_float(
                    expected_return_pct
                ),
                4,
            ),
            expected_profit=round(
                self._safe_float(
                    expected_profit
                ),
                2,
            ),
            maximum_loss=round(
                self._safe_float(
                    maximum_loss
                ),
                2,
            ),
            capital_required=round(
                self._safe_float(
                    capital_required
                ),
                2,
            ),
            probability_of_profit=(
                self._normalize_probability(
                    probability_of_profit
                )
            ),
            liquidity_score=round(
                liquidity_score,
                2,
            ),
            execution_score=round(
                execution_score,
                2,
            ),
            greeks_score=round(
                greeks_score,
                2,
            ),
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
                self._bound_score(
                    portfolio_fit_score
                ),
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
            metadata=combined_metadata,
        )

    def _derive_probability_of_profit(
        self,
        strategy_candidate,
        strike_candidate,
    ) -> float | None:
        for obj in [
            strategy_candidate,
            strike_candidate,
        ]:
            if obj is None:
                continue

            for field_name in [
                "probability_of_profit",
                "pop",
            ]:
                value = getattr(
                    obj,
                    field_name,
                    None,
                )

                if value is not None:
                    return self._normalize_probability(
                        value
                    )

        return None

    def _first_value(
        self,
        obj: Any,
        fields: list[str],
        bound: bool = True,
    ) -> float:
        if obj is None:
            return 0.0

        for field_name in fields:
            if isinstance(obj, dict):
                value = obj.get(
                    field_name
                )
            else:
                value = getattr(
                    obj,
                    field_name,
                    None,
                )

            if value is None:
                continue

            parsed = self._safe_float(
                value
            )

            if parsed != 0:
                return (
                    self._bound_score(
                        parsed
                    )
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

        probability = self._safe_float(
            value
        )

        if probability > 1.0:
            probability /= 100.0

        return round(
            max(
                0.0,
                min(
                    1.0,
                    probability,
                ),
            ),
            4,
        )

    def _optional_numeric(
        self,
        value,
    ) -> float | None:
        if value is None:
            return None

        return self._safe_float(
            value
        )

    def _optional_float(
        self,
        value,
    ) -> float | None:
        if value is None:
            return None

        return self._safe_float(
            value
        )

    def _bound_score(
        self,
        value,
    ) -> float:
        return max(
            0.0,
            min(
                100.0,
                self._safe_float(
                    value
                ),
            ),
        )

    def _safe_float(
        self,
        value,
        default: float = 0.0,
    ) -> float:
        try:
            result = float(
                value
            )

            if (
                math.isnan(result)
                or math.isinf(result)
            ):
                return float(
                    default
                )

            return result

        except (
            TypeError,
            ValueError,
        ):
            return float(
                default
            )
