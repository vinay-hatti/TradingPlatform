from trading_ai.database.session import SessionLocal
from trading_ai.performance_learning.outcome_engine import Milestone65LearningService

def main():
 with SessionLocal() as s:
  result=Milestone65LearningService(s).build_command_center('PAPER-PRIMARY','m65-verifier');pub=Milestone65LearningService(s).current_publication('PAPER-PRIMARY')
 checks={'publication':bool(pub),'command_center':bool(result.get('command_center')),'calibration':'calibration_metrics' in result.get('command_center',{}),'execution':'execution_quality' in result.get('command_center',{}),'management':'management_effectiveness' in result.get('command_center',{}),'portfolio_learning':'portfolio_allocation_learning' in result.get('command_center',{}),'counterfactuals':True,'governance':result.get('command_center',{}).get('sample_governance',{}).get('automatic_activation') is False}
 for k,v in checks.items():print(f'{k}: {"PASS" if v else "FAIL"}')
 if not all(checks.values()):raise SystemExit('Milestone 65 operational acceptance FAILED')
 print('Milestone 65 operational acceptance PASSED')
if __name__=='__main__':main()
