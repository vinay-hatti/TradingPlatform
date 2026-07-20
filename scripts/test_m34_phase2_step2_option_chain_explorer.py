from datetime import date
from types import SimpleNamespace

from trading_ai.research_workstation.analysis import (
    OptionChainExplorerEngine,
    option_chain_explorer_payload,
)


def contract(expiry, strike, option_type, bid, ask, volume, oi, iv, delta):
    return SimpleNamespace(
        underlying_symbol="AAA",
        expiry=expiry,
        strike=strike,
        option_type=option_type,
        bid=bid,
        ask=ask,
        last=(bid + ask) / 2,
        volume=volume,
        open_interest=oi,
        implied_volatility=iv,
        delta=delta,
        gamma=0.03,
        theta=-0.08,
        vega=0.12,
    )


def main() -> None:
    contracts = [
        contract(date(2026, 8, 21), 95, "CALL", 6.00, 6.20, 900, 4000, 0.30, 0.70),
        contract(date(2026, 8, 21), 100, "CALL", 3.00, 3.10, 2000, 9000, 0.28, 0.52),
        contract(date(2026, 8, 21), 100, "PUT", 2.80, 2.90, 1800, 8500, 0.29, -0.48),
        contract(date(2026, 9, 18), 100, "CALL", 4.70, 5.10, 500, 2500, 0.31, 0.53),
        contract(date(2026, 9, 18), 100, "PUT", 4.50, 4.90, 450, 2200, 0.32, -0.47),
    ]

    profile = OptionChainExplorerEngine().analyze(
        symbol="AAA",
        underlying_price=100.0,
        contracts=contracts,
        quote_date=date(2026, 7, 19),
    )

    assert profile.symbol == "AAA", profile
    assert profile.contract_count == 5, profile
    assert profile.expiration_count == 2, profile
    assert profile.preferred_expiration == date(2026, 8, 21), profile
    assert profile.expirations[0].preferred is True
    assert profile.expirations[0].quality_grade in {"A", "B"}
    assert profile.contracts[0].expiration == date(2026, 8, 21)
    assert any(
        item.moneyness == "ATM" for item in profile.contracts
    )
    assert all(item.contract_score >= 0 for item in profile.contracts)

    payload = option_chain_explorer_payload(profile)
    assert payload["symbol"] == "AAA"
    assert payload["preferred_expiration"] == "2026-08-21"
    assert payload["expirations"][0]["preferred"] is True

    print(
        "All Milestone 34 Phase 2 Step 2 option-chain explorer "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
