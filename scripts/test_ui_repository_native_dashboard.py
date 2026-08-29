from __future__ import annotations

import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.ui.adapters.artifact_sources import RepositoryArtifactAdapters
from trading_ai.ui.services.dashboard_service import DashboardService


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        reports = root / "reports"
        reports.mkdir(parents=True)

        with (reports / "scanner_results_20260718.csv").open(
            "w", newline="", encoding="utf-8"
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "symbol", "signal", "rank_score",
                    "probability_of_profit", "regime",
                    "strike", "expiry", "liquidity_score",
                ],
            )
            writer.writeheader()
            writer.writerow({
                "symbol": "SPY",
                "signal": "CALL",
                "rank_score": "94",
                "probability_of_profit": "0.82",
                "regime": "BULL_TREND",
                "strike": "700",
                "expiry": "2026-08-21",
                "liquidity_score": "96",
            })

        paper = root / "data/paper"
        paper.mkdir(parents=True)
        (paper / "positions.json").write_text(json.dumps([
            {
                "symbol": "SPY",
                "status": "OPEN",
                "quantity": 2,
                "current_price": 5.0,
                "unrealized_pnl": 125.0,
            }
        ]))
        (paper / "cash.json").write_text(json.dumps({"cash": 90000.0}))

        service = DashboardService(RepositoryArtifactAdapters(root))
        snapshot = service.snapshot()

        assert snapshot.market_regime == "BULL_TREND"
        assert snapshot.opportunities[0].symbol == "SPY"
        assert snapshot.opportunities[0].score == 94.0
        assert snapshot.ai_confidence == 0.82
        assert snapshot.market_status == "Artifact data available"
        assert snapshot.raw["portfolio"]["open_positions"] == 1.0

    print("All repository-native dashboard assertions passed.")


if __name__ == "__main__":
    main()
