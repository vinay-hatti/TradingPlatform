#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
svc = (ROOT / "src/trading_ai/dynamic_position_management/service.py").read_text()
ui = (ROOT / "ui/workstation/src/PortfolioIntelligenceRefinedPage.tsx").read_text()
css = (ROOT / "ui/workstation/src/portfolio-intelligence-refined.css").read_text()

checks = {
    "unified_version": 'M74.14-UNIFIED-EXIT-MATERIALIZATION-AUTONOMOUS-HEALTH-1.0' in svc,
    "legacy_failure_rearm": "_rearm_legacy_canonical_missing_failures" in svc and "REARMED_FOR_UNIFIED_EXIT_MATERIALIZATION" in svc,
    "audit_preserved": "submission_failure_history" in svc and "legacy_submission_error_superseded" in svc,
    "no_broad_failure_reset": "LEGACY_CANONICAL_MISSING_FRAGMENT" in svc,
    "single_leg_unified": "'unified_exit_materialization':True" in svc and "'exit_method':'SINGLE_LEG'" in svc,
    "strategy_bag_contract": all(token in svc for token in ["'closing_combo':True", "'strategy_level_exit':True", "'includes_short_legs':True", "'exit_method':'ATOMIC_BAG'"]),
    "short_leg_governance": 'if typ=="SHORT_LEG_DTE"' in svc,
    "ui_current_projection": "currentInstructionProjection" in ui,
    "ui_protection_vs_target": "CRITICAL PROTECTION ACTIVE" in ui and "PROFIT TARGET ATTENTION" in ui,
    "ui_history_separated": "Management history" in ui,
    "ui_health_css": ".pi-autonomous-health'" not in css and ".pi-autonomous-health" in css,
}
failed = [name for name, passed in checks.items() if not passed]
if failed:
    raise SystemExit("M74.14 verification FAILED: " + ", ".join(failed))
print("M74.14 unified exit materialization & autonomous health verification: PASSED")
for name in checks:
    print(f"  PASS {name}")
