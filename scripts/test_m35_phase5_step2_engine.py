from datetime import date

from trading_ai.scanner.intermarket_relationships.contracts import (
    IntermarketGovernanceStatus,
)
from trading_ai.scanner.intermarket_relationships.engine import (
    IntermarketRelationshipEngine,
)


def record(value):
    return {
        "return_21d": value,
        "governance_status": "READY",
    }


def main():
    features = {
        "SPY": record(0.08),
        "QQQ": record(0.12),
        "IWM": record(0.10),
        "^VIX": record(-0.15),
        "IEF": record(-0.01),
        "TLT": record(-0.03),
        "LQD": record(0.01),
        "HYG": record(0.04),
        "UUP": record(-0.02),
        "GLD": record(0.01),
        "USO": record(0.02),
    }

    profile = IntermarketRelationshipEngine().evaluate(
        as_of_date=date(2026, 7, 20),
        features_by_symbol=features,
    )

    assert profile.governance_status == IntermarketGovernanceStatus.READY
    assert profile.market_state == "RISK_ON"
    assert profile.risk_on_score > 0
    assert profile.risk_off_score == 0
    assert profile.credit_risk_spread > 0
    assert profile.growth_relative_strength_21d > 0
    assert profile.confidence > 0

    risk_off_features = {
        "SPY": record(-0.08),
        "QQQ": record(-0.12),
        "IWM": record(-0.10),
        "^VIX": record(0.25),
        "IEF": record(0.04),
        "TLT": record(0.08),
        "LQD": record(0.02),
        "HYG": record(-0.05),
        "UUP": record(0.05),
        "GLD": record(0.06),
        "USO": record(-0.08),
    }

    risk_off = IntermarketRelationshipEngine().evaluate(
        as_of_date=date(2026, 7, 20),
        features_by_symbol=risk_off_features,
    )

    assert risk_off.market_state == "RISK_OFF"
    assert risk_off.risk_off_score > 0

    print("Milestone 35 Phase 5 Step 2 engine assertions passed.")


if __name__ == "__main__":
    main()
