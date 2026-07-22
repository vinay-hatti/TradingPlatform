from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class SurfacePersistencePolicy:
    allowed_expiration_statuses: tuple[str, ...] = (
        "READY",
        "REVIEW",
    )
    allowed_symbol_statuses: tuple[str, ...] = (
        "READY",
        "REVIEW",
    )
    require_matching_as_of_date: bool = True
    fail_on_duplicate_expiration_key: bool = True
    fail_on_duplicate_symbol_key: bool = True


@dataclass(frozen=True)
class SurfacePersistenceRunProfile:
    as_of_date: date
    generated_at: datetime

    expiration_input_path: str
    symbol_input_path: str
    expiration_csv_path: str
    symbol_csv_path: str
    governance_summary_path: str

    expiration_records_read: int
    expiration_records_persisted: int
    expiration_records_filtered: int

    symbol_records_read: int
    symbol_records_persisted: int
    symbol_records_filtered: int

    duplicate_expiration_keys: int
    duplicate_symbol_keys: int

    expiration_ready: int
    expiration_review: int
    expiration_excluded: int

    symbol_ready: int
    symbol_review: int
    symbol_excluded: int

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
