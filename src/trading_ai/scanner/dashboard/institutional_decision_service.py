from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any

from .institutional_decision_profile import (
    InstitutionalDecisionPolicy,
    InstitutionalDecisionRecord,
)


class InstitutionalDecisionHandoffService:
    APPROVE = "APPROVE"
    REJECT = "REJECT"

    def evaluate(
        self,
        strategy_comparison_payload: dict[str, Any],
        *,
        policy: InstitutionalDecisionPolicy | None = None,
    ) -> InstitutionalDecisionRecord:
        active_policy = policy or InstitutionalDecisionPolicy()

        symbol = str(
            strategy_comparison_payload.get("symbol", "")
        ).strip().upper()
        direction = str(
            strategy_comparison_payload.get("direction", "")
        ).strip().upper()
        ranked = strategy_comparison_payload.get(
            "ranked_strategies",
            [],
        )

        if not symbol:
            raise ValueError(
                "Strategy-comparison payload is missing symbol."
            )
        if direction not in {"CALL", "PUT"}:
            raise ValueError(
                "Strategy-comparison payload direction must be CALL or PUT."
            )
        if not isinstance(ranked, list):
            raise ValueError(
                "ranked_strategies must be a list."
            )

        approved: list[dict[str, Any]] = []
        rejection_reasons: Counter[str] = Counter()

        for candidate in ranked:
            if not isinstance(candidate, dict):
                rejection_reasons["INVALID_CANDIDATE_PAYLOAD"] += 1
                continue

            reasons = self._candidate_rejections(
                candidate,
                active_policy,
            )
            if reasons:
                rejection_reasons.update(reasons)
            else:
                approved.append(candidate)

        approved.sort(
            key=lambda item: (
                self._number(item.get("institutional_score")),
                self._number(item.get("reward_risk_ratio")),
                self._number(item.get("liquidity_score")),
            ),
            reverse=True,
        )

        selected = deepcopy(approved[0]) if approved else None
        decision = self.APPROVE if selected else self.REJECT
        warnings: list[str] = []

        comparison_warnings = strategy_comparison_payload.get(
            "warnings",
            [],
        )
        if isinstance(comparison_warnings, list):
            warnings.extend(str(item) for item in comparison_warnings)

        if selected:
            quote_quality = str(
                selected.get("quote_quality", "UNKNOWN")
            ).upper()
            if quote_quality != "COMPLETE":
                warnings.append("SELECTED_STRATEGY_HAS_INCOMPLETE_QUOTES")
        else:
            warnings.append("NO_STRATEGY_PASSED_INSTITUTIONAL_POLICY")

        paper_trade_ready = bool(
            selected
            and str(
                selected.get("quote_quality", "UNKNOWN")
            ).upper()
            == "COMPLETE"
        )
        paper_trade_payload = (
            self._paper_trade_payload(selected)
            if selected
            else None
        )

        if selected and not paper_trade_ready:
            warnings.append("QUOTE_REFRESH_REQUIRED_BEFORE_PAPER_TRADE")

        return InstitutionalDecisionRecord(
            symbol=symbol,
            direction=direction,
            decision=decision,
            selected_strategy_id=(
                str(selected.get("strategy_id"))
                if selected
                else None
            ),
            selected_strategy=selected,
            approved_candidates=len(approved),
            rejected_candidates=max(0, len(ranked) - len(approved)),
            rejection_summary=dict(sorted(rejection_reasons.items())),
            warnings=tuple(dict.fromkeys(warnings)),
            policy=active_policy,
            paper_trade_ready=paper_trade_ready,
            paper_trade_payload=paper_trade_payload,
        )

    def _candidate_rejections(
        self,
        candidate: dict[str, Any],
        policy: InstitutionalDecisionPolicy,
    ) -> list[str]:
        reasons: list[str] = []

        if self._number(
            candidate.get("institutional_score")
        ) < policy.min_institutional_score:
            reasons.append("INSTITUTIONAL_SCORE_BELOW_MINIMUM")

        if self._number(
            candidate.get("liquidity_score")
        ) < policy.min_liquidity_score:
            reasons.append("LIQUIDITY_SCORE_BELOW_MINIMUM")

        probability = self._optional_number(
            candidate.get("probability_proxy")
        )
        if (
            probability is None
            or probability < policy.min_probability_proxy
        ):
            reasons.append("PROBABILITY_PROXY_BELOW_MINIMUM")

        reward_risk = self._optional_number(
            candidate.get("reward_risk_ratio")
        )
        strategy_type = str(
            candidate.get("strategy_type", "")
        ).upper()

        if policy.require_defined_risk:
            max_loss = self._optional_number(
                candidate.get("max_loss")
            )
            if max_loss is None or max_loss <= 0:
                reasons.append("DEFINED_MAX_LOSS_REQUIRED")

        if "SPREAD" in strategy_type:
            if (
                reward_risk is None
                or reward_risk < policy.min_reward_risk_ratio
            ):
                reasons.append("REWARD_RISK_BELOW_MINIMUM")

        quote_quality = str(
            candidate.get("quote_quality", "UNKNOWN")
        ).upper()
        if (
            quote_quality != "COMPLETE"
            and not policy.allow_historical_quotes
        ):
            reasons.append("COMPLETE_QUOTES_REQUIRED")

        warnings = candidate.get("warnings", [])
        if (
            isinstance(warnings, list)
            and "UNPRICED_STRATEGY" in warnings
            and not policy.allow_unpriced_strategies
        ):
            reasons.append("UNPRICED_STRATEGY_NOT_ALLOWED")

        return reasons

    def _paper_trade_payload(
        self,
        selected: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "strategy_id": selected.get("strategy_id"),
            "symbol": selected.get("symbol"),
            "direction": selected.get("direction"),
            "strategy_type": selected.get("strategy_type"),
            "expiry": selected.get("expiry"),
            "legs": deepcopy(selected.get("legs", [])),
            "estimated_debit": selected.get("debit"),
            "estimated_credit": selected.get("credit"),
            "max_profit": selected.get("max_profit"),
            "max_loss": selected.get("max_loss"),
            "breakeven": selected.get("breakeven"),
            "reward_risk_ratio": selected.get(
                "reward_risk_ratio"
            ),
            "institutional_score": selected.get(
                "institutional_score"
            ),
            "quote_quality": selected.get("quote_quality"),
            "execution_status": (
                "READY"
                if str(
                    selected.get("quote_quality", "")
                ).upper()
                == "COMPLETE"
                else "QUOTE_REFRESH_REQUIRED"
            ),
        }

    def _optional_number(self, value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _number(self, value: Any) -> float:
        return self._optional_number(value) or 0.0
