from __future__ import annotations
import argparse,json
from trading_ai.database.session import SessionLocal
from trading_ai.live_trading_governance.service import LiveTradingGovernanceService

def main():
 p=argparse.ArgumentParser();p.add_argument('command',choices=['status','create-policy','request-approval','approve','certify','activate','halt','evaluate']);p.add_argument('--portfolio-id',default='LIVE-PRIMARY');p.add_argument('--actor',default='operator');p.add_argument('--approval-id');p.add_argument('--confirmation',default='');p.add_argument('--reason',default='');p.add_argument('--symbol',default='SPY');p.add_argument('--strategy',default='LONG_CALL');p.add_argument('--quantity',type=int,default=1);a=p.parse_args()
 with SessionLocal() as s:
  g=LiveTradingGovernanceService(s)
  if a.command=='status': out=g.status(a.portfolio_id)
  elif a.command=='create-policy': out=g.create_policy(a.portfolio_id,a.actor,{'allowed_symbols':[a.symbol],'allowed_strategies':[a.strategy],'allowed_order_types':['LMT'],'max_contracts':1})
  elif a.command=='request-approval': out=g.request_approval(a.portfolio_id,a.actor,a.reason)
  elif a.command=='approve': out=g.approve(a.approval_id,a.actor,a.reason)
  elif a.command=='certify': out=g.certify(a.portfolio_id,a.actor,{'platform_ready':True,'broker_account_verified':True,'management_ready':True,'kill_switch_tested':True})
  elif a.command=='activate': out=g.activate(a.portfolio_id,a.actor,a.confirmation)
  elif a.command=='halt': out=g.halt(a.portfolio_id,a.actor,a.reason or 'Operator halt')
  else: out=g.evaluate_order(a.portfolio_id,{'symbol':a.symbol,'strategy':a.strategy,'order_type':'LMT','quantity':a.quantity,'maximum_loss_pct':.25},{'platform_ready':True,'execution_ready':True,'portfolio_ready':True,'management_ready':True})
 print(json.dumps(out,indent=2,default=str))
if __name__=='__main__':main()
