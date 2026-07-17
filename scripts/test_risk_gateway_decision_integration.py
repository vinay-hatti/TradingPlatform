from __future__ import annotations

from dataclasses import dataclass

from trading_ai.risk_gateway.risk_gateway_decision_bridge import (
    RiskGatewayDecisionBridge,
)
from trading_ai.risk_gateway.trading_control_profile import (
    CombinedRiskGatewayDecision,
)


@dataclass(frozen=True)
class CompatibleDecisionResult:
    symbol: str
    risk_gateway_allowed: bool = False
    risk_gateway_score: float = 0.0
    risk_gateway_grade: str = "F"
    risk_gateway_severity: str = "CRITICAL"
    risk_gateway_recommendation: str = "BLOCK"
    risk_gateway_rejection_reasons: tuple[str, ...] = ()
    risk_gateway_warnings: tuple[str, ...] = ()
    risk_gateway_evaluated_at: str = ""


def make_decision(allowed: bool) -> CombinedRiskGatewayDecision:
    return CombinedRiskGatewayDecision(
        valid=True,
        allowed=allowed,
        aggregate_id="agg-001",
        client_order_id="client-001",
        account_id="PAPER-001",
        score=100.0 if allowed else 60.0,
        grade="A" if allowed else "F",
        severity="LOW" if allowed else "CRITICAL",
        recommendation="APPROVE" if allowed else "BLOCK",
        rejection_reasons=() if allowed else (
            "TradingControlDecision:DAILY_TOTAL_LOSS",
        ),
        warnings=("SAMPLE_WARNING",),
        metadata={
            "decision_count": 4,
            "blocking_components": ()
            if allowed
            else ("TradingControlDecision",),
        },
    )


def main() -> None:
    bridge = RiskGatewayDecisionBridge()
    approved = make_decision(True)

    mapped = bridge.apply(
        {"symbol": "AAPL", "recommendation": "TRADE"},
        approved,
    )
    assert mapped["risk_gateway_allowed"] is True
    assert mapped["risk_gateway_score"] == 100.0
    assert mapped["risk_gateway_decision_count"] == 4
    assert mapped["recommendation"] == "TRADE"

    compatible = bridge.apply(
        CompatibleDecisionResult(symbol="AAPL"),
        approved,
    )
    assert compatible.risk_gateway_allowed
    assert compatible.risk_gateway_grade == "A"
    assert compatible.risk_gateway_recommendation == "APPROVE"

    blocked = make_decision(False)
    metadata = bridge.decision_metadata(blocked)
    assert metadata["execution_permitted"] is False
    assert "DAILY_TOTAL_LOSS" in metadata["execution_block_reason"]
    assert (
        metadata["risk_gateway"]["risk_gateway_blocking_components"]
        == ("TradingControlDecision",)
    )

    print("All risk-gateway Decision Engine integration assertions passed.")


if __name__ == "__main__":
    main()
