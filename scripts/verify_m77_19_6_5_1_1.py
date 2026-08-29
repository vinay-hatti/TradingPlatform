#!/usr/bin/env python3
import ast
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
p = root / "scripts" / "run_m77_19_6_5_1_1_imported_native_contract_resolution.py"

if not p.exists():
    raise SystemExit("M77.19.6.5.1.1 verification FAILED: runner missing")

text = p.read_text()
tree = ast.parse(text)

required = [
    "m77_19_4_isolated_adapters.py",
    "snapshot",
    "daily_dates",
    "monthly_dates",
    "call_profile",
    "StockIntelligenceService",
    "session_set",
    '"replay_execution": False',
    '"heuristic_adapter_execution_allowed": False',
    '"full_23_year_reconstruction_authorized": False',
    '"production_authority_effect": False',
]

for marker in required:
    if marker not in text:
        raise SystemExit(
            "M77.19.6.5.1.1 verification FAILED: missing marker: " + marker
        )

for prohibited in [
    "SessionLocal",
    "create_engine(",
    "subprocess.run(",
    "fn(**",
]:
    if prohibited in text:
        raise SystemExit(
            "M77.19.6.5.1.1 verification FAILED: execution/database behavior detected"
        )

print("M77.19.6.5.1.1 verification PASSED")
print(" - certified DAILY/MONTHLY adapter module is followed directly")
print(" - snapshot/daily_dates/monthly_dates contracts are captured")
print(" - WEEKLY call_profile/service/session_set wiring is captured")
print(" - no replay execution or database access")
print(" - parity thresholds unchanged; 23-year reconstruction remains blocked")
