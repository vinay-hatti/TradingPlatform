from trading_ai.scanner.dashboard import RankingRecord
from trading_ai.scanner.dashboard.ranking_contracts import RankingQuery
from trading_ai.scanner.dashboard.ranking_engine import OpportunityRankingEngine


def main() -> None:
    engine = OpportunityRankingEngine()
    page = engine.build_page(
        [RankingRecord("AAPL", 1, 0.9, 0.7), RankingRecord("MSFT", 2, 0.8, 0.6)],
        RankingQuery(page_size=10, top_n=10),
    )
    selected = engine.select_candidate(page, "aapl")
    assert selected.selected_symbol == "AAPL"
    try:
        engine.select_candidate(page, "NVDA")
    except ValueError:
        pass
    else:
        raise AssertionError("selection outside current page should fail")
    print("Milestone 35 Phase 5 Step 3 selection assertions passed.")


if __name__ == "__main__":
    main()
