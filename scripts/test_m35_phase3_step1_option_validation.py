from datetime import date

from trading_ai.scanner.options_market_data_quality import (
    OptionContractIdentity,
    OptionContractValidationEngine,
    OptionQuoteRecord,
    OptionSide,
)


def main() -> None:
    engine = OptionContractValidationEngine()

    valid = OptionQuoteRecord(
        identity=OptionContractIdentity(
            underlying_symbol="AAPL",
            expiration_date=date(2026, 8, 21),
            strike=250.0,
            option_side=OptionSide.CALL,
        ),
        quote_date=date(2026, 7, 20),
        bid=5.1,
        ask=5.4,
        volume=200,
        open_interest=1000,
        implied_volatility=0.35,
        delta=0.45,
        gamma=0.02,
        theta=-0.08,
        vega=0.15,
    )
    result = engine.evaluate(valid)
    assert result.valid
    assert result.error_count == 0

    invalid = OptionQuoteRecord(
        identity=OptionContractIdentity(
            underlying_symbol="AAPL",
            expiration_date=date(2026, 7, 17),
            strike=-1.0,
            option_side=OptionSide.PUT,
        ),
        quote_date=date(2026, 7, 20),
        bid=5.0,
        ask=4.0,
        volume=-1,
        open_interest=-2,
        implied_volatility=-0.5,
        delta=2.0,
    )
    result = engine.evaluate(invalid)
    assert not result.valid
    assert result.error_count >= 6
    codes = {issue.code for issue in result.issues}
    assert "INVALID_STRIKE" in codes
    assert "EXPIRED_CONTRACT" in codes
    assert "CROSSED_MARKET" in codes

    print("Milestone 35 Phase 3 Step 1 option validation assertions passed.")


if __name__ == "__main__":
    main()
