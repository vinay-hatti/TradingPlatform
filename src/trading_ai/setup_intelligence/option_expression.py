from __future__ import annotations


class ShadowOptionExpressionAdvisor:
    """Non-authoritative setup-aware option-expression guidance.

    It deliberately returns strategy families, not contracts or orders. Existing
    Institutional Options remains the sole production strategy/contract authority.
    """
    version = "M78-SHADOW-OPTION-EXPRESSION-1.0"

    _MAP = {
        "TREND_PULLBACK": ("LONG_CALL_OR_PUT", "VERTICAL_DEBIT", "DIAGONAL"),
        "TREND_CONTINUATION": ("LONG_CALL_OR_PUT", "VERTICAL_DEBIT", "DIAGONAL"),
        "MOMENTUM_ACCELERATION": ("LONG_CALL_OR_PUT", "VERTICAL_DEBIT"),
        "BREAKOUT_SETUP": ("WAIT_FOR_CONFIRMATION",),
        "BREAKOUT_CONFIRMED": ("LONG_CALL", "BULL_CALL_SPREAD"),
        "BREAKOUT_RETEST": ("LONG_CALL", "BULL_CALL_SPREAD", "CALL_DIAGONAL"),
        "BREAKOUT_CONTINUATION": ("LONG_CALL", "BULL_CALL_SPREAD"),
        "BREAKDOWN_SETUP": ("WAIT_FOR_CONFIRMATION",),
        "BREAKDOWN_CONFIRMED": ("LONG_PUT", "BEAR_PUT_SPREAD"),
        "BREAKDOWN_RETEST": ("LONG_PUT", "BEAR_PUT_SPREAD", "PUT_DIAGONAL"),
        "BREAKDOWN_CONTINUATION": ("LONG_PUT", "BEAR_PUT_SPREAD"),
        "FAILED_BREAKOUT_REVERSAL": ("LONG_PUT", "BEAR_PUT_SPREAD"),
        "FAILED_BREAKDOWN_REVERSAL": ("LONG_CALL", "BULL_CALL_SPREAD"),
        "SUPPORT_REVERSAL": ("LONG_CALL", "BULL_CALL_SPREAD", "CALL_DIAGONAL"),
        "RESISTANCE_REVERSAL": ("LONG_PUT", "BEAR_PUT_SPREAD", "PUT_DIAGONAL"),
        "POST_EARNINGS_DRIFT_LONG": ("LONG_CALL", "BULL_CALL_SPREAD", "CALL_DIAGONAL"),
        "POST_EARNINGS_DRIFT_SHORT": ("LONG_PUT", "BEAR_PUT_SPREAD", "PUT_DIAGONAL"),
    }

    def advise(self, setup_type: str, *, probability_status: str, expected_holding_days: float | None = None) -> dict:
        families = list(self._MAP.get(str(setup_type), ("NO_SHADOW_GUIDANCE",)))
        if probability_status != "READY":
            return {"status": "INSUFFICIENT_EVIDENCE", "strategy_families": ["NO_TRADE_RESEARCH_ONLY"],
                    "reason": "setup probability is not READY", "authority_effect": False}
        return {"status": "SHADOW_GUIDANCE", "strategy_families": families,
                "expected_holding_days": expected_holding_days, "authority_effect": False,
                "production_strategy_selection_unchanged": True}
