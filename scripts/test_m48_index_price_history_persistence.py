from __future__ import annotations

from pathlib import Path


def main() -> None:
    source = Path("scripts/run_market_ingestion.py").read_text(encoding="utf-8")
    service = Path(
        "src/trading_ai/market/index_ingestion/service.py"
    ).read_text(encoding="utf-8")

    assert "IndexHistoryIngestionService" in source
    assert "session_factory=SessionLocal" in source
    assert "MarketService(provider=index_provider)" not in source
    assert "session.merge(" in service
    assert "session.commit()" in service
    assert "session.rollback()" in service
    assert "persistence verification failed" in service
    assert "PriceHistory(" in service
    assert "symbol=symbol" in service
    assert "persisted_rows" in source

    print("Milestone 48 index price-history persistence assertions passed.")


if __name__ == "__main__":
    main()
