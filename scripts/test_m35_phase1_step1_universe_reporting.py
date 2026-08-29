import json
from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.scanner.universe_management import (
    SecurityProfile,
    UniverseEngine,
    UniversePolicy,
    write_universe_json,
    write_universe_summary,
)


def main() -> None:
    result = UniverseEngine(UniversePolicy(minimum_symbol_count=1)).build(
        [SecurityProfile("AAPL", exchange="NASDAQ", source="TEST")]
    )
    with TemporaryDirectory() as directory:
        root = Path(directory)
        full = write_universe_json(result, root / "universe.json")
        summary = write_universe_summary(result, root / "summary.json")
        full_payload = json.loads(full.read_text(encoding="utf-8"))
        summary_payload = json.loads(summary.read_text(encoding="utf-8"))
        assert full_payload["accepted_count"] == 1
        assert summary_payload["governance_status"] == "READY"
        assert summary_payload["accepted_count"] == 1
    print("Milestone 35 Phase 1 Step 1 universe reporting assertions passed.")


if __name__ == "__main__":
    main()
