from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.scanner.dashboard import RankingRecord
from trading_ai.scanner.dashboard.ranking_contracts import RankingQuery
from trading_ai.scanner.dashboard.ranking_service import OpportunityRankingService


def main() -> None:
    with TemporaryDirectory() as directory:
        service = OpportunityRankingService(output_dir=directory)
        page = service.build_view(
            [RankingRecord("AAPL", 1, 0.95, 0.78, regime="TREND_UP")],
            RankingQuery(page_size=10, top_n=10),
        )
        assert page.records[0].symbol == "AAPL"
        output = Path(directory)
        assert (output / "opportunity_rankings_view.json").exists()
        html = (output / "opportunity_rankings.html").read_text(encoding="utf-8")
        assert "Institutional Opportunity Rankings" in html
        assert "AAPL" in html
    print("Milestone 35 Phase 5 Step 3 service assertions passed.")


if __name__ == "__main__":
    main()
