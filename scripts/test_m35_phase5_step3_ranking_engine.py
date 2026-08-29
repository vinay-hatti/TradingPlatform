from trading_ai.scanner.dashboard import RankingRecord
from trading_ai.scanner.dashboard.ranking_contracts import RankingQuery, RankingSort, RankingSortDirection
from trading_ai.scanner.dashboard.ranking_engine import OpportunityRankingEngine


def records():
    return [
        RankingRecord("AAPL", 1, 0.95, 0.78, 0.04, "TREND_UP", "Technology", "NASDAQ", True, False, 0.81),
        RankingRecord("MSFT", 2, 0.93, 0.76, 0.03, "TREND_UP", "Technology", "NASDAQ", True, False, 0.79),
        RankingRecord("SPY", 3, 0.90, 0.72, 0.02, "NEUTRAL", "ETF", "ARCA", True, True, 0.75),
        RankingRecord("XOM", 4, 0.84, 0.65, 0.05, "TREND_DOWN", "Energy", "NYSE", True, False, 0.60),
    ]


def main() -> None:
    engine = OpportunityRankingEngine()
    page = engine.build_page(records(), RankingQuery(page_size=10, top_n=10))
    assert page.records[0].symbol == "AAPL"
    assert page.summary.optionable_count == 4
    assert page.summary.bullish_count == 2

    page = engine.build_page(
        records(),
        RankingQuery(
            search_text="technology",
            sort=RankingSort("probability_score", RankingSortDirection.DESC),
            page_size=10,
            top_n=10,
        ),
    )
    assert [r.symbol for r in page.records] == ["AAPL", "MSFT"]
    print("Milestone 35 Phase 5 Step 3 ranking engine assertions passed.")


if __name__ == "__main__":
    main()
