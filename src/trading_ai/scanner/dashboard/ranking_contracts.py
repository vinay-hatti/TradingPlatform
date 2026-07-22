from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Sequence

from .contracts import RankingRecord


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RankingSortDirection(str, Enum):
    ASC = "ASC"
    DESC = "DESC"


class RankingColumnType(str, Enum):
    TEXT = "TEXT"
    INTEGER = "INTEGER"
    DECIMAL = "DECIMAL"
    PERCENTAGE = "PERCENTAGE"
    BOOLEAN = "BOOLEAN"


@dataclass(frozen=True)
class RankingColumn:
    key: str
    label: str
    column_type: RankingColumnType
    sortable: bool = True
    visible: bool = True
    width: int | None = None


@dataclass(frozen=True)
class RankingSort:
    field: str = "rank"
    direction: RankingSortDirection = RankingSortDirection.ASC


@dataclass(frozen=True)
class RankingQuery:
    search_text: str | None = None
    sort: RankingSort = field(default_factory=RankingSort)
    page: int = 1
    page_size: int = 25
    top_n: int = 50


@dataclass(frozen=True)
class RankingSummary:
    total_records: int
    visible_records: int
    average_institutional_score: float
    average_probability_score: float
    bullish_count: int
    bearish_count: int
    neutral_count: int
    optionable_count: int
    etf_count: int


@dataclass(frozen=True)
class RankingPage:
    query: RankingQuery
    columns: Sequence[RankingColumn]
    records: Sequence[RankingRecord]
    total_records: int
    filtered_records: int
    total_pages: int
    has_previous: bool
    has_next: bool
    selected_symbol: str | None = None
    summary: RankingSummary | None = None
    generated_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)
