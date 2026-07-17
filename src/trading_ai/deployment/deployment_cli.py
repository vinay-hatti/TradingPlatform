import argparse
from .deployment_governance_report import DeploymentGovernanceReportBuilder
def _report(args):
 p=DeploymentGovernanceReportBuilder().write(args.output);print(f'Deployment governance report written: {p}');return 0
def _stub(action):
 def f(args):print(f'Deployment action registered: {action}');return 0
 return f
def register_deployment_commands(subparsers):
 d=subparsers.add_parser('deployment');c=d.add_subparsers(dest='deployment_command',required=True)
 r=c.add_parser('report');r.add_argument('--output',default='reports/deployment_governance_report.html');r.set_defaults(func=_report)
 for n in ('validate','approve','promote','rollback-plan'):c.add_parser(n).set_defaults(func=_stub(n))
def main(argv=None):
 p=argparse.ArgumentParser();s=p.add_subparsers(dest='command',required=True);register_deployment_commands(s);a=p.parse_args(argv);return int(a.func(a))
if __name__=='__main__':raise SystemExit(main())
