import json
from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.ui.models.executive_reporting import RegulatoryExportRequest
from trading_ai.ui.services.executive_reporting_service import ExecutiveReportingService

def main():
    with TemporaryDirectory() as d:
        root=Path(d)
        reports=root/"reports"
        exports=root/"exports"
        reports.mkdir()

        (reports/"portfolio_summary.json").write_text(json.dumps({
            "summary":{"total_net_pnl":2500,"gross_exposure":50000,"net_exposure":12000}
        }))
        (reports/"walk_forward_metrics.json").write_text(json.dumps({
            "runs":[{"win_rate":0.62,"sharpe_ratio":1.4,"max_drawdown":-0.08}]
        }))
        (reports/"strategy_studio_state.json").write_text(json.dumps({
            "promotions":{"options_momentum":{"version_id":"sv-1"}}
        }))
        (reports/"operations_command_center_state.json").write_text(json.dumps({
            "incidents":[{"status":"OPEN"}],
            "alerts":[{"severity":"CRITICAL","acknowledged":False}]
        }))
        (reports/"security_compliance_state.json").write_text(json.dumps({
            "access_reviews":[{"status":"OPEN"}]
        }))
        audit=reports/"audit_events.jsonl"
        audit.write_text(json.dumps({"event_type":"TEST"})+"\n")

        svc=ExecutiveReportingService(reports,exports)
        score=svc.scorecard()
        assert score.total_net_pnl==2500
        assert score.win_rate==0.62
        assert score.active_incidents==1
        assert score.critical_alerts==1
        assert score.open_access_reviews==1

        board=svc.board_report()
        assert len(board.sections)==4

        export=svc.regulatory_export(RegulatoryExportRequest(
            export_type="FULL_EVIDENCE_PACKAGE"))
        assert Path(export.output_path).exists()
        assert len(export.checksum)==64

    print("All Milestone 33 Phase 9 Executive Reporting assertions passed.")

if __name__=="__main__":
    main()
