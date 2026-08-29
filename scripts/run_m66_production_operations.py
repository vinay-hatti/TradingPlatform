import argparse,json,time
from trading_ai.database.session import SessionLocal
from trading_ai.production_operations.service import ProductionOperationsService
def once(simulate=True):
 with SessionLocal() as s:return ProductionOperationsService(s).run_workflow('SIMULATION' if simulate else 'EXECUTION','m66-daemon')
def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--daemon',action='store_true');p.add_argument('--interval-seconds',type=int,default=300);a=p.parse_args()
 while True:
  print(json.dumps(once(not a.execute),indent=2,default=str),flush=True)
  if not a.daemon:break
  time.sleep(max(60,a.interval_seconds))
if __name__=='__main__':main()
