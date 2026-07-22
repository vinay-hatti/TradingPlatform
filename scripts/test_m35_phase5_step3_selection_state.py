from dataclasses import dataclass
from pathlib import Path
from trading_ai.scanner.dashboard.ranking_cli import _apply_selection, _persist_if_supported, _view_value

@dataclass(frozen=True)
class View:
    total_records: int
    filtered_records: int
    selected_symbol: str | None = None

@dataclass(frozen=True)
class Candidate:
    symbol: str

class Service:
    def select_candidate(self, view, symbol):
        return Candidate(symbol)
    def persist(self, view):
        return Path("ranking_snapshot.json")

def main() -> None:
    view = View(8, 8)
    service = Service()
    selected = _apply_selection(service, view, "amzn")
    selected = _persist_if_supported(service, selected)
    assert _view_value(selected, "selected_symbol") == "AMZN"
    assert _view_value(selected, "total_records") == 8
    print("Milestone 35 Phase 5 Step 3 selection-state assertions passed.")

if __name__ == "__main__":
    main()
