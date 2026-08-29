import argparse,json
from pathlib import Path
from trading_ai.paper_trading.paper_trading_reporting import PaperTradingOperationalReport
def load(p,key):
 q=Path(p) if p else None
 if not q or not q.exists(): return ()
 x=json.loads(q.read_text());return tuple(x.get(key,x if isinstance(x,list) else ()))
def main():
 a=argparse.ArgumentParser();a.add_argument('--runtime-json');a.add_argument('--executions-json');a.add_argument('--positions-json');a.add_argument('--checkpoints-json');a.add_argument('--output',default='reports/paper_trading_operational_report.html');x=a.parse_args()
 p=PaperTradingOperationalReport().generate(runtime_states=load(x.runtime_json,'sessions'),executions=load(x.executions_json,'executions'),positions=load(x.positions_json,'positions'),checkpoints=load(x.checkpoints_json,'checkpoints'),path=x.output);print(f'Paper-trading operational report: {p}')
if __name__=='__main__':main()
