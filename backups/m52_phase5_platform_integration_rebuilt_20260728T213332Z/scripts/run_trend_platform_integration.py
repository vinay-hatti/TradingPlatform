from __future__ import annotations
import argparse, json
from pathlib import Path
from sqlalchemy import text
from trading_ai.database.session import SessionLocal
from trading_ai.trend_intelligence.platform_integration import TrendPlatformIntegrationService


def symbols_from_db():
    with SessionLocal() as session:
        return tuple(session.execute(text("SELECT DISTINCT symbol FROM stock_trend_snapshot ORDER BY symbol")).scalars())


def main():
    parser=argparse.ArgumentParser(description="Build Milestone 52 platform-integration context")
    parser.add_argument("--symbols")
    parser.add_argument("--output",default="reports/trend_intelligence/platform_integration_latest.json")
    args=parser.parse_args()
    symbols=tuple(s.strip().upper() for s in args.symbols.split(",") if s.strip()) if args.symbols else symbols_from_db()
    service=TrendPlatformIntegrationService()
    result={"market_overview":service.market_overview(symbols),"symbols":[service.context(s).to_dict() for s in symbols]}
    path=Path(args.output); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(result,indent=2,default=str)+"\n")
    print(json.dumps(result["market_overview"],indent=2)); print(path)
if __name__=="__main__": main()
