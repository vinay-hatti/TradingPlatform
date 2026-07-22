from __future__ import annotations
import argparse, json
from pathlib import Path
from .reporting_service import ExecutionOrchestrationReportingService
from .service import ExecutionOrchestrationService

def main(argv=None):
    p=argparse.ArgumentParser(description='Milestone 38 execution orchestration'); sub=p.add_subparsers(dest='command',required=True)
    run=sub.add_parser('run'); run.add_argument('--handoff-file',type=Path,default=Path('reports/m36/phase2/execution_handoff.json')); run.add_argument('--risk-control-file',type=Path,default=Path('reports/m37/execution_risk_control.json')); run.add_argument('--output-dir',type=Path,default=Path('reports/m38'))
    approve=sub.add_parser('approve'); approve.add_argument('--execution-order-id',required=True); approve.add_argument('--approved-by',required=True); approve.add_argument('--output-dir',type=Path,default=Path('reports/m38'))
    rec=sub.add_parser('reconcile'); rec.add_argument('--broker-state-file',type=Path,required=True); rec.add_argument('--output-dir',type=Path,default=Path('reports/m38'))
    report=sub.add_parser('report'); report.add_argument('--output-dir',type=Path,default=Path('reports/m38'))
    args=p.parse_args(argv); svc=ExecutionOrchestrationService()
    if args.command=='run': payload=svc.run(args.handoff_file,args.risk_control_file,args.output_dir).to_dict(); ExecutionOrchestrationReportingService().generate(args.output_dir)
    elif args.command=='approve': payload=svc.approve(args.output_dir/'execution_queue.json',args.output_dir/'execution_events.json',args.execution_order_id,args.approved_by)
    elif args.command=='reconcile': payload=svc.reconcile_broker_state(args.output_dir/'execution_queue.json',args.output_dir/'execution_events.json',args.broker_state_file); ExecutionOrchestrationReportingService().generate(args.output_dir)
    else: payload=ExecutionOrchestrationReportingService().generate(args.output_dir)
    print(json.dumps(payload,indent=2,default=str)); return 0
