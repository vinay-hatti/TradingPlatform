from __future__ import annotations

from copy import deepcopy
from math import isfinite
from typing import Any, Iterable

from .paper_trade_preparation_profile import (
    PaperTradePreparationPolicy,
    PaperTradePreparationRecord,
    RefreshedStrategyLeg,
)


class PaperTradePreparationService:
    READY = "READY"
    REJECT = "REJECT"

    def prepare(
        self,
        decision_payload: dict[str, Any],
        quote_records: Iterable[dict[str, Any]],
        *,
        policy: PaperTradePreparationPolicy | None = None,
    ) -> PaperTradePreparationRecord:
        active_policy = policy or PaperTradePreparationPolicy()

        symbol = str(decision_payload.get("symbol", "")).strip().upper()
        direction = str(
            decision_payload.get("direction", "")
        ).strip().upper()
        selected = decision_payload.get("selected_strategy")

        if not symbol:
            raise ValueError("Decision payload is missing symbol.")
        if direction not in {"CALL", "PUT"}:
            raise ValueError(
                "Decision payload direction must be CALL or PUT."
            )
        if not isinstance(selected, dict):
            return self._rejected_without_strategy(
                symbol,
                direction,
                decision_payload,
                active_policy,
            )

        quote_index = self._build_quote_index(quote_records)
        refreshed_legs: list[RefreshedStrategyLeg] = []
        rejection_reasons: list[str] = []
        warnings: list[str] = []

        raw_legs = selected.get("legs", [])
        if not isinstance(raw_legs, list) or not raw_legs:
            rejection_reasons.append("SELECTED_STRATEGY_HAS_NO_LEGS")
        else:
            for raw_leg in raw_legs:
                if not isinstance(raw_leg, dict):
                    rejection_reasons.append("INVALID_STRATEGY_LEG")
                    continue
                refreshed = self._refresh_leg(
                    symbol,
                    raw_leg,
                    quote_index,
                    active_policy,
                )
                refreshed_legs.append(refreshed)
                if refreshed.quote_status == "MISSING":
                    rejection_reasons.append("QUOTE_NOT_FOUND")
                elif refreshed.quote_status == "INVALID":
                    rejection_reasons.append("INVALID_BID_ASK")
                elif refreshed.quote_status == "WIDE":
                    rejection_reasons.append("SPREAD_ABOVE_MAXIMUM")

        original_debit = self._optional_number(selected.get("debit"))
        refreshed_debit = self._strategy_debit(refreshed_legs)
        debit_drift_pct = self._debit_drift_pct(
            original_debit,
            refreshed_debit,
        )

        if (
            active_policy.require_complete_quotes
            and any(
                leg.quote_status != "VALID"
                for leg in refreshed_legs
            )
        ):
            rejection_reasons.append("COMPLETE_QUOTES_REQUIRED")

        if (
            active_policy.require_positive_debit
            and (
                refreshed_debit is None
                or refreshed_debit <= 0
            )
        ):
            rejection_reasons.append("POSITIVE_DEBIT_REQUIRED")

        if (
            debit_drift_pct is not None
            and debit_drift_pct > active_policy.max_debit_drift_pct
        ):
            rejection_reasons.append("DEBIT_DRIFT_ABOVE_MAXIMUM")

        metrics = self._recompute_metrics(
            selected,
            refreshed_debit,
        )
        reward_risk = metrics["reward_risk_ratio"]
        if (
            reward_risk is None
            or reward_risk < active_policy.min_reward_risk_ratio
        ):
            rejection_reasons.append("REWARD_RISK_BELOW_MINIMUM")

        rejection_reasons = list(dict.fromkeys(rejection_reasons))
        paper_trade_ready = not rejection_reasons
        decision = self.READY if paper_trade_ready else self.REJECT

        if original_debit is None:
            warnings.append("ORIGINAL_DEBIT_UNAVAILABLE")
        if debit_drift_pct is None:
            warnings.append("DEBIT_DRIFT_UNAVAILABLE")
        if paper_trade_ready:
            warnings.append("EXECUTABLE_QUOTES_VALIDATED")

        paper_trade_payload = (
            self._paper_trade_payload(
                selected,
                refreshed_legs,
                refreshed_debit,
                metrics,
            )
            if paper_trade_ready
            else None
        )

        return PaperTradePreparationRecord(
            symbol=symbol,
            direction=direction,
            strategy_id=self._text(selected.get("strategy_id")),
            strategy_type=self._text(selected.get("strategy_type")),
            decision=decision,
            refreshed_legs=tuple(refreshed_legs),
            original_debit=original_debit,
            refreshed_debit=refreshed_debit,
            debit_drift_pct=debit_drift_pct,
            max_profit=metrics["max_profit"],
            max_loss=metrics["max_loss"],
            breakeven=metrics["breakeven"],
            reward_risk_ratio=reward_risk,
            rejection_reasons=tuple(rejection_reasons),
            warnings=tuple(dict.fromkeys(warnings)),
            paper_trade_ready=paper_trade_ready,
            paper_trade_payload=paper_trade_payload,
            policy=active_policy,
        )

    def _rejected_without_strategy(
        self,
        symbol: str,
        direction: str,
        decision_payload: dict[str, Any],
        policy: PaperTradePreparationPolicy,
    ) -> PaperTradePreparationRecord:
        reasons = ["NO_SELECTED_STRATEGY"]
        if str(decision_payload.get("decision", "")).upper() == "REJECT":
            reasons.append("INSTITUTIONAL_DECISION_REJECTED")
        return PaperTradePreparationRecord(
            symbol=symbol,
            direction=direction,
            strategy_id=None,
            strategy_type=None,
            decision=self.REJECT,
            refreshed_legs=(),
            original_debit=None,
            refreshed_debit=None,
            debit_drift_pct=None,
            max_profit=None,
            max_loss=None,
            breakeven=None,
            reward_risk_ratio=None,
            rejection_reasons=tuple(reasons),
            warnings=(),
            paper_trade_ready=False,
            paper_trade_payload=None,
            policy=policy,
        )

    def _build_quote_index(
        self,
        records: Iterable[dict[str, Any]],
    ) -> dict[tuple[str, str, float, str], dict[str, Any]]:
        index: dict[
            tuple[str, str, float, str],
            dict[str, Any],
        ] = {}
        for payload in records:
            if not isinstance(payload, dict):
                continue
            symbol = self._first_text(
                payload,
                ("underlying_symbol", "symbol", "ticker"),
            )
            expiry = self._first_text(
                payload,
                ("expiry", "expiration", "expiration_date"),
            )
            strike = self._first_number(payload, ("strike",))
            option_type = self._normalize_option_type(
                self._first_text(
                    payload,
                    ("option_type", "type", "right"),
                )
            )
            if (
                symbol
                and expiry
                and strike is not None
                and option_type
            ):
                index[
                    (
                        symbol.upper(),
                        expiry,
                        strike,
                        option_type,
                    )
                ] = payload
        return index

    def _refresh_leg(
        self,
        symbol: str,
        leg: dict[str, Any],
        quote_index: dict[
            tuple[str, str, float, str],
            dict[str, Any],
        ],
        policy: PaperTradePreparationPolicy,
    ) -> RefreshedStrategyLeg:
        expiry = self._text(leg.get("expiry")) or ""
        strike = self._number(leg.get("strike"))
        option_type = self._normalize_option_type(
            self._text(leg.get("option_type"))
        )
        action = (self._text(leg.get("action")) or "").upper()
        quantity = int(self._number(leg.get("quantity")) or 1)

        quote = quote_index.get(
            (symbol, expiry, strike, option_type)
        )
        if quote is None:
            return RefreshedStrategyLeg(
                symbol=symbol,
                expiry=expiry,
                strike=strike,
                option_type=option_type,
                action=action,
                quantity=quantity,
                bid=None,
                ask=None,
                last=None,
                mid=None,
                spread_pct=None,
                quote_status="MISSING",
            )

        bid = self._first_number(quote, ("bid",))
        ask = self._first_number(quote, ("ask",))
        last = self._first_number(
            quote,
            ("last", "last_price"),
        )
        mid = (
            (bid + ask) / 2.0
            if bid is not None and ask is not None
            else None
        )
        spread_pct = self._spread_pct(bid, ask)

        if spread_pct is None:
            status = "INVALID"
        elif spread_pct > policy.max_spread_pct:
            status = "WIDE"
        else:
            status = "VALID"

        return RefreshedStrategyLeg(
            symbol=symbol,
            expiry=expiry,
            strike=strike,
            option_type=option_type,
            action=action,
            quantity=quantity,
            bid=bid,
            ask=ask,
            last=last,
            mid=mid,
            spread_pct=spread_pct,
            quote_status=status,
            source=self._first_text(
                quote,
                ("source", "provider"),
            ),
        )

    def _strategy_debit(
        self,
        legs: list[RefreshedStrategyLeg],
    ) -> float | None:
        if not legs or any(
            leg.quote_status != "VALID" for leg in legs
        ):
            return None
        debit = 0.0
        for leg in legs:
            if leg.action == "BUY":
                if leg.ask is None:
                    return None
                debit += leg.ask * leg.quantity
            elif leg.action == "SELL":
                if leg.bid is None:
                    return None
                debit -= leg.bid * leg.quantity
            else:
                return None
        return round(debit, 8)

    def _debit_drift_pct(
        self,
        original: float | None,
        refreshed: float | None,
    ) -> float | None:
        if (
            original is None
            or refreshed is None
            or original <= 0
        ):
            return None
        return abs(refreshed - original) / original

    def _recompute_metrics(
        self,
        selected: dict[str, Any],
        debit: float | None,
    ) -> dict[str, float | None]:
        strategy_type = str(
            selected.get("strategy_type", "")
        ).upper()
        legs = selected.get("legs", [])
        direction = str(
            selected.get("direction", "")
        ).upper()

        max_profit: float | None = None
        max_loss: float | None = debit
        breakeven: float | None = None
        reward_risk: float | None = None

        strikes = [
            self._number(leg.get("strike"))
            for leg in legs
            if isinstance(leg, dict)
        ]

        if debit is not None and strikes:
            long_strike = next(
                (
                    self._number(leg.get("strike"))
                    for leg in legs
                    if isinstance(leg, dict)
                    and str(
                        leg.get("action", "")
                    ).upper()
                    == "BUY"
                ),
                strikes[0],
            )

            if "SPREAD" in strategy_type and len(strikes) >= 2:
                width = max(strikes) - min(strikes)
                max_profit = max(0.0, width - debit)
                reward_risk = (
                    max_profit / debit
                    if debit > 0
                    else None
                )

            if direction == "CALL":
                breakeven = long_strike + debit
            elif direction == "PUT":
                breakeven = long_strike - debit

        return {
            "max_profit": max_profit,
            "max_loss": max_loss,
            "breakeven": breakeven,
            "reward_risk_ratio": reward_risk,
        }

    def _paper_trade_payload(
        self,
        selected: dict[str, Any],
        legs: list[RefreshedStrategyLeg],
        debit: float | None,
        metrics: dict[str, float | None],
    ) -> dict[str, Any]:
        return {
            "strategy_id": selected.get("strategy_id"),
            "symbol": selected.get("symbol"),
            "direction": selected.get("direction"),
            "strategy_type": selected.get("strategy_type"),
            "expiry": selected.get("expiry"),
            "legs": [leg.to_dict() for leg in legs],
            "limit_debit": debit,
            "max_profit": metrics["max_profit"],
            "max_loss": metrics["max_loss"],
            "breakeven": metrics["breakeven"],
            "reward_risk_ratio": metrics[
                "reward_risk_ratio"
            ],
            "execution_status": "READY_FOR_PAPER_TRADE",
        }

    def _spread_pct(
        self,
        bid: float | None,
        ask: float | None,
    ) -> float | None:
        if bid is None or ask is None or ask < bid:
            return None
        mid = (bid + ask) / 2.0
        if mid <= 0:
            return None
        return (ask - bid) / mid

    def _first_text(
        self,
        payload: dict[str, Any],
        aliases: tuple[str, ...],
    ) -> str | None:
        for alias in aliases:
            value = payload.get(alias)
            if value not in (None, ""):
                return str(value).strip()
        return None

    def _first_number(
        self,
        payload: dict[str, Any],
        aliases: tuple[str, ...],
    ) -> float | None:
        for alias in aliases:
            value = self._optional_number(payload.get(alias))
            if value is not None:
                return value
        return None

    def _normalize_option_type(
        self,
        value: str | None,
    ) -> str:
        normalized = (value or "").strip().upper()
        if normalized in {"C", "CALL"}:
            return "CALL"
        if normalized in {"P", "PUT"}:
            return "PUT"
        return normalized

    def _text(self, value: Any) -> str | None:
        if value in (None, ""):
            return None
        return str(value).strip()

    def _optional_number(
        self,
        value: Any,
    ) -> float | None:
        if value in (None, ""):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if isfinite(number) else None

    def _number(self, value: Any) -> float:
        return self._optional_number(value) or 0.0
