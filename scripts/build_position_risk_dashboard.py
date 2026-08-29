from __future__ import annotations
import argparse, json
from pathlib import Path
from trading_ai.position_monitoring.position_risk_dashboard import PositionRiskDashboardBuilder

def latest(path,key,account=None):
    p=Path(path)
    if not p.exists(): return None
    data=json.loads(p.read_text(encoding='utf-8')).get(key,{})
    vals=list(data.values()) if isinstance(data,dict) else list(data)
    if account: vals=[v for v in vals if v.get('account_id')==account]
    return max(vals,key=lambda v:v.get('created_at') or v.get('started_at') or '') if vals else None

def all_values(path,key):
    p=Path(path)
    if not p.exists(): return ()
    data=json.loads(p.read_text(encoding='utf-8')).get(key,{})
    return tuple(data.values()) if isinstance(data,dict) else tuple(data)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--account-id')
    ap.add_argument('--snapshots-json',default='data/position_monitoring/snapshots.json')
    ap.add_argument('--greeks-json',default='data/position_monitoring/portfolio_greeks.json')
    ap.add_argument('--breaches-json',default='data/position_monitoring/risk_breaches.json')
    ap.add_argument('--alerts-json',default='data/position_monitoring/risk_alerts.json')
    ap.add_argument('--cycles-json',default='data/position_monitoring/continuous_cycles.json')
    ap.add_argument('--output',default='reports/position_risk_dashboard.json'); a=ap.parse_args()
    b=PositionRiskDashboardBuilder(); payload=b.build_payload(position_state=latest(a.snapshots_json,'snapshots',a.account_id),greeks_state=latest(a.greeks_json,'snapshots',a.account_id),breaches=all_values(a.breaches_json,'breaches'),alerts=all_values(a.alerts_json,'alerts'),cycle_state=latest(a.cycles_json,'cycles',a.account_id)); path=b.write(payload,a.output); print(f'Position and risk dashboard payload: {path}')
if __name__=='__main__': main()
