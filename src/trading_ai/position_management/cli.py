from __future__ import annotations
import argparse, json
from .reporting_service import PositionManagementReportingService
from .service import PositionMonitoringService

def build_parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="Milestone 39 position monitoring")
    sub=p.add_subparsers(dest="command",required=True)
    run=sub.add_parser("run")
    run.add_argument("--registry-file",default="data/portfolio/m36_portfolio_registry.json")
    run.add_argument("--marks-file",required=True)
    run.add_argument("--risk-control-file",default="reports/m37/execution_risk_control.json")
    run.add_argument("--output-dir",default="reports/m39")
    return p

def main(argv=None) -> int:
    args=build_parser().parse_args(argv)
    result=PositionMonitoringService().run(args.registry_file,args.marks_file,args.output_dir,args.risk_control_file)
    report=PositionManagementReportingService().render(result.assessment_file,result.instruction_file,result.report_file)
    payload=result.to_dict(); payload["report_file"]=report
    print(json.dumps(payload,indent=2)); return 0
