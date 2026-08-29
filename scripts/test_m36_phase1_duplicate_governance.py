from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.portfolio_management.service import PortfolioRegistryService


def main() -> None:
    with TemporaryDirectory() as directory:
        service = PortfolioRegistryService(Path(directory) / "registry.json")
        service.initialize("Primary", 100000.0)
        kwargs = dict(
            symbol="AAPL",
            strategy_id="AAPL:VERTICAL:1",
            strategy_type="BULL_CALL_SPREAD",
            direction="CALL",
            quantity=1,
            entry_price=2.00,
            capital_committed=200.0,
        )
        service.register_position(**kwargs)
        try:
            service.register_position(**kwargs)
        except ValueError as error:
            assert "duplicate open strategy" in str(error)
        else:
            raise AssertionError("duplicate position was not rejected")
    print("Milestone 36 Phase 1 duplicate-governance assertions passed.")


if __name__ == "__main__":
    main()
