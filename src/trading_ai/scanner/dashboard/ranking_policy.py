from __future__ import annotations

from dataclasses import dataclass

from .ranking_contracts import RankingQuery


@dataclass(frozen=True)
class OpportunityRankingPolicy:
    allowed_top_n: tuple[int, ...] = (10, 25, 50, 100)
    allowed_page_sizes: tuple[int, ...] = (10, 25, 50, 100)
    sortable_fields: tuple[str, ...] = (
        "rank",
        "symbol",
        "institutional_score",
        "probability_score",
        "expected_move",
        "regime",
        "sector",
        "exchange",
        "cross_asset_score",
    )

    def validate_query(self, query: RankingQuery) -> None:
        if query.top_n not in self.allowed_top_n:
            raise ValueError(f"top_n must be one of {self.allowed_top_n}")
        if query.page_size not in self.allowed_page_sizes:
            raise ValueError(f"page_size must be one of {self.allowed_page_sizes}")
        if query.page < 1:
            raise ValueError("page must be at least 1")
        if query.sort.field not in self.sortable_fields:
            raise ValueError(f"unsupported ranking sort field: {query.sort.field}")
