from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Iterable, Sequence

from trading_ai.scanner.options_market_data_quality.normalization import (
    OptionQuoteNormalizer,
)

from .contracts import ProviderBatch


class CsvOptionHistoryProvider:
    """Stream one or more historical option-chain CSV files."""

    def __init__(
        self,
        paths: Sequence[str | Path],
        *,
        normalizer: OptionQuoteNormalizer | None = None,
    ) -> None:
        self.paths = tuple(Path(path) for path in paths)
        self.normalizer = normalizer or OptionQuoteNormalizer()

    @property
    def source_name(self) -> str:
        return "csv"

    def iter_batches(
        self,
        *,
        symbols: Sequence[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        batch_size: int = 5_000,
    ) -> Iterable[ProviderBatch]:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")

        symbol_filter = (
            {symbol.strip().upper() for symbol in symbols if symbol}
            if symbols
            else None
        )

        for path in self.paths:
            if not path.exists():
                raise FileNotFoundError(path)

            batch = []
            batch_number = 1
            with path.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames:
                    raise ValueError(f"CSV has no header: {path}")

                for row_number, row in enumerate(reader, start=2):
                    try:
                        record = self.normalizer.normalize(row)
                    except Exception as exc:
                        raise ValueError(
                            f"{path}:{row_number}: {exc}"
                        ) from exc

                    if (
                        symbol_filter is not None
                        and record.identity.underlying_symbol not in symbol_filter
                    ):
                        continue
                    if start_date is not None and record.quote_date < start_date:
                        continue
                    if end_date is not None and record.quote_date > end_date:
                        continue

                    batch.append(record)
                    if len(batch) >= batch_size:
                        yield ProviderBatch(
                            batch_id=f"{path.name}:{batch_number}",
                            records=tuple(batch),
                            source_name=self.source_name,
                            metadata={
                                "path": str(path),
                                "batch_number": batch_number,
                            },
                        )
                        batch = []
                        batch_number += 1

            if batch:
                yield ProviderBatch(
                    batch_id=f"{path.name}:{batch_number}",
                    records=tuple(batch),
                    source_name=self.source_name,
                    metadata={
                        "path": str(path),
                        "batch_number": batch_number,
                    },
                )
