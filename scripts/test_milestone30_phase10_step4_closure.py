from __future__ import annotations

from pathlib import Path


REQUIRED = (
    "operational_governance_policy.py",
    "operational_governance_profile.py",
    "operational_runbook_service.py",
    "disaster_recovery_service.py",
    "compliance_governance_service.py",
    "production_governance_service.py",
    "operational_governance_service.py",
    "operational_governance_report.py",
    "operational_governance_cli.py",
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    package = root / "src/trading_ai/deployment"

    missing = [
        name for name in REQUIRED
        if not (package / name).exists()
    ]
    assert not missing, "Missing Step 4 modules: " + ", ".join(missing)

    status_candidates = (
        root / "updated_PROJECT_STATUS.md",
        root / "PROJECT_STATUS.md",
    )
    status_path = next(
        (
            path for path in status_candidates
            if path.exists()
            and "Phase 10" in path.read_text(encoding="utf-8")
            and "Step 4" in path.read_text(encoding="utf-8")
        ),
        None,
    )
    assert status_path is not None, (
        "No current project status contains Phase 10 Step 4."
    )

    status = status_path.read_text(encoding="utf-8")
    step4_lines = [
        line for line in status.splitlines()
        if "Step 4" in line
    ]
    assert any("COMPLETE" in line for line in step4_lines), (
        f"Step 4 is not marked complete in {status_path.name}"
    )
    assert "Step 5" in status
    assert "PENDING" in status

    print(
        "All Milestone 30 Phase 10 Step 4 closure assertions passed "
        f"using {status_path.name}."
    )


if __name__ == "__main__":
    main()
