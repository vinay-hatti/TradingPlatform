from trading_ai.scanner.universe_management import (
    SecurityProfile,
    UniverseEngine,
    UniversePolicy,
)


def main() -> None:
    securities = [
        SecurityProfile("AAPL", exchange="NASDAQ", options_eligible=True, source="TEST"),
        SecurityProfile("MSFT", exchange="NASDAQ", options_eligible=True, source="TEST"),
        SecurityProfile(" aapl ", exchange="NASDAQ", source="TEST"),
        SecurityProfile("BAD", exchange="OTC", source="TEST"),
        SecurityProfile("OLD", exchange="NYSE", active=False, source="TEST"),
    ]
    result = UniverseEngine(UniversePolicy(minimum_symbol_count=2)).build(securities)
    assert result.received_count == 5
    assert result.accepted_count == 2
    assert result.rejected_count == 3
    assert result.duplicate_count == 1
    assert result.universe.governance_status == "READY"
    assert [item.symbol for item in result.universe.securities] == ["AAPL", "MSFT"]
    print("Milestone 35 Phase 1 Step 1 universe registry assertions passed.")


if __name__ == "__main__":
    main()
