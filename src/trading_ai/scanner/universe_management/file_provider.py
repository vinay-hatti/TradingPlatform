from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .provider_contracts import ProviderFetchResult
from .universe_service import UniverseService


class FileUniverseProvider:
    """Load a universe from a canonical CSV file.

    ``CsvUniverseProvider`` was the public name introduced in Milestone 35
    Phase 1 Step 2.  ``FileUniverseProvider`` later became the implementation
    name.  The alias below preserves both APIs.
    """

    def __init__(self, path: str | Path, name: str = "CSV") -> None:
        self.path = Path(path)
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def fetch(self) -> ProviderFetchResult:
        securities = UniverseService().load_csv(self.path, source=self.name)
        return ProviderFetchResult(
            self.name,
            securities,
            datetime.now(timezone.utc),
            source_uri=str(self.path),
        )


# Backward-compatible public API used by the original Step 2 tests and callers.
CsvUniverseProvider = FileUniverseProvider


__all__ = ["FileUniverseProvider", "CsvUniverseProvider"]
