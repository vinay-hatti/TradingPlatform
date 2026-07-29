from __future__ import annotations
import json
import tempfile
import sys
import types
from pathlib import Path

# Isolate report aggregation from the application's configured PostgreSQL engine.
database_stub=types.ModuleType('trading_ai.database')
database_stub.SessionLocal=lambda: None
sys.modules['trading_ai.database']=database_stub
from trading_ai.market_overview.service import MarketOverviewService

def write(root: Path, name: str, payload: dict) -> None:
    path=root/"reports"/"trend_intelligence"/name
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(payload))

def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        common={"status":"READY","snapshot_timestamp":"2026-07-28T12:00:00+00:00"}
        write(root,"latest.json",{**common,"results":[
            {"symbol":"AAA","as_of_date":"2026-07-28","intermediate_term":"BULLISH","trend_stage":"ADVANCING","alignment_score":82,"trend_quality_score":75},
            {"symbol":"BBB","as_of_date":"2026-07-28","intermediate_term":"BEARISH","trend_stage":"DECLINING","alignment_score":31,"trend_quality_score":44},
        ]})
        write(root,"transitions_latest.json",{**common,"results":[
            {"symbol":"AAA","as_of_date":"2026-07-28","transition_state":"CONTINUATION","breakout_state":"BREAKOUT_WATCH","reversal_risk_score":10,"exhaustion_risk_score":12},
            {"symbol":"BBB","as_of_date":"2026-07-28","transition_state":"REVERSAL_WATCH","breakout_state":"IN_CHANNEL","reversal_risk_score":78,"exhaustion_risk_score":65},
        ]})
        write(root,"forecasts_latest.json",{**common,"results":[
            {"symbol":"AAA","as_of_date":"2026-07-28","horizon_days":10,"forecast_direction":"BULLISH","confidence_score":81},
            {"symbol":"BBB","as_of_date":"2026-07-28","horizon_days":10,"forecast_direction":"BEARISH","confidence_score":73},
        ]})
        write(root,"institutional_latest.json",{**common,"market_overview":{"participation_breadth_pct":50},"results":[
            {"symbol":"AAA","as_of_date":"2026-07-28","participation_score":79,"participation_state":"ACCUMULATION","leadership_state":"LEADER","deterioration_state":"STABLE","deterioration_risk_score":14},
            {"symbol":"BBB","as_of_date":"2026-07-28","participation_score":29,"participation_state":"DISTRIBUTION","leadership_state":"LAGGARD","deterioration_state":"DETERIORATING","deterioration_risk_score":88},
        ]})
        write(root,"phase6_latest.json",{**common,"score":99.6,"assessments":{},"milestone_52_closure_eligible":True})
        summary=MarketOverviewService(root=root).trend_intelligence_summary()
        assert summary["status"]=="READY", summary
        assert summary["breadth"]["bullish"]==1
        assert summary["breadth"]["bearish"]==1
        assert summary["breadth"]["transition_watch_count"]==1
        assert summary["top_strengthening"][0]["symbol"]=="AAA"
        assert summary["top_deteriorating"][0]["symbol"]=="BBB"
        assert summary["operations"]["score"]==99.6
        assert len(summary["symbols"])==2
    print("All Milestone 53 Trend Intelligence aggregation assertions passed.")

if __name__=="__main__":
    main()
