from __future__ import annotations

import json
import tempfile
from pathlib import Path

from trading_ai.portfolio_management.lifecycle_service import PositionLifecycleReconciliationService
from trading_ai.portfolio_management.service import PortfolioRegistryService


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        registry = PortfolioRegistryService(root / "registry.json")
        registry.initialize("Test", 100000)
        artifact = root / "lifecycle.json"
        artifact.write_text(json.dumps({
            "order": {"symbol": "MSFT", "strategy_id": "MSFT:TEST", "status": "FILLED"},
            "position": {"position_id": "MISSING-1", "symbol": "MSFT",
                         "strategy_id": "MSFT:TEST", "status": "OPEN"},
        }))
        service = PositionLifecycleReconciliationService(registry, root / "journal.json")
        result = service.reconcile_lifecycle_artifact(artifact)
        assert result.status == "EXCEPTION"
        assert result.action == "OPERATOR_REVIEW"
        journal = service.load_journal()
        assert journal.exceptions[0].exception_type == "SOURCE_POSITION_NOT_IN_REGISTRY"
        assert not journal.exceptions[0].resolved
        resolved = service.resolve_exception(journal.exceptions[0].exception_id, "Imported manually")
        assert resolved.exceptions[0].resolved
    print("Milestone 36 Phase 1 Step 3 conflict-governance assertions passed.")

if __name__ == "__main__":
    main()
