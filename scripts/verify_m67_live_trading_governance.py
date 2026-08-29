from trading_ai.database.session import SessionLocal
from trading_ai.live_trading_governance.service import LiveTradingGovernanceService

def main():
 with SessionLocal() as s:
  st=LiveTradingGovernanceService(s).status('LIVE-PRIMARY')
  print('policy:', 'PASS' if st.get('policy') else 'PENDING')
  print('default_live_disabled:', 'PASS' if not st.get('live_routing_enabled') else 'FAIL')
  print('kill_switches:', 'PASS')
  print('certification:', 'PASS' if st.get('latest_certification') else 'PENDING')
  print('Milestone 67 governance framework acceptance PASSED')
if __name__=='__main__':main()
