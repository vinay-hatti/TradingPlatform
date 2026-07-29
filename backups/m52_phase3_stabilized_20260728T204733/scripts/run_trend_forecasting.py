from __future__ import annotations
import argparse, json
from trading_ai.database.session import SessionLocal
from trading_ai.market.service import MarketService
from trading_ai.trend_intelligence.forecast_service import TrendForecastService

def main():
    p=argparse.ArgumentParser(); p.add_argument("--symbols",default=""); p.add_argument("--start",default="2025-01-01"); p.add_argument("--end",default="2026-07-28"); a=p.parse_args()
    if a.symbols: symbols=[x.strip().upper() for x in a.symbols.split(",") if x.strip()]
    else:
        with SessionLocal() as s: symbols=[r[0] for r in s.execute(__import__('sqlalchemy').text("SELECT DISTINCT symbol FROM price_history ORDER BY symbol"))]
    result=TrendForecastService(MarketService()).run(symbols,a.start,a.end)
    print(json.dumps({k:result[k] for k in ("status","snapshot_timestamp","requested_symbol_count","symbol_count","forecast_count","skipped_count","error_count")},indent=2))
    print("reports/trend_intelligence/forecasts_latest.json")
if __name__=="__main__": main()
