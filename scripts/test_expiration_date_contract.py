from trading_ai.daily.expiry_selector import StandardFridayExpirySelector

def main():
    result = StandardFridayExpirySelector().select(
        valuation_date="2026-07-17",
        target_dte=30,
    )
    assert result.expiration_iso == "2026-08-14"
    assert result.actual_dte == 28
    assert result.expiration_date.weekday() == 4
    assert result.source == "STANDARD_FRIDAY_PROXY"
    print(
        f"Expiration example: valuation={result.valuation_date}, "
        f"target_dte={result.target_dte}, "
        f"expiration={result.expiration_iso}, "
        f"actual_dte={result.actual_dte}, source={result.source}"
    )
    print("All expiration-date contract assertions passed.")

if __name__ == "__main__":
    main()
