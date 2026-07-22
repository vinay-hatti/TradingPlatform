from __future__ import annotations

from dataclasses import replace
from math import ceil
from typing import Iterable, Sequence

from .contracts import RankingRecord
from .ranking_contracts import (
    RankingColumn,
    RankingColumnType,
    RankingPage,
    RankingQuery,
    RankingSortDirection,
    RankingSummary,
)
from .ranking_policy import OpportunityRankingPolicy


class OpportunityRankingEngine:
    def __init__(self, policy: OpportunityRankingPolicy | None = None) -> None:
        self.policy = policy or OpportunityRankingPolicy()

    def default_columns(self) -> tuple[RankingColumn, ...]:
        return (
            RankingColumn("rank", "Rank", RankingColumnType.INTEGER, width=72),
            RankingColumn("symbol", "Symbol", RankingColumnType.TEXT, width=100),
            RankingColumn("institutional_score", "Institutional Score", RankingColumnType.DECIMAL),
            RankingColumn("probability_score", "Probability", RankingColumnType.PERCENTAGE),
            RankingColumn("expected_move", "Expected Move", RankingColumnType.PERCENTAGE),
            RankingColumn("regime", "Regime", RankingColumnType.TEXT),
            RankingColumn("sector", "Sector", RankingColumnType.TEXT),
            RankingColumn("exchange", "Exchange", RankingColumnType.TEXT),
            RankingColumn("optionable", "Optionable", RankingColumnType.BOOLEAN),
            RankingColumn("is_etf", "ETF", RankingColumnType.BOOLEAN),
            RankingColumn("cross_asset_score", "Cross-Asset", RankingColumnType.DECIMAL),
        )

    def build_page(
        self,
        rankings: Iterable[RankingRecord],
        query: RankingQuery | None = None,
        *,
        selected_symbol: str | None = None,
        columns: Sequence[RankingColumn] | None = None,
    ) -> RankingPage:
        active_query = query or RankingQuery()
        self.policy.validate_query(active_query)

        records = list(rankings)
        total_records = len(records)
        records = self._search(records, active_query.search_text)
        records = self._sort(records, active_query)
        records = records[: active_query.top_n]
        filtered_records = len(records)

        total_pages = max(1, ceil(filtered_records / active_query.page_size))
        page = min(active_query.page, total_pages)
        normalized_query = replace(active_query, page=page)
        start = (page - 1) * active_query.page_size
        stop = start + active_query.page_size
        page_records = tuple(records[start:stop])

        return RankingPage(
            query=normalized_query,
            columns=tuple(columns or self.default_columns()),
            records=page_records,
            total_records=total_records,
            filtered_records=filtered_records,
            total_pages=total_pages,
            has_previous=page > 1,
            has_next=page < total_pages,
            selected_symbol=selected_symbol.upper() if selected_symbol else None,
            summary=self._summary(records),
            metadata={"available_top_n": list(self.policy.allowed_top_n)},
        )

    def select_candidate(self, page: RankingPage, symbol: str) -> RankingPage:
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("symbol is required")
        known = {record.symbol.upper() for record in page.records}
        if normalized not in known:
            raise ValueError(f"symbol is not present on the current ranking page: {normalized}")
        return replace(page, selected_symbol=normalized)

    @staticmethod
    def _search(records: list[RankingRecord], search_text: str | None) -> list[RankingRecord]:
        if not search_text or not search_text.strip():
            return records
        token = search_text.strip().lower()
        return [
            record
            for record in records
            if token in record.symbol.lower()
            or token in (record.sector or "").lower()
            or token in (record.exchange or "").lower()
            or token in (record.regime or "").lower()
        ]

    @staticmethod
    def _sort(records: list[RankingRecord], query: RankingQuery) -> list[RankingRecord]:
        reverse = query.sort.direction is RankingSortDirection.DESC

        def key(record: RankingRecord):
            value = getattr(record, query.sort.field)
            if value is None:
                return (1, "")
            if isinstance(value, str):
                return (0, value.lower())
            return (0, value)

        return sorted(records, key=key, reverse=reverse)

    @staticmethod
    def _summary(records: Sequence[RankingRecord]) -> RankingSummary:
        count = len(records)
        if count == 0:
            return RankingSummary(0, 0, 0.0, 0.0, 0, 0, 0, 0, 0)

        bullish = sum(1 for r in records if "UP" in (r.regime or "").upper() or "BULL" in (r.regime or "").upper())
        bearish = sum(1 for r in records if "DOWN" in (r.regime or "").upper() or "BEAR" in (r.regime or "").upper())
        neutral = count - bullish - bearish
        return RankingSummary(
            total_records=count,
            visible_records=count,
            average_institutional_score=sum(r.institutional_score for r in records) / count,
            average_probability_score=sum(r.probability_score for r in records) / count,
            bullish_count=bullish,
            bearish_count=bearish,
            neutral_count=neutral,
            optionable_count=sum(1 for r in records if r.optionable is True),
            etf_count=sum(1 for r in records if r.is_etf is True),
        )
