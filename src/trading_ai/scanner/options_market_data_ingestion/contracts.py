from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Mapping, Protocol, Sequence

from trading_ai.scanner.options_market_data_quality.contracts import (
    OptionQuoteRecord,
)


@dataclass(frozen=True)
class ProviderBatch:
    batch_id: str
    records: tuple[OptionQuoteRecord, ...]
    source_name: str
    metadata: Mapping[str, object] = field(default_factory=dict)


class OptionHistoryProvider(Protocol):
    @property
    def source_name(self) -> str:
        ...

    def iter_batches(
        self,
        *,
        symbols: Sequence[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        batch_size: int = 5_000,
    ) -> Iterable[ProviderBatch]:
        ...


@dataclass(frozen=True)
class IngestionBatchResult:
    batch_id: str
    input_records: int
    valid_records: int
    rejected_records: int
    inserted_records: int
    updated_records: int
    skipped_records: int
    error_messages: tuple[str, ...] = ()


@dataclass(frozen=True)
class IngestionRunProfile:
    source_name: str
    started_at: str
    completed_at: str
    batch_count: int
    input_records: int
    valid_records: int
    rejected_records: int
    inserted_records: int
    updated_records: int
    skipped_records: int
    resumed_batches: int
    failed_batches: int
    batch_results: tuple[IngestionBatchResult, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)
