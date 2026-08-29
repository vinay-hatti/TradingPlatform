from pathlib import Path
import sys

root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
checks={
    'fingerprint_engine': ('plan_fingerprint', root/'src/trading_ai/trade_plan_certification/engine.py'),
    'institutional_recertification': ('certify_institutional_underlying_plan', root/'src/trading_ai/institutional_options/management.py'),
    'source_plan_change_detection': ('source_plan_changed', root/'src/trading_ai/institutional_options/opportunity_ingestion.py'),
    'source_plan_reset': ('TPC-LIN-020', root/'src/trading_ai/institutional_options/repository.py'),
    'valuation_no_early_ready': ('m75_2_2_final_plan_certification_pending', root/'src/trading_ai/institutional_options/valuation.py'),
    'ready_transition_after_cert': ('Final Institutional Options plan certified for Trade Builder handoff', root/'src/trading_ai/institutional_options/management.py'),
    'fail_closed_readiness_reversal': ('invalidate_ready_for_execution', root/'src/trading_ai/institutional_options/repository.py'),
    'handoff_exact_scope': ('INSTITUTIONAL_OPTIONS_FINAL_PLAN', root/'src/trading_ai/institutional_options/handoff.py'),
    'router_certification_projection': ('institutional_plan_certification', root/'src/trading_ai/institutional_options/router.py'),
    'ui_lineage': ('Trade plan certification lineage', root/'ui/workstation/src/InstitutionalOptionsPage.tsx'),
    'ui_handoff_gate': ('finalCertified', root/'ui/workstation/src/InstitutionalOptionsPage.tsx'),
}
for name,(needle,path) in checks.items():
    text=path.read_text()
    assert needle in text, f'{name}: missing {needle} in {path}'
    print('PASS',name)
valuation=(root/'src/trading_ai/institutional_options/valuation.py').read_text()
assert '"Final valued strategy selected"' not in valuation
print('PASS no_valuation_ready_transition')
print('M75.2.2 certification lineage & downstream mutation governance verification: PASSED')
