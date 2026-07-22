from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.portfolio_management.service import PortfolioRegistryService
from trading_ai.portfolio_management.snapshot_service import PortfolioSnapshotService


with TemporaryDirectory() as tmp:
    root = Path(tmp)
    registry = PortfolioRegistryService(root / "registry.json")
    registry.initialize("Test", 100000)
    service = PortfolioSnapshotService(registry, root / "snapshots", root / "exposure.json", root / "audit.json")
    service.create_snapshot(event_type="DAILY_CLOSE")
    service.create_snapshot(event_type="DAILY_CLOSE")
    history = service.load_audit_history()
    assert len(history.records) == 1
    registry.register_position(
        symbol="SPY", strategy_id="SPY:1", strategy_type="BULL_CALL_SPREAD",
        direction="CALL", quantity=1, entry_price=1, capital_committed=100,
    )
    service.create_snapshot(event_type="DAILY_CLOSE")
    assert len(service.load_audit_history().records) == 2

print("Milestone 36 Phase 1 Step 4 audit-idempotency assertions passed.")
