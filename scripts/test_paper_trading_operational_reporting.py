import tempfile
from pathlib import Path
from trading_ai.paper_trading.paper_trading_reporting import PaperTradingOperationalReport
def main():
 with tempfile.TemporaryDirectory() as t:
  p=PaperTradingOperationalReport().generate(runtime_states=({'session':'s','cycle_count':1,'orders_submitted':2,'fills_received':2,'open_positions':1,'realized_pnl':10},),executions=({'execution_key':'e','aggregate_id':'a','status':'FILLED','filled_quantity':1,'average_fill_price':5,'commissions':.65,'latency_ms':100},),positions=({'position_id':'p','symbol':'AAPL','state':'OPEN','quantity':1,'average_cost':5,'realized_pnl':0,'unrealized_pnl':20},),checkpoints=({'checkpoint_id':'c','session_id':'s','cycle_id':'cy','stage':'COMPLETE','state':'COMPLETED','retry_count':0,'last_error':None},),path=Path(t)/'r.html')
  h=p.read_text()
  for x in ('Session Runtime and Automation Cycles','Paper Execution, Slippage, Commission, and Latency','Position Lifecycle, Cost Basis, P&L, Exits, and Adjustments','Restart Recovery and Automation Checkpoints','Paper Trading Operational Diagnostics'):assert x in h
 print('All paper-trading operational reporting assertions passed.')
if __name__=='__main__':main()
