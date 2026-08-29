from pathlib import Path

REQUIRED = (
    "deployment_automation_policy.py",
    "deployment_automation_profile.py",
    "deployment_adapter.py",
    "deployment_health_gate.py",
    "blue_green_deployment_service.py",
    "canary_deployment_service.py",
    "rollback_execution_service.py",
    "deployment_orchestrator.py",
    "deployment_automation_report.py",
    "deployment_automation_cli.py",
)

def main():
    root = Path(__file__).resolve().parents[1]
    package = root / "src/trading_ai/deployment"
    for name in REQUIRED:
        assert (package / name).exists(), name
    status = (root / "updated_PROJECT_STATUS.md").read_text(encoding="utf-8")
    assert "Step 3" in status
    assert "COMPLETE" in status
    assert "Step 4" in status
    print("All Milestone 30 Phase 10 Step 3 closure assertions passed.")

if __name__ == "__main__":
    main()
