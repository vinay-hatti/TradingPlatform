from trading_ai.scanner.universe_management import (
    SecurityProfile,
    UniverseEngine,
    UniversePolicy,
)


def main() -> None:
    securities = [
        SecurityProfile(
            symbol=f"T{i:04d}",
            exchange="NASDAQ" if i % 2 == 0 else "NYSE",
            options_eligible=(i % 3 == 0),
            source="SCALE_TEST",
        )
        for i in range(6500)
    ]
    result = UniverseEngine(UniversePolicy(minimum_symbol_count=6000)).build(securities)
    assert result.accepted_count == 6500
    assert result.universe.governance_status == "READY"
    assert result.universe.metadata["options_eligible_count"] == 2167
    assert result.universe.securities[0].symbol == "T0000"
    assert result.universe.securities[-1].symbol == "T6499"
    print("Milestone 35 Phase 1 Step 1 6,000+ universe scale assertions passed.")


if __name__ == "__main__":
    main()
