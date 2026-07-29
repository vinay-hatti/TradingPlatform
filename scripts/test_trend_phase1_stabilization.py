from pathlib import Path
from types import SimpleNamespace

from trading_ai.trend_intelligence.service import TrendIntelligenceService


class StubEngine:
    def analyze(self, symbol, prices, **kwargs):
        if symbol == "HONA":
            raise ValueError("insufficient price history for HONA: 28 rows")

        snapshot = SimpleNamespace(
            snapshot_timestamp="2026-07-28T00:00:00+00:00",
            symbol=symbol,
            as_of_date="2026-07-24",
            short_term=SimpleNamespace(state="BULLISH"),
            intermediate_term=SimpleNamespace(state="BULLISH"),
            long_term=SimpleNamespace(state="BULLISH"),
            alignment_score=90.0,
            trend_quality_score=80.0,
            trend_confidence=85.0,
            trend_stage="EARLY_TREND",
            trend_age_days=4,
            relative_strength_vs_spy=3.0,
            relative_strength_vs_sector=2.0,
            sector=kwargs.get("sector", "Unknown"),
            sector_etf=kwargs.get("sector_etf", ""),
            calculation_version="trend.v1",
        )
        snapshot.to_dict = lambda: {
            "symbol": snapshot.symbol,
            "status": "READY",
            "sector": snapshot.sector,
            "sector_etf": snapshot.sector_etf,
        }
        return snapshot


def main():
    service = TrendIntelligenceService(
        canonical_csv=Path("missing.csv"),
        engine=StubEngine(),
    )
    service._membership = lambda: {
        "AAPL": ("Information Technology", "XLK"),
        "HONA": ("Financials", "XLF"),
    }
    service._prices = lambda symbols: {symbol: object() for symbol in symbols}
    service.persist = lambda snapshots: None

    result = service.build(["AAPL", "HONA"], persist=True)

    assert result["status"] == "READY", result
    assert result["requested_symbol_count"] == 2, result
    assert result["symbol_count"] == 1, result
    assert result["skipped_count"] == 1, result
    assert result["error_count"] == 0, result
    assert result["skipped"][0]["symbol"] == "HONA", result
    assert result["skipped"][0]["reason"] == "INSUFFICIENT_PRICE_HISTORY", result
    assert result["results"][0]["symbol"] == "AAPL", result
    assert result["results"][0]["sector"] == "Information Technology", result
    assert result["results"][0]["sector_etf"] == "XLK", result

    print("All Trend Intelligence Phase 1 stabilization assertions passed.")


if __name__ == "__main__":
    main()
