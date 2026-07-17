from __future__ import annotations
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any
import json

class PositionRiskDashboardBuilder:
    @staticmethod
    def _dict(value: Any) -> dict[str, Any]:
        if value is None: return {}
        if is_dataclass(value): return asdict(value)
        return dict(value)

    def build_payload(self, *, position_state=None, greeks_state=None, breaches=(), alerts=(), escalations=(), cycle_state=None) -> dict[str, Any]:
        p=self._dict(position_state); g=self._dict(greeks_state); c=self._dict(cycle_state)
        open_breaches=[self._dict(b) for b in breaches if self._dict(b).get('status','OPEN')!='RESOLVED']
        return {
            'schema_version':'1.0',
            'summary':{
                'account_id':p.get('account_id') or g.get('account_id') or c.get('account_id'),
                'current_equity':p.get('current_equity'),
                'total_pnl':p.get('total_pnl'),
                'gross_exposure':p.get('gross_exposure'),
                'net_exposure':p.get('net_exposure'),
                'intraday_drawdown':p.get('intraday_drawdown'),
                'portfolio_delta':g.get('delta'),
                'portfolio_gamma':g.get('gamma'),
                'worst_scenario_loss':g.get('worst_scenario_loss'),
                'open_breach_count':len(open_breaches),
                'critical_breach_count':sum(1 for b in open_breaches if b.get('severity')=='CRITICAL'),
                'kill_switch_activated':c.get('kill_switch_activated',False),
                'monitoring_state':c.get('state'),
            },
            'position_state':p,
            'greeks_state':g,
            'breaches':[self._dict(v) for v in breaches],
            'alerts':[self._dict(v) for v in alerts],
            'escalations':[self._dict(v) for v in escalations],
            'continuous_cycle':c,
        }

    def write(self, payload: dict[str, Any], path='reports/position_risk_dashboard.json') -> Path:
        target=Path(path); target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2, sort_keys=True)+'\n', encoding='utf-8'); return target
