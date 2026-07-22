from trading_ai.scanner.dashboard import RankingRecord
from trading_ai.scanner.dashboard.ranking_contracts import RankingQuery
from trading_ai.scanner.dashboard.ranking_engine import OpportunityRankingEngine


def main() -> None:
    records = [RankingRecord(f"SYM{i:03d}", i, 1.0 - i / 1000, 0.5) for i in range(1, 61)]
    engine = OpportunityRankingEngine()
    page = engine.build_page(records, RankingQuery(page=2, page_size=25, top_n=50))
    assert len(page.records) == 25
    assert page.records[0].rank == 26
    assert page.has_previous is True
    assert page.has_next is False
    assert page.total_pages == 2
    print("Milestone 35 Phase 5 Step 3 pagination assertions passed.")


if __name__ == "__main__":
    main()
