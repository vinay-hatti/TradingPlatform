from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.portfolio_management.service import PortfolioRegistryService
from trading_ai.portfolio_management.snapshot_service import PortfolioSnapshotService


with TemporaryDirectory() as tmp:
    root = Path(tmp)
    registry = PortfolioRegistryService(root / "registry.json")
    registry.initialize("Test", 100000)
    registry.register_position(
        symbol="AMZN",
        strategy_id="AMZN:CALL:VERTICAL",
        strategy_type="BULL_CALL_SPREAD",
        direction="CALL",
        quantity=1,
        entry_price=1.30,
        capital_committed=130,
        maximum_loss=130,
        maximum_profit=370,
        sector="CONSUMER CYCLICAL",
    )
    service = PortfolioSnapshotService(
        registry,
        root / "snapshots",
        root / "exposure.json",
        root / "audit.json",
    )
    artifact = service.create_snapshot()
    assert artifact.registry["open_position_count"] == 1
    assert artifact.exposure.capital_committed == 130
    assert artifact.exposure.by_symbol[0].key == "AMZN"
    assert artifact.exposure.by_sector[0].key == "CONSUMER CYCLICAL"
    assert len(list((root / "snapshots").glob("*.json"))) == 1
    assert service.load_audit_history().records[0].snapshot_id == artifact.snapshot_id

print("Milestone 36 Phase 1 Step 4 snapshot assertions passed.")
