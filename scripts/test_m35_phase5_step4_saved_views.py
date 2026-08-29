from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.scanner.dashboard.filter_contracts import (
    SavedScannerView,
    ScannerFilter,
)
from trading_ai.scanner.dashboard.saved_view_repository import (
    SavedScannerViewRepository,
)
from trading_ai.scanner.dashboard.saved_view_service import (
    SavedScannerViewService,
)


def main() -> None:
    with TemporaryDirectory() as directory:
        path = Path(directory) / "saved_views.json"
        service = SavedScannerViewService(
            SavedScannerViewRepository(path)
        )

        service.save(
            SavedScannerView(
                name="Institutional Calls",
                description="High-conviction liquid bullish candidates",
                filters=ScannerFilter(
                    min_institutional_score=80,
                    min_probability_of_profit=0.60,
                    max_spread_pct=0.10,
                    directions=("CALL",),
                ),
                sort_field="institutional_score",
                sort_direction="DESC",
                top_n=50,
                page_size=25,
            )
        )

        loaded = service.load("institutional calls")
        assert loaded.name == "Institutional Calls"
        assert loaded.filters.directions == ("CALL",)
        assert len(service.list_views()) == 1

        service.save(
            SavedScannerView(
                name="Institutional Calls",
                filters=ScannerFilter(
                    min_institutional_score=85,
                    directions=("CALL",),
                ),
            )
        )
        assert len(service.list_views()) == 1
        assert (
            service.load("Institutional Calls")
            .filters.min_institutional_score
            == 85
        )

        assert service.delete("Institutional Calls") is True
        assert service.list_views() == []

    print(
        "Milestone 35 Phase 5 Step 4 saved-view assertions passed."
    )


if __name__ == "__main__":
    main()
