from __future__ import annotations
import argparse, json
from pathlib import Path
from trading_ai.position_monitoring.position_risk_reporting import PositionRiskOperationalReport

def load(path, key):
    p=Path(path)
    if not p.exists(): return ()
    data=json.loads(p.read_text(encoding='utf-8'))
    if isinstance(data,list): return data
    return data.get(key, ())

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--snapshots-json',default='data/position_monitoring/snapshots.json')
    ap.add_argument('--greeks-json',default='data/position_monitoring/portfolio_greeks.json')
    ap.add_argument('--breaches-json',default='data/position_monitoring/risk_breaches.json')
    ap.add_argument('--alerts-json',default='data/position_monitoring/risk_alerts.json')
    ap.add_argument('--cycles-json',default='data/position_monitoring/continuous_cycles.json')
    ap.add_argument('--output',default='reports/position_risk_monitoring_report.html')
    a=ap.parse_args()
    snapshots=tuple(load(a.snapshots_json,'snapshots').values()) if isinstance(load(a.snapshots_json,'snapshots'),dict) else load(a.snapshots_json,'snapshots')
    greeks=tuple(load(a.greeks_json,'snapshots').values()) if isinstance(load(a.greeks_json,'snapshots'),dict) else load(a.greeks_json,'snapshots')
    breaches=tuple(load(a.breaches_json,'breaches').values()) if isinstance(load(a.breaches_json,'breaches'),dict) else load(a.breaches_json,'breaches')
    alerts=tuple(load(a.alerts_json,'alerts').values()) if isinstance(load(a.alerts_json,'alerts'),dict) else load(a.alerts_json,'alerts')
    cycles=tuple(load(a.cycles_json,'cycles').values()) if isinstance(load(a.cycles_json,'cycles'),dict) else load(a.cycles_json,'cycles')
    path=PositionRiskOperationalReport().generate(position_snapshots=snapshots,greeks_states=greeks,breaches=breaches,alerts=alerts,cycles=cycles,path=a.output)
    print(f'Position and risk monitoring report: {path}')
if __name__=='__main__': main()
