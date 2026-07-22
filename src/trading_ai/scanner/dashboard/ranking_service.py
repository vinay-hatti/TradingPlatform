from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from .contracts import RankingRecord
from .ranking_contracts import RankingColumn, RankingPage, RankingQuery
from .ranking_engine import OpportunityRankingEngine
from .ranking_reporting import write_rankings_html
from .ranking_serialization import write_ranking_page


class OpportunityRankingService:
    def __init__(
        self,
        engine: OpportunityRankingEngine | None = None,
        output_dir: Path | str = "reports/m35/phase5/dashboard",
    ) -> None:
        self.engine = engine or OpportunityRankingEngine()
        self.output_dir = Path(output_dir)

    def build_view(
        self,
        rankings: Iterable[RankingRecord],
        query: RankingQuery | None = None,
        *,
        selected_symbol: str | None = None,
        columns: Sequence[RankingColumn] | None = None,
    ) -> RankingPage:
        page = self.engine.build_page(
            rankings,
            query,
            selected_symbol=selected_symbol,
            columns=columns,
        )
        return self.persist(page)

    def select_candidate(self, page: RankingPage, symbol: str) -> RankingPage:
        return self.persist(self.engine.select_candidate(page, symbol))

    def persist(self, page: RankingPage) -> RankingPage:
        write_ranking_page(self.output_dir / "opportunity_rankings_view.json", page)
        write_rankings_html(self.output_dir / "opportunity_rankings.html", page)
        return page
