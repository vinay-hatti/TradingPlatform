from trading_ai.execution_intelligence.policy import ExecutionIntelligencePolicy, load_execution_intelligence_policy
from trading_ai.execution_intelligence.entry_chase import working_order_lifetime_phase
from trading_ai.execution_intelligence.auto_fill import AutomaticEntryFillManager

checks={}
p=ExecutionIntelligencePolicy()
checks['version']=AutomaticEntryFillManager.VERSION.startswith('M73.0.8-') and p.policy_version.startswith('M73.0.8-')
checks['default_active_chase_180']=p.active_chase_window_seconds==180.0
checks['default_hard_timeout_600']=p.working_order_max_age_seconds==600.0
checks['active_phase']=working_order_lifetime_phase(179.9,180,600)['phase']=='ACTIVE_CHASE'
checks['resting_at_180']=working_order_lifetime_phase(180,180,600)=={'phase':'RESTING','reason':'RESTING_AT_FINAL_LIMIT','cancel_required':False}
checks['resting_at_181']=working_order_lifetime_phase(181,180,600)['phase']=='RESTING'
checks['resting_before_600']=working_order_lifetime_phase(599.9,180,600)['phase']=='RESTING'
checks['hard_timeout_after_600']=working_order_lifetime_phase(600.1,180,600)=={'phase':'HARD_TIMEOUT','reason':'ORDER_AGE_EXCEEDED','cancel_required':True}
for k,v in checks.items(): print(f'{k}: {"PASS" if v else "FAIL"}')
assert all(checks.values()),checks
print('M73.0.8 Adaptive Working-Order Lifetime Governance verifier: PASS')
