from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from .forecast_engine import TrendForecastEngine
from .forecast_repository import TrendForecastRepository

class TrendForecastService:
    def __init__(self, market_service, engine=None, repository=None):
        self.market_service=market_service; self.engine=engine or TrendForecastEngine(); self.repository=repository or TrendForecastRepository()
    def run(self, symbols, start, end, report_path="reports/trend_intelligence/forecasts_latest.json"):
        results=[]; skipped=[]; errors=[]
        for symbol in symbols:
            try:
                prices=self.market_service.get_price_history(symbol,start,end)
                for horizon in self.engine.policy.horizons:
                    snapshot=self.engine.calculate(symbol,prices,horizon); self.repository.save(snapshot); results.append(snapshot.to_dict())
            except ValueError as exc:
                skipped.append({"symbol":symbol,"reason":"INSUFFICIENT_FORECAST_HISTORY","detail":str(exc)})
            except Exception as exc:
                errors.append({"symbol":symbol,"error":str(exc)})
        status="READY" if not errors else "DEGRADED"
        payload={"status":status,"snapshot_timestamp":datetime.now(timezone.utc).isoformat(),"requested_symbol_count":len(symbols),
        "symbol_count":len({x["symbol"] for x in results}),"forecast_count":len(results),"skipped_count":len(skipped),"error_count":len(errors),
        "results":results,"skipped":skipped,"errors":errors}
        path=Path(report_path); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(payload,indent=2),encoding="utf-8")
        return payload
