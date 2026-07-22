from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.scanner.dashboard.ranking_cli import (
    _apply_selection,
    _invoke_service,
    _persist_if_supported,
)


@dataclass
class View:
    total_records: int
    selected_symbol: str | None = None


class InstalledShapeService:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.persisted = False

    def build_view(self, records, query):
        return View(total_records=len(records))

    def select_candidate(self, view, symbol):
        view.selected_symbol = symbol
        return view

    def persist(self, view):
        self.persisted = True
        return view


def main() -> None:
    with TemporaryDirectory() as directory:
        service = InstalledShapeService(Path(directory))
        records = [object(), object()]
        query = object()

        view = _invoke_service(service, records, query)
        assert view.total_records == 2

        view = _apply_selection(service, view, "aapl")
        assert view.selected_symbol == "AAPL"

        view = _persist_if_supported(service, view)
        assert service.persisted is True
        assert view.total_records == 2

    print(
        "Milestone 35 Phase 5 Step 3 build_view dispatch assertions passed."
    )


if __name__ == "__main__":
    main()
