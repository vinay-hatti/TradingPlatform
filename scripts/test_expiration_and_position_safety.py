from __future__ import annotations

from trading_ai.daily.expiry_selector import (
    StandardFridayExpirySelector,
)


def main() -> None:
    selection = StandardFridayExpirySelector().select(
        valuation_date="2026-07-17",
        target_dte=30,
    )

    assert selection.expiration_iso == "2026-08-14"
    assert selection.actual_dte == 28
    assert selection.expiration_date.weekday() == 4
    assert selection.source == "STANDARD_FRIDAY_PROXY"

    print(
        "Expiration selection: "
        f"2026-07-17 + target 30 DTE -> "
        f"{selection.expiration_iso} "
        f"({selection.actual_dte} actual DTE)"
    )
    print("All expiration-selector assertions passed.")


if __name__ == "__main__":
    main()
