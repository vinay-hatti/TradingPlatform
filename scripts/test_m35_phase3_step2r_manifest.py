from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.scanner.options_market_data_ingestion import (
    IngestionManifestStore,
)


def main() -> None:
    with TemporaryDirectory() as directory:
        store = IngestionManifestStore(Path(directory) / "manifest.json")
        assert not store.is_completed("batch-1")
        store.mark_completed("batch-1", metadata={"records": 10})
        assert store.is_completed("batch-1")
        store.reset()
        assert not store.is_completed("batch-1")

    print("Milestone 35 Phase 3 revised Step 2 manifest assertions passed.")


if __name__ == "__main__":
    main()
