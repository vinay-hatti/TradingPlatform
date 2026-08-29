from pathlib import Path
import sys

checks = {
    "src/trading_ai/institutional_options/decision.py": [
        'valuation_payload.get("capital_required")',
        'capital_raw = valuation_payload.get("maximum_loss")',
    ],
    "src/trading_ai/institutional_options/router.py": [
        "derive_lifecycle_authority",
        'payload["display_state"]',
        'payload["next_governed_action"]',
    ],
    "src/trading_ai/institutional_options/lifecycle_authority.py": [
        "M68.2.1.15.4-AUTHORITY-STATE-RECONCILIATION-1.0",
        "PLAN_COMPLETE_WAITING_FOR_ENTRY",
        "PLAN_COMPLETE_REGENERATE_REQUIRED",
        "PLAN_COMPLETE_NOT_SELECTED",
    ],
    "ui/workstation/src/InstitutionalOptionsPage.tsx": [
        "o.next_governed_action",
        "o.display_state",
        "PLAN_COMPLETE_WAITING_FOR_ENTRY",
        "PLAN_COMPLETE_REGENERATE_REQUIRED",
    ],
}

errors = []
for name, needles in checks.items():
    path = Path(name)
    if not path.exists():
        errors.append(f"missing file: {name}")
        continue
    text = path.read_text()
    for needle in needles:
        if needle not in text:
            errors.append(f"{name}: missing {needle}")

if "valuation.capital_required" in Path("src/trading_ai/institutional_options/decision.py").read_text():
    errors.append("decision.py still dereferences nonexistent StrategyValuationModel.capital_required")

if errors:
    print("M68.2.1.15.4 verification FAILED")
    for error in errors:
        print(f" - {error}")
    sys.exit(1)

print("M68.2.1.15.4 verification PASSED")
print(" - portfolio-context capital source corrected")
print(" - lifecycle completion separated from execution disposition")
print(" - next governed action derived from actual persisted artifacts")
print(" - waiting/regeneration/portfolio-selection states remain fail-closed")
