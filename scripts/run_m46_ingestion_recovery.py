from __future__ import annotations
import argparse, json
from pathlib import Path

RECOVERABLE={"market_overview","market_intelligence","scanner_readiness","publish_current_snapshot"}

def main() -> int:
    p=argparse.ArgumentParser(description="Recover failed post-ingestion Milestone 46 phases without recapturing Polygon options.")
    p.add_argument("--report",default="reports/market_ingestion/unified_latest.json")
    p.add_argument("--publication-name",default="current_market_state")
    args=p.parse_args()
    payload=json.loads(Path(args.report).read_text(encoding="utf-8"))
    failed=[x["name"] for x in payload.get("phases",[]) if x.get("status")=="FAILED"]
    unsupported=[x for x in failed if x not in RECOVERABLE]
    if unsupported:
        print("Full ingestion is required for failed data-capture phases: "+", ".join(unsupported))
        return 2
    if "market_overview" in failed:
        from trading_ai.market_overview.service import MarketOverviewService
        MarketOverviewService().build(persist=True)
        print("market_overview: READY")
    if "market_intelligence" in failed or "market_overview" in failed:
        from trading_ai.market_intelligence.service import MarketIntelligenceService
        MarketIntelligenceService().build(persist=True)
        print("market_intelligence: READY")
    from trading_ai.database import SessionLocal
    from trading_ai.market_intelligence.publication import ScannerReadinessService
    with SessionLocal() as session:
        result=ScannerReadinessService(session).publish(run_id=str(payload.get("run_id") or "recovery"),publication_name=args.publication_name)
    print(json.dumps(result.to_dict(),indent=2,default=str))
    return 0 if result.scanner_ready else 1

if __name__ == "__main__":
    raise SystemExit(main())
