from __future__ import annotations

from math import isfinite
from typing import Any, Iterable

from .strategy_comparison_profile import (
    StrategyCandidate,
    StrategyComparisonProfile,
    StrategyLeg,
)


class StrategyComparisonService:
    def compare(
        self,
        option_chain_payload: dict[str, Any],
        *,
        direction: str,
        max_candidates: int = 20,
        min_open_interest: int = 0,
        min_volume: int = 0,
    ) -> StrategyComparisonProfile:
        symbol = str(option_chain_payload.get("symbol", "")).strip().upper()
        normalized_direction = direction.strip().upper()
        if normalized_direction not in {"CALL", "PUT"}:
            raise ValueError("Direction must be CALL or PUT.")
        if not symbol:
            raise ValueError("Option-chain payload is missing symbol.")

        source_key = "calls" if normalized_direction == "CALL" else "puts"
        raw_contracts = option_chain_payload.get(source_key, [])
        if not isinstance(raw_contracts, list):
            raise ValueError(
                f"Option-chain payload field '{source_key}' must be a list."
            )

        contracts = [
            item
            for item in raw_contracts
            if isinstance(item, dict)
            and self._integer(item.get("volume")) >= min_volume
            and self._integer(item.get("open_interest")) >= min_open_interest
        ]
        contracts.sort(
            key=lambda item: (
                str(item.get("expiry", "")),
                self._number(item.get("strike")),
            )
        )

        strategies: list[StrategyCandidate] = []
        for contract in contracts:
            strategies.append(
                self._single_leg_candidate(
                    symbol,
                    normalized_direction,
                    contract,
                )
            )

        by_expiry: dict[str, list[dict[str, Any]]] = {}
        for contract in contracts:
            by_expiry.setdefault(str(contract.get("expiry", "")), []).append(
                contract
            )

        for expiry, expiry_contracts in by_expiry.items():
            expiry_contracts.sort(key=lambda item: self._number(item.get("strike")))
            for index in range(len(expiry_contracts) - 1):
                lower = expiry_contracts[index]
                upper = expiry_contracts[index + 1]
                if normalized_direction == "CALL":
                    strategies.append(
                        self._vertical_candidate(
                            symbol=symbol,
                            expiry=expiry,
                            direction=normalized_direction,
                            long_leg=lower,
                            short_leg=upper,
                        )
                    )
                else:
                    strategies.append(
                        self._vertical_candidate(
                            symbol=symbol,
                            expiry=expiry,
                            direction=normalized_direction,
                            long_leg=upper,
                            short_leg=lower,
                        )
                    )

        ranked = sorted(
            strategies,
            key=lambda item: (
                item.institutional_score,
                item.reward_risk_ratio
                if item.reward_risk_ratio is not None
                else -1.0,
            ),
            reverse=True,
        )[:max_candidates]

        warnings: list[str] = []
        if not contracts:
            warnings.append("NO_DIRECTIONAL_CONTRACTS_AVAILABLE")
        if any(item.quote_quality != "COMPLETE" for item in ranked):
            warnings.append("ONE_OR_MORE_STRATEGIES_USE_INCOMPLETE_QUOTES")
        if option_chain_payload.get("quote_policy") == (
            "HISTORICAL_ALLOW_MISSING_QUOTES"
        ):
            warnings.append("HISTORICAL_QUOTE_POLICY_ACTIVE")

        return StrategyComparisonProfile(
            symbol=symbol,
            direction=normalized_direction,
            source_contracts=len(contracts),
            generated_strategies=len(strategies),
            ranked_strategies=tuple(ranked),
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def _single_leg_candidate(
        self,
        symbol: str,
        direction: str,
        contract: dict[str, Any],
    ) -> StrategyCandidate:
        expiry = str(contract.get("expiry", ""))
        strike = self._number(contract.get("strike"))
        ask = self._optional_number(contract.get("ask"))
        last = self._optional_number(contract.get("last"))
        entry = ask if ask is not None else last
        quote_quality = (
            "COMPLETE"
            if self._optional_number(contract.get("bid")) is not None
            and ask is not None
            else "HISTORICAL_LAST_ONLY"
            if last is not None
            else "MISSING"
        )
        warnings: list[str] = []
        if quote_quality != "COMPLETE":
            warnings.append("INCOMPLETE_ENTRY_QUOTE")

        probability = self._probability_proxy(
            direction,
            self._optional_number(contract.get("delta")),
        )
        liquidity = self._liquidity_score(contract)
        institutional_score = self._institutional_score(
            probability=probability,
            liquidity=liquidity,
            reward_risk=None,
            quote_quality=quote_quality,
        )

        leg = StrategyLeg(
            symbol=symbol,
            expiry=expiry,
            strike=strike,
            option_type=direction,
            action="BUY",
            ask=ask,
            bid=self._optional_number(contract.get("bid")),
            last=last,
            delta=self._optional_number(contract.get("delta")),
            implied_volatility=self._optional_number(
                contract.get("implied_volatility")
            ),
        )
        return StrategyCandidate(
            strategy_id=f"{symbol}:{expiry}:{direction}:{strike}:LONG",
            symbol=symbol,
            expiry=expiry,
            direction=direction,
            strategy_type=f"LONG_{direction}",
            legs=(leg,),
            debit=entry,
            max_loss=entry,
            breakeven=(
                strike + entry
                if direction == "CALL" and entry is not None
                else strike - entry
                if direction == "PUT" and entry is not None
                else None
            ),
            probability_proxy=probability,
            liquidity_score=liquidity,
            institutional_score=institutional_score,
            quote_quality=quote_quality,
            warnings=tuple(warnings),
        )

    def _vertical_candidate(
        self,
        *,
        symbol: str,
        expiry: str,
        direction: str,
        long_leg: dict[str, Any],
        short_leg: dict[str, Any],
    ) -> StrategyCandidate:
        long_strike = self._number(long_leg.get("strike"))
        short_strike = self._number(short_leg.get("strike"))
        width = abs(short_strike - long_strike)

        long_entry = self._entry_price(long_leg)
        short_entry = self._exit_price(short_leg)
        debit = (
            long_entry - short_entry
            if long_entry is not None and short_entry is not None
            else None
        )
        if debit is not None and debit < 0:
            debit = None

        max_profit = (
            width - debit
            if debit is not None and width >= debit
            else None
        )
        max_loss = debit
        reward_risk = (
            max_profit / max_loss
            if max_profit is not None and max_loss not in (None, 0)
            else None
        )
        breakeven = (
            long_strike + debit
            if direction == "CALL" and debit is not None
            else long_strike - debit
            if direction == "PUT" and debit is not None
            else None
        )

        quote_quality = self._combined_quote_quality(long_leg, short_leg)
        warnings: list[str] = []
        if quote_quality != "COMPLETE":
            warnings.append("INCOMPLETE_SPREAD_QUOTES")
        if debit is None:
            warnings.append("UNPRICED_STRATEGY")

        probability = self._probability_proxy(
            direction,
            self._optional_number(long_leg.get("delta")),
        )
        liquidity = min(
            self._liquidity_score(long_leg),
            self._liquidity_score(short_leg),
        )
        score = self._institutional_score(
            probability=probability,
            liquidity=liquidity,
            reward_risk=reward_risk,
            quote_quality=quote_quality,
        )

        return StrategyCandidate(
            strategy_id=(
                f"{symbol}:{expiry}:{direction}:"
                f"{long_strike}-{short_strike}:VERTICAL"
            ),
            symbol=symbol,
            expiry=expiry,
            direction=direction,
            strategy_type=(
                "BULL_CALL_SPREAD"
                if direction == "CALL"
                else "BEAR_PUT_SPREAD"
            ),
            legs=(
                StrategyLeg(
                    symbol=symbol,
                    expiry=expiry,
                    strike=long_strike,
                    option_type=direction,
                    action="BUY",
                    bid=self._optional_number(long_leg.get("bid")),
                    ask=self._optional_number(long_leg.get("ask")),
                    last=self._optional_number(long_leg.get("last")),
                    delta=self._optional_number(long_leg.get("delta")),
                    implied_volatility=self._optional_number(
                        long_leg.get("implied_volatility")
                    ),
                ),
                StrategyLeg(
                    symbol=symbol,
                    expiry=expiry,
                    strike=short_strike,
                    option_type=direction,
                    action="SELL",
                    bid=self._optional_number(short_leg.get("bid")),
                    ask=self._optional_number(short_leg.get("ask")),
                    last=self._optional_number(short_leg.get("last")),
                    delta=self._optional_number(short_leg.get("delta")),
                    implied_volatility=self._optional_number(
                        short_leg.get("implied_volatility")
                    ),
                ),
            ),
            debit=debit,
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven=breakeven,
            reward_risk_ratio=reward_risk,
            probability_proxy=probability,
            liquidity_score=liquidity,
            institutional_score=score,
            quote_quality=quote_quality,
            warnings=tuple(warnings),
            metadata={"width": width},
        )

    def _entry_price(self, contract: dict[str, Any]) -> float | None:
        return self._optional_number(contract.get("ask")) or self._optional_number(
            contract.get("last")
        )

    def _exit_price(self, contract: dict[str, Any]) -> float | None:
        return self._optional_number(contract.get("bid")) or self._optional_number(
            contract.get("last")
        )

    def _combined_quote_quality(
        self,
        long_leg: dict[str, Any],
        short_leg: dict[str, Any],
    ) -> str:
        complete = all(
            self._optional_number(contract.get(field)) is not None
            for contract, field in (
                (long_leg, "ask"),
                (short_leg, "bid"),
            )
        )
        if complete:
            return "COMPLETE"
        if all(
            self._optional_number(contract.get("last")) is not None
            for contract in (long_leg, short_leg)
        ):
            return "HISTORICAL_LAST_ONLY"
        return "MISSING"

    def _probability_proxy(
        self,
        direction: str,
        delta: float | None,
    ) -> float | None:
        if delta is None:
            return None
        probability = abs(delta)
        return max(0.0, min(1.0, probability))

    def _liquidity_score(self, contract: dict[str, Any]) -> float:
        volume = self._integer(contract.get("volume"))
        open_interest = self._integer(contract.get("open_interest"))
        volume_component = min(volume / 1000.0, 1.0)
        oi_component = min(open_interest / 5000.0, 1.0)
        return round((volume_component * 40.0) + (oi_component * 60.0), 4)

    def _institutional_score(
        self,
        *,
        probability: float | None,
        liquidity: float,
        reward_risk: float | None,
        quote_quality: str,
    ) -> float:
        probability_score = (probability or 0.0) * 45.0
        liquidity_score = (liquidity / 100.0) * 35.0
        reward_score = (
            min(max(reward_risk, 0.0), 3.0) / 3.0 * 20.0
            if reward_risk is not None
            else 0.0
        )
        quote_penalty = {
            "COMPLETE": 0.0,
            "HISTORICAL_LAST_ONLY": 12.5,
            "MISSING": 25.0,
        }.get(quote_quality, 25.0)
        return round(
            max(
                0.0,
                probability_score
                + liquidity_score
                + reward_score
                - quote_penalty,
            ),
            4,
        )

    def _optional_number(self, value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if isfinite(number) else None

    def _number(self, value: Any) -> float:
        return self._optional_number(value) or 0.0

    def _integer(self, value: Any) -> int:
        number = self._optional_number(value)
        return int(number) if number is not None else 0
