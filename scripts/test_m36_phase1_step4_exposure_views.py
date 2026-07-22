from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.portfolio_management.service import PortfolioRegistryService
from trading_ai.portfolio_management.snapshot_service import PortfolioSnapshotService


with TemporaryDirectory() as tmp:
    root = Path(tmp)
    registry = PortfolioRegistryService(root / "registry.json")
    registry.initialize("Test", 100000)
    registry.register_position(
        symbol="AAPL", strategy_id="AAPL:1", strategy_type="BULL_CALL_SPREAD",
        direction="CALL", quantity=1, entry_price=2, capital_committed=200,
        sector="TECHNOLOGY",
    )
    registry.register_position(
        symbol="MSFT", strategy_id="MSFT:1", strategy_type="BULL_CALL_SPREAD",
        direction="CALL", quantity=1, entry_price=3, capital_committed=300,
        sector="TECHNOLOGY",
    )
    service = PortfolioSnapshotService(registry, root / "snapshots", root / "exposure.json", root / "audit.json")
    view = service.build_exposure_view()
    assert view.open_position_count == 2
    assert view.capital_committed == 500
    assert view.by_sector[0].capital_committed == 500
    assert view.by_sector[0].capital_pct == 100.0
    assert view.largest_sector_pct == 100.0
    assert "SECTOR_CONCENTRATION_ABOVE_40_PCT" in view.warnings
    assert view.largest_symbol_pct == 60.0

print("Milestone 36 Phase 1 Step 4 exposure-view assertions passed.")
