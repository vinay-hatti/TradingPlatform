import csv, json
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import date
from trading_ai.ui.models.research_workbench import ReplayRequest, ScannerQuery
from trading_ai.ui.services.research_workbench_service import ResearchWorkbenchService

def main():
    with TemporaryDirectory() as d:
        root=Path(d); reports=root/"reports"; data=root/"data"; reports.mkdir(); data.mkdir()
        (reports/"scanner_results.json").write_text(json.dumps({"results":[{"symbol":"AAPL","date":"2026-07-17","signal":"CALL","call_score":82,"put_score":35,"market_regime":"TREND_UP","rsi14":62,"atr14":4.2}]}))
        (reports/"feature_importance.json").write_text(json.dumps({"feature_importance":{"rsi14":0.4,"atr14":0.3,"macd":0.2}}))
        (reports/"walk_forward_metrics.json").write_text(json.dumps({"runs":[{"run_id":"wf-1","symbol":"AAPL","test_end":"2026-07-17","net_pnl":1200,"win_rate":0.6,"sharpe_ratio":1.2,"max_drawdown":-0.08,"trades":20}]}))
        with (data/"AAPL_features.csv").open("w",newline="") as f:
            w=csv.DictWriter(f,fieldnames=["date","close","rsi14","atr14","call_score","put_score","signal","market_regime"]); w.writeheader()
            w.writerow({"date":"2026-07-17","close":210,"rsi14":62,"atr14":4.2,"call_score":82,"put_score":35,"signal":"CALL","market_regime":"TREND_UP"})
        svc=ResearchWorkbenchService(reports,data)
        assert len(svc.scanner(ScannerQuery(symbols=["AAPL"],signal="CALL",min_score=50)))==1
        assert svc.feature_importance()[0].feature=="rsi14"
        assert svc.walk_forward_runs()[0].run_id=="wf-1"
        replay=svc.replay(ReplayRequest(symbol="AAPL",start=date(2026,7,17),end=date(2026,7,17)))
        assert len(replay)==1 and replay[0].signal=="CALL"
    print("All Milestone 33 Phase 5 Research Workbench assertions passed.")
if __name__=="__main__": main()
