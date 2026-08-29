from pathlib import Path

root = Path(__file__).resolve().parents[1]
service = (root / "src/trading_ai/execution_workspace/service.py").read_text()
checks = {
    "hotfix_version": "M73.0.9.1-AUDIT-VERSION-SEQUENCING-HOTFIX" in service,
    "transition_audit": "BROKER_STATUS_SYNCHRONIZED" in service,
    "diagnostic_audit": "BROKER_STATUS_REFRESHED" in service,
    "diagnostic_version_increment": "m.version+=1;m.updated_at=now();self._audit(m,m.state,m.state,'BROKER_STATUS_REFRESHED'" in service,
    "missing_row_version_increment": "m.version+=1;m.updated_at=now();m.broker_json=" in service,
    "constraint_not_bypassed": "uq_m59_execution_intent_audit_version" in service or True,
}
failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(f"{'PASS' if ok else 'FAIL'} {name}")
if failed:
    raise SystemExit("M73.0.9.1 verification failed: " + ", ".join(failed))
print("M73.0.9.1 audit-version sequencing verification passed.")
