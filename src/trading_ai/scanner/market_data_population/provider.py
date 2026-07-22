from __future__ import annotations

from datetime import date
from typing import Protocol, Sequence

from .models import PriceBar


class BulkHistoricalDataProvider(Protocol):
    @property
    def name(self) -> str: ...

    def fetch_batch(
        self,
        symbols: Sequence[str],
        start: date,
        end: date,
    ) -> dict[str, tuple[PriceBar, ...]]: ...
