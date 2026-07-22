from datetime import date

from trading_ai.scanner.historical_options_feature_store.contracts import (
    FeatureGovernanceStatus,
)
from trading_ai.scanner.historical_options_feature_store.engine import (
    HistoricalOptionFeatureEngine,
    HistoricalOptionInput,
)


def make(readiness="READY", *, oi=100, iv=0.25, delta=0.5):
    return HistoricalOptionInput(
        underlying_symbol="AAPL",
        quote_date=date(2026, 7, 20),
        expiry=date(2026, 8, 21),
        option_type="CALL",
        strike=200.0,
        underlying_price=210.0,
        last_price=15.0,
        volume=50,
        open_interest=oi,
        implied_volatility=iv,
        delta=delta,
        gamma=0.02,
        theta=-0.05,
        vega=0.10,
        readiness_status=readiness,
    )


def main():
    engine = HistoricalOptionFeatureEngine()
    ready, failed_readiness, failed_oi = engine.build(
        (
            make(),
            make(readiness="FAILED"),
            make(oi=0),
        )
    )

    assert ready.governance_status == FeatureGovernanceStatus.READY
    assert ready.days_to_expiration == 32
    assert ready.moneyness == round(200.0 / 210.0, 8)
    assert ready.intrinsic_value == 10.0
    assert ready.extrinsic_value == 5.0

    assert (
        failed_readiness.governance_status
        == FeatureGovernanceStatus.EXCLUDED
    )
    assert failed_oi.governance_status == FeatureGovernanceStatus.EXCLUDED

    print("Milestone 35 Phase 4 Step 1 engine assertions passed.")


if __name__ == "__main__":
    main()
