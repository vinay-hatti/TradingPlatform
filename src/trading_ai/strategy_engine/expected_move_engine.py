import math
from collections import defaultdict
from typing import Any

from trading_ai.strategy_engine.expected_move_profile import (
    ExpectedMoveProfile,
)
from trading_ai.strategy_engine.expected_move_scoring import (
    ExpectedMoveScoring,
)
from trading_ai.strategy_engine.expected_move_source import (
    ExpectedMoveSource,
)


class ExpectedMoveEngine:
    """
    Institutional expected-move estimator.

    Sources:
      1. Implied-volatility move
      2. ATM straddle move
      3. Historical-volatility move
      4. ATR-derived move

    The final expected move is a confidence-aware weighted blend.
    """

    DEFAULT_WEIGHTS = {
        "ATM_STRADDLE": 0.40,
        "IMPLIED_VOLATILITY": 0.30,
        "HISTORICAL_VOLATILITY": 0.20,
        "ATR": 0.10,
    }

    def __init__(
        self,
        annual_trading_days: int = 252,
        calendar_days: int = 365,
        straddle_multiplier: float = 0.85,
        atr_scaling_mode: str = "SQRT_TIME",
    ):
        self.annual_trading_days = int(annual_trading_days)
        self.calendar_days = int(calendar_days)
        self.straddle_multiplier = float(straddle_multiplier)
        self.atr_scaling_mode = str(atr_scaling_mode).upper()

        self.scoring = ExpectedMoveScoring()

    # ---------------------------------------------------------
    # Backward-compatible basic API
    # ---------------------------------------------------------

    def calculate(
        self,
        underlying_price: float,
        volatility: float,
        dte: int,
    ) -> float:
        """
        Backward-compatible IV-only expected move.

        Existing Phase 1 and Phase 4 callers can continue using:

            calculate(price, volatility, dte)
        """

        return self.implied_volatility_move(
            underlying_price=underlying_price,
            implied_volatility=volatility,
            horizon_days=dte,
        )

    # ---------------------------------------------------------
    # Source calculations
    # ---------------------------------------------------------

    def implied_volatility_move(
        self,
        underlying_price: float,
        implied_volatility: float,
        horizon_days: int,
    ) -> float:
        price = self._safe_float(underlying_price)
        volatility = self._normalize_volatility(implied_volatility)
        days = max(int(horizon_days or 0), 0)

        if price <= 0 or volatility <= 0 or days <= 0:
            return 0.0

        move = (
            price
            * volatility
            * math.sqrt(days / self.calendar_days)
        )

        return round(move, 4)

    def historical_volatility_move(
        self,
        underlying_price: float,
        historical_volatility: float,
        horizon_days: int,
    ) -> float:
        price = self._safe_float(underlying_price)
        volatility = self._normalize_volatility(
            historical_volatility
        )
        days = max(int(horizon_days or 0), 0)

        if price <= 0 or volatility <= 0 or days <= 0:
            return 0.0

        move = (
            price
            * volatility
            * math.sqrt(days / self.annual_trading_days)
        )

        return round(move, 4)

    def atr_expected_move(
        self,
        atr: float,
        horizon_days: int,
    ) -> float:
        atr = self._safe_float(atr)
        days = max(int(horizon_days or 0), 0)

        if atr <= 0 or days <= 0:
            return 0.0

        if self.atr_scaling_mode == "LINEAR":
            move = atr * days
        else:
            move = atr * math.sqrt(days)

        return round(move, 4)

    def straddle_expected_move(
        self,
        call_price: float,
        put_price: float,
        multiplier: float | None = None,
    ) -> float:
        call_price = self._safe_float(call_price)
        put_price = self._safe_float(put_price)

        multiplier = (
            self.straddle_multiplier
            if multiplier is None
            else float(multiplier)
        )

        if call_price <= 0 or put_price <= 0:
            return 0.0

        return round(
            (call_price + put_price) * multiplier,
            4,
        )

    # ---------------------------------------------------------
    # Main profile API
    # ---------------------------------------------------------

    def analyze(
        self,
        symbol: str,
        underlying_price: float,
        horizon_days: int,
        implied_volatility: float = 0.0,
        historical_volatility: float = 0.0,
        atr: float = 0.0,
        atm_call_price: float = 0.0,
        atm_put_price: float = 0.0,
        custom_weights: dict[str, float] | None = None,
    ) -> ExpectedMoveProfile:
        underlying_price = self._safe_float(underlying_price)
        horizon_days = max(int(horizon_days or 0), 0)

        implied_volatility = self._normalize_volatility(
            implied_volatility
        )

        historical_volatility = self._normalize_volatility(
            historical_volatility
        )

        atr = self._safe_float(atr)

        if underlying_price <= 0:
            raise ValueError(
                "underlying_price must be greater than zero"
            )

        if horizon_days <= 0:
            raise ValueError(
                "horizon_days must be greater than zero"
            )

        iv_move = self.implied_volatility_move(
            underlying_price=underlying_price,
            implied_volatility=implied_volatility,
            horizon_days=horizon_days,
        )

        straddle_move = self.straddle_expected_move(
            call_price=atm_call_price,
            put_price=atm_put_price,
        )

        historical_move = self.historical_volatility_move(
            underlying_price=underlying_price,
            historical_volatility=historical_volatility,
            horizon_days=horizon_days,
        )

        atr_move = self.atr_expected_move(
            atr=atr,
            horizon_days=horizon_days,
        )

        sources = self._build_sources(
            underlying_price=underlying_price,
            horizon_days=horizon_days,
            iv_move=iv_move,
            straddle_move=straddle_move,
            historical_move=historical_move,
            atr_move=atr_move,
            custom_weights=custom_weights,
        )

        blended_move = self._weighted_blend(sources)

        blended_move_pct = (
            blended_move / underlying_price
            if underlying_price > 0
            else 0.0
        )

        available_moves = [
            source.move_dollars
            for source in sources
            if source.available and source.move_dollars > 0
        ]

        source_agreement = (
            self.scoring.source_agreement_score(
                available_moves
            )
        )

        source_count = len(available_moves)

        confidence = self.scoring.confidence_score(
            source_count=source_count,
            agreement_score=source_agreement,
            iv_available=iv_move > 0,
            straddle_available=straddle_move > 0,
            historical_available=historical_move > 0,
            atr_available=atr_move > 0,
        )

        confidence_grade = self.scoring.confidence_grade(
            confidence
        )

        move_regime = self.scoring.classify_move_regime(
            move_pct=blended_move_pct,
            horizon_days=horizon_days,
        )

        expansion_signal = self.scoring.expansion_signal(
            implied_move=iv_move,
            historical_move=historical_move,
            straddle_move=straddle_move,
        )

        dominant_source = self._dominant_source(sources)

        daily_move = self._daily_equivalent(
            blended_move=blended_move,
            horizon_days=horizon_days,
        )

        weekly_move = daily_move * math.sqrt(5.0)
        monthly_move = daily_move * math.sqrt(21.0)

        warnings = self._warnings(
            source_count=source_count,
            agreement_score=source_agreement,
            confidence=confidence,
            blended_move=blended_move,
            underlying_price=underlying_price,
        )

        return ExpectedMoveProfile(
            symbol=symbol,
            underlying_price=round(underlying_price, 4),
            horizon_days=horizon_days,
            implied_volatility=round(
                implied_volatility,
                4,
            ),
            historical_volatility=round(
                historical_volatility,
                4,
            ),
            atr=round(atr, 4),
            iv_move=round(iv_move, 4),
            straddle_move=round(straddle_move, 4),
            historical_move=round(
                historical_move,
                4,
            ),
            atr_move=round(atr_move, 4),
            blended_move=round(blended_move, 4),
            blended_move_pct=round(
                blended_move_pct * 100.0,
                2,
            ),
            lower_bound=round(
                max(
                    underlying_price - blended_move,
                    0.0,
                ),
                4,
            ),
            upper_bound=round(
                underlying_price + blended_move,
                4,
            ),
            lower_bound_2sigma=round(
                max(
                    underlying_price
                    - blended_move * 2.0,
                    0.0,
                ),
                4,
            ),
            upper_bound_2sigma=round(
                underlying_price
                + blended_move * 2.0,
                4,
            ),
            daily_move=round(daily_move, 4),
            weekly_move=round(weekly_move, 4),
            monthly_move=round(monthly_move, 4),
            source_count=source_count,
            source_agreement_score=round(
                source_agreement,
                2,
            ),
            confidence_score=round(confidence, 2),
            confidence_grade=confidence_grade,
            move_regime=move_regime,
            expansion_signal=expansion_signal,
            dominant_source=dominant_source,
            sources=sources,
            warnings=warnings,
        )

    # ---------------------------------------------------------
    # Option-chain analysis
    # ---------------------------------------------------------

    def analyze_from_option_chain(
        self,
        symbol: str,
        underlying_price: float,
        horizon_days: int,
        option_chain,
        implied_volatility: float = 0.0,
        historical_volatility: float = 0.0,
        atr: float = 0.0,
        target_expiry: str | None = None,
    ) -> ExpectedMoveProfile:
        rows = self._rows(option_chain)

        if target_expiry:
            rows = [
                row
                for row in rows
                if str(
                    self._get(row, "expiry", "")
                    or self._get(
                        row,
                        "expiration",
                        "",
                    )
                )
                == str(target_expiry)
            ]

        atm_call, atm_put = self._find_atm_straddle(
            rows=rows,
            underlying_price=underlying_price,
        )

        chain_iv = self._chain_implied_volatility(
            rows=rows,
            underlying_price=underlying_price,
        )

        effective_iv = (
            self._normalize_volatility(
                implied_volatility
            )
            or chain_iv
        )

        return self.analyze(
            symbol=symbol,
            underlying_price=underlying_price,
            horizon_days=horizon_days,
            implied_volatility=effective_iv,
            historical_volatility=historical_volatility,
            atr=atr,
            atm_call_price=atm_call,
            atm_put_price=atm_put,
        )

    def horizon_profiles(
        self,
        symbol: str,
        underlying_price: float,
        horizons: list[int],
        implied_volatility: float = 0.0,
        historical_volatility: float = 0.0,
        atr: float = 0.0,
        atm_call_price: float = 0.0,
        atm_put_price: float = 0.0,
    ) -> list[ExpectedMoveProfile]:
        profiles = []

        for horizon in horizons:
            profiles.append(
                self.analyze(
                    symbol=symbol,
                    underlying_price=underlying_price,
                    horizon_days=horizon,
                    implied_volatility=implied_volatility,
                    historical_volatility=(
                        historical_volatility
                    ),
                    atr=atr,
                    atm_call_price=atm_call_price,
                    atm_put_price=atm_put_price,
                )
            )

        return profiles

    # ---------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------

    def _build_sources(
        self,
        underlying_price: float,
        horizon_days: int,
        iv_move: float,
        straddle_move: float,
        historical_move: float,
        atr_move: float,
        custom_weights: dict[str, float] | None,
    ) -> list[ExpectedMoveSource]:
        weights = dict(self.DEFAULT_WEIGHTS)

        if custom_weights:
            weights.update(custom_weights)

        raw = [
            (
                "ATM_STRADDLE",
                straddle_move,
                weights["ATM_STRADDLE"],
                "ATM call and put premium",
            ),
            (
                "IMPLIED_VOLATILITY",
                iv_move,
                weights["IMPLIED_VOLATILITY"],
                "Annualized implied volatility",
            ),
            (
                "HISTORICAL_VOLATILITY",
                historical_move,
                weights["HISTORICAL_VOLATILITY"],
                "Realized historical volatility",
            ),
            (
                "ATR",
                atr_move,
                weights["ATR"],
                "ATR scaled by square root of time",
            ),
        ]

        sources = []

        for source_name, move, weight, reason in raw:
            available = move is not None and move > 0

            move_pct = (
                move / underlying_price
                if available and underlying_price > 0
                else 0.0
            )

            sources.append(
                ExpectedMoveSource(
                    source=source_name,
                    horizon_days=horizon_days,
                    move_dollars=round(
                        float(move or 0.0),
                        4,
                    ),
                    move_pct=round(
                        move_pct * 100.0,
                        2,
                    ),
                    weight=float(weight),
                    available=available,
                    reason=reason,
                )
            )

        return sources

    def _weighted_blend(
        self,
        sources: list[ExpectedMoveSource],
    ) -> float:
        available = [
            source
            for source in sources
            if source.available
            and source.move_dollars > 0
            and source.weight > 0
        ]

        if not available:
            return 0.0

        total_weight = sum(
            source.weight
            for source in available
        )

        if total_weight <= 0:
            return 0.0

        value = sum(
            source.move_dollars * source.weight
            for source in available
        ) / total_weight

        return round(value, 4)

    def _dominant_source(
        self,
        sources: list[ExpectedMoveSource],
    ) -> str:
        available = [
            source
            for source in sources
            if source.available
        ]

        if not available:
            return "NONE"

        dominant = max(
            available,
            key=lambda source: source.weight,
        )

        return dominant.source

    def _daily_equivalent(
        self,
        blended_move: float,
        horizon_days: int,
    ) -> float:
        if blended_move <= 0 or horizon_days <= 0:
            return 0.0

        return blended_move / math.sqrt(horizon_days)

    def _find_atm_straddle(
        self,
        rows: list,
        underlying_price: float,
    ) -> tuple[float, float]:
        grouped = defaultdict(dict)

        for row in rows:
            strike = self._safe_float(
                self._get(row, "strike", 0.0)
            )

            option_type = str(
                self._get(row, "option_type", "")
                or self._get(row, "type", "")
            ).upper()

            if strike <= 0:
                continue

            grouped[strike][option_type] = row

        complete_strikes = [
            strike
            for strike, contracts in grouped.items()
            if "CALL" in contracts
            and "PUT" in contracts
        ]

        if not complete_strikes:
            return 0.0, 0.0

        atm_strike = min(
            complete_strikes,
            key=lambda strike: abs(
                strike - underlying_price
            ),
        )

        call_row = grouped[atm_strike]["CALL"]
        put_row = grouped[atm_strike]["PUT"]

        return (
            self._mid(call_row),
            self._mid(put_row),
        )

    def _chain_implied_volatility(
        self,
        rows: list,
        underlying_price: float,
    ) -> float:
        iv_rows = []

        for row in rows:
            strike = self._safe_float(
                self._get(row, "strike", 0.0)
            )

            iv = self._normalize_volatility(
                self._get(
                    row,
                    "implied_volatility",
                    self._get(row, "iv", 0.0),
                )
            )

            if strike <= 0 or iv <= 0:
                continue

            distance = (
                abs(strike - underlying_price)
                / underlying_price
                if underlying_price > 0
                else 1.0
            )

            iv_rows.append(
                (distance, iv)
            )

        if not iv_rows:
            return 0.0

        iv_rows.sort(
            key=lambda item: item[0]
        )

        nearest = iv_rows[:4]

        return round(
            sum(iv for _, iv in nearest)
            / len(nearest),
            4,
        )

    def _mid(self, row) -> float:
        mid = self._safe_float(
            self._get(row, "mid", 0.0)
        )

        if mid > 0:
            return mid

        bid = self._safe_float(
            self._get(row, "bid", 0.0)
        )

        ask = self._safe_float(
            self._get(row, "ask", 0.0)
        )

        if bid >= 0 and ask > 0:
            return (bid + ask) / 2.0

        return self._safe_float(
            self._get(row, "last", 0.0)
        )

    def _warnings(
        self,
        source_count: int,
        agreement_score: float,
        confidence: float,
        blended_move: float,
        underlying_price: float,
    ) -> list[str]:
        warnings = []

        if source_count == 0:
            warnings.append(
                "No expected-move sources are available"
            )

        elif source_count == 1:
            warnings.append(
                "Expected move is based on one source only"
            )

        elif source_count == 2:
            warnings.append(
                "Expected move has limited source coverage"
            )

        if agreement_score < 45:
            warnings.append(
                "Expected-move sources disagree materially"
            )

        if confidence < 60:
            warnings.append(
                "Expected-move confidence is low"
            )

        if (
            underlying_price > 0
            and blended_move / underlying_price > 0.50
        ):
            warnings.append(
                "Expected move exceeds 50% of underlying price"
            )

        return warnings

    def _normalize_volatility(
        self,
        value: Any,
    ) -> float:
        volatility = self._safe_float(value)

        if volatility > 3.0:
            volatility /= 100.0

        return max(volatility, 0.0)

    def _rows(self, option_chain) -> list:
        if option_chain is None:
            return []

        if hasattr(option_chain, "to_dict"):
            return option_chain.to_dict("records")

        return list(option_chain)

    def _get(
        self,
        obj,
        key: str,
        default=None,
    ):
        if isinstance(obj, dict):
            return obj.get(key, default)

        return getattr(obj, key, default)

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
