from trading_ai.research_workstation.scanner import (
    OptionHistoryDataAdapter,
    RepositoryOptionsDataAdapter,
)
from trading_ai.ui.services.research_scanner_service import (
    ResearchScannerDashboardService,
)


def main() -> None:
    assert RepositoryOptionsDataAdapter is not None
    assert OptionHistoryDataAdapter is RepositoryOptionsDataAdapter
    assert ResearchScannerDashboardService is not None

    print(
        "Milestone 34 Phase 1 Step 5 option-adapter "
        "contract assertions passed."
    )


if __name__ == "__main__":
    main()
