from __future__ import annotations
from dataclasses import asdict, is_dataclass
from html import escape
from pathlib import Path
from typing import Any

class PositionRiskOperationalReport:
    @staticmethod
    def _get(obj: Any, name: str, default=None):
        if obj is None: return default
        if isinstance(obj, dict): return obj.get(name, default)
        return getattr(obj, name, default)

    @staticmethod
    def _fmt(value: Any) -> str:
        return 'N/A' if value is None else escape(str(value))

    @staticmethod
    def _num(value: Any) -> str:
        try: return f'{float(value):,.2f}'
        except (TypeError, ValueError): return 'N/A'

    @staticmethod
    def _table(rows, columns):
        if not rows: return "<p class='note'>No records available.</p>"
        out='<table><thead><tr>'+''.join(f'<th>{escape(label)}</th>' for label,_ in columns)+'</tr></thead><tbody>'
        for row in rows:
            out += '<tr>'+''.join(f'<td>{row.get(key, "")}</td>' for _,key in columns)+'</tr>'
        return out+'</tbody></table>'

    def position_snapshot_html(self, snapshots):
        rows=[]
        for item in snapshots or ():
            rows.append({
                'id':self._fmt(self._get(item,'snapshot_id')),
                'account':self._fmt(self._get(item,'account_id')),
                'equity':self._num(self._get(item,'current_equity')),
                'pnl':self._num(self._get(item,'total_pnl')),
                'gross':self._num(self._get(item,'gross_exposure')),
                'net':self._num(self._get(item,'net_exposure')),
                'drawdown':self._num(self._get(item,'intraday_drawdown')),
                'positions':self._fmt(self._get(item,'open_position_count')),
                'stale':self._fmt(self._get(item,'stale_position_count')),
            })
        return "<section><h2>Real-Time Position Snapshots and Mark-to-Market</h2>"+self._table(rows,[('Snapshot','id'),('Account','account'),('Equity','equity'),('Total P&L','pnl'),('Gross Exposure','gross'),('Net Exposure','net'),('Drawdown','drawdown'),('Positions','positions'),('Stale','stale')])+'</section>'

    def greeks_html(self, states):
        rows=[]
        for item in states or ():
            rows.append({
                'id':self._fmt(self._get(item,'snapshot_id')),
                'delta':self._num(self._get(item,'delta')),
                'gamma':self._num(self._get(item,'gamma')),
                'vega':self._num(self._get(item,'vega')),
                'theta':self._num(self._get(item,'theta')),
                'rho':self._num(self._get(item,'rho')),
                'loss':self._num(self._get(item,'worst_scenario_loss')),
                'scenario':self._fmt(self._get(item,'worst_scenario_id')),
            })
        return "<section><h2>Portfolio Greeks, Exposure Surfaces, and Scenario Risk</h2>"+self._table(rows,[('Snapshot','id'),('Delta','delta'),('Gamma','gamma'),('Vega','vega'),('Theta','theta'),('Rho','rho'),('Worst Loss','loss'),('Worst Scenario','scenario')])+'</section>'

    def breach_html(self, breaches, alerts, escalations):
        breach_rows=[]
        for b in breaches or ():
            breach_rows.append({'id':self._fmt(self._get(b,'breach_id')),'metric':self._fmt(self._get(b,'metric')),'scope':self._fmt(f"{self._get(b,'scope_type','')}:{self._get(b,'scope_value','')}"),'observed':self._num(self._get(b,'observed_value')),'limit':self._num(self._get(b,'limit_value')),'severity':self._fmt(self._get(b,'severity')),'status':self._fmt(self._get(b,'status')),'count':self._fmt(self._get(b,'occurrence_count'))})
        alert_rows=[]
        for a in alerts or ():
            alert_rows.append({'id':self._fmt(self._get(a,'alert_id')),'breach':self._fmt(self._get(a,'breach_id')),'severity':self._fmt(self._get(a,'severity')),'channel':self._fmt(self._get(a,'channel')),'destination':self._fmt(self._get(a,'destination')),'status':self._fmt(self._get(a,'status'))})
        esc_rows=[]
        for e in escalations or ():
            esc_rows.append({'id':self._fmt(self._get(e,'escalation_id')),'breach':self._fmt(self._get(e,'breach_id')),'level':self._fmt(self._get(e,'level')),'target':self._fmt(self._get(e,'target_role')),'reason':self._fmt(self._get(e,'reason'))})
        return "<section><h2>Dynamic Limits, Breaches, Alerts, and Escalations</h2><h3>Breaches</h3>"+self._table(breach_rows,[('Breach','id'),('Metric','metric'),('Scope','scope'),('Observed','observed'),('Limit','limit'),('Severity','severity'),('Status','status'),('Occurrences','count')])+"<h3>Alerts</h3>"+self._table(alert_rows,[('Alert','id'),('Breach','breach'),('Severity','severity'),('Channel','channel'),('Destination','destination'),('Status','status')])+"<h3>Escalations</h3>"+self._table(esc_rows,[('Escalation','id'),('Breach','breach'),('Level','level'),('Target','target'),('Reason','reason')])+'</section>'

    def continuous_html(self, cycles):
        rows=[]
        for c in cycles or ():
            rows.append({'id':self._fmt(self._get(c,'cycle_id')),'account':self._fmt(self._get(c,'account_id')),'seq':self._fmt(self._get(c,'sequence_number')),'state':self._fmt(self._get(c,'state')),'stages':self._fmt(', '.join(self._get(c,'completed_stages',()) or ())),'failed':self._fmt(self._get(c,'failed_stage')),'breaches':self._fmt(self._get(c,'breach_count')),'reconciled':self._fmt(self._get(c,'reconciliation_allowed')),'kill':self._fmt(self._get(c,'kill_switch_activated'))})
        return "<section><h2>Continuous Monitoring, Reconciliation, and Kill-Switch Governance</h2>"+self._table(rows,[('Cycle','id'),('Account','account'),('Sequence','seq'),('State','state'),('Completed Stages','stages'),('Failed Stage','failed'),('Breaches','breaches'),('Reconciled','reconciled'),('Kill Switch','kill')])+'</section>'

    def generate(self, *, position_snapshots=(), greeks_states=(), breaches=(), alerts=(), escalations=(), cycles=(), path='reports/position_risk_monitoring_report.html') -> Path:
        target=Path(path); target.parent.mkdir(parents=True, exist_ok=True)
        html=("<!doctype html><html><head><meta charset='utf-8'><title>Position and Risk Monitoring Report</title><style>body{font-family:Arial,sans-serif;margin:24px;background:#f4f6f8;color:#1c2733}section{background:white;border:1px solid #d8e0e8;border-radius:8px;padding:18px;margin:16px 0}table{width:100%;border-collapse:collapse}th,td{border:1px solid #d8e0e8;padding:8px;text-align:left}th{background:#eef2f6}.note{color:#66788a}</style></head><body><h1>Real-Time Position and Risk Monitoring</h1><p>Milestone 30 Phase 7 operational report.</p>" + self.position_snapshot_html(position_snapshots) + self.greeks_html(greeks_states) + self.breach_html(breaches,alerts,escalations) + self.continuous_html(cycles) + "</body></html>")
        target.write_text(html, encoding='utf-8'); return target
