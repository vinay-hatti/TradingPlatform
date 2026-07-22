import json
from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.scanner.dashboard.dashboard_artifact_discovery import (
    DashboardArtifactDiscoveryService,
)


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        target = (
            root
            / "reports/m35/phase5/dashboard/"
            / "paper_trade_preparation"
            / "amzn_call_paper_trade_preparation.json"
        )
        target.parent.mkdir(parents=True)
        target.write_text(
            json.dumps(
                {
                    "symbol": "AMZN",
                    "direction": "CALL",
                    "paper_trade_ready": True,
                    "refreshed_debit": 1.30,
                }
            ),
            encoding="utf-8",
        )

        result = DashboardArtifactDiscoveryService().discover(root)
        item = result["PAPER_TRADE_PREPARATION"]

        assert item.path == target.resolve()
        assert item.payload is not None
        assert item.payload["paper_trade_ready"] is True

    print(
        "Milestone 35 Phase 5 Step 12 artifact-discovery "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
