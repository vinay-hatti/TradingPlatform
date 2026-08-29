from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import csv
from trading_ai.ui.adapters.artifact_sources import RepositoryArtifactAdapters
from trading_ai.ui.services.symbol_intelligence_service import SymbolIntelligenceService

@dataclass
class Row:
    symbol:str; date:date; open:float; high:float; low:float; close:float; volume:int

class FakePrices:
    def get_range(self, symbol, start, end):
        first = date.today() - timedelta(days=299)
        return [Row(symbol, first+timedelta(days=i), 100+i*.25, 102+i*.25, 99+i*.25, 101+i*.25, 1_000_000+i*1000) for i in range(300)]

def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({k for row in rows for k in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

def main():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        write_csv(root/"reports/scanner_results_newest.csv", [{"symbol":"QQQ","signal":"PUT"}])
        write_csv(root/"reports/scanner_results_older.csv", [{
            "symbol":"SPY","signal":"CALL","strategy":"LONG_CALL",
            "contract_ticker":"O:SPY","rank_score":"90","probability_of_profit":"0.78"
        }])
        write_csv(root/"reports/daily/2026-07-18/live_trade_candidates.csv", [{
            "symbol":"SPY","signal":"CALL","strategy":"BULL_CALL_SPREAD",
            "ai_score":"88","market_regime":"TREND_UP","strike":"181"
        }])
        service = SymbolIntelligenceService(
            FakePrices(), RepositoryArtifactAdapters(root), 999999999
        )
        result = service.get("SPY")
        assert len(result.price_history) == 252
        assert result.technicals.sma200 is not None
        assert len(result.opportunity_history) == 2
        assert any(x.contract == "O:SPY" for x in result.opportunity_history)
    print("All corrected Milestone 31 Phase 4 Symbol Intelligence assertions passed.")

if __name__ == "__main__":
    main()
