from __future__ import annotations
from pathlib import Path
from html import escape
class PaperTradingOperationalReport:
 def _v(self,o,n,d=None): return o.get(n,d) if isinstance(o,dict) else getattr(o,n,d)
 def generate(self,*,runtime_states=(),executions=(),positions=(),checkpoints=(),path='reports/paper_trading_operational_report.html'):
  p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
  def rows(items,cols):
   if not items:return '<p>No records available.</p>'
   h='<table><tr>'+''.join(f'<th>{escape(a)}</th>' for a,_ in cols)+'</tr>'
   for x in items:h+='<tr>'+''.join(f'<td>{escape(str(self._v(x,k,"N/A")))}</td>' for _,k in cols)+'</tr>'
   return h+'</table>'
  html=f'''<!doctype html><html><head><meta charset="utf-8"><title>Paper Trading Operations</title><style>body{{font-family:Arial;margin:24px;background:#f4f6f8}}section{{background:white;padding:16px;margin:14px 0}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccc;padding:7px}}</style></head><body><h1>Paper Trading Automation Operations</h1>
<section><h2>Session Runtime and Automation Cycles</h2>{rows(runtime_states,[('Session','session'),('Cycles','cycle_count'),('Submitted','orders_submitted'),('Fills','fills_received'),('Open Positions','open_positions'),('Realized P&L','realized_pnl')])}</section>
<section><h2>Paper Execution, Slippage, Commission, and Latency</h2>{rows(executions,[('Execution','execution_key'),('Aggregate','aggregate_id'),('Status','status'),('Filled','filled_quantity'),('Price','average_fill_price'),('Commission','commissions'),('Latency','latency_ms')])}</section>
<section><h2>Position Lifecycle, Cost Basis, P&L, Exits, and Adjustments</h2>{rows(positions,[('Position','position_id'),('Symbol','symbol'),('State','state'),('Quantity','quantity'),('Cost','average_cost'),('Realized','realized_pnl'),('Unrealized','unrealized_pnl')])}</section>
<section><h2>Restart Recovery and Automation Checkpoints</h2>{rows(checkpoints,[('Checkpoint','checkpoint_id'),('Session','session_id'),('Cycle','cycle_id'),('Stage','stage'),('State','state'),('Retries','retry_count'),('Error','last_error')])}</section>
<section><h2>Paper Trading Operational Diagnostics</h2><p>Checkpoint failures, recovery state, working executions, and active positions are surfaced above.</p></section></body></html>'''
  p.write_text(html);return p
