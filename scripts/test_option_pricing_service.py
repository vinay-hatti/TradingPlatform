from datetime import date

from trading_ai.options.pricing_service import HistoricalOptionPricingService


def main():
    service = HistoricalOptionPricingService(
        min_volume=100,
        min_open_interest=100,
        max_spread_pct=0.20,
    )

    result = service.price(
        underlying_symbol="AAPL",
        quote_date=date(2026, 1, 21),
        option_type="CALL",
        target_strike=300,
        target_dte=30,
    )

    print()
    print("========== Historical Option Pricing Test ==========")

    if not result:
        print("No contract found.")
    else:
        for key, value in result.items():
            print(f"{key:20}: {value}")

    print("====================================================")
    print()


if __name__ == "__main__":
    main()
