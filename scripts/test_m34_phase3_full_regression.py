import subprocess
import sys


SCRIPTS = (
    "scripts/test_m34_phase3_step1_strategy_blueprint_trade_ticket.py",
    "scripts/test_m34_phase3_step1_trade_construction_governance.py",
    "scripts/test_m34_phase3_step2_position_sizing.py",
    "scripts/test_m34_phase3_step2_portfolio_allocation.py",
    "scripts/test_m34_phase3_step2_portfolio_governance.py",
    "scripts/test_m34_phase3_step3_trade_lifecycle.py",
    "scripts/test_m34_phase3_step3_adjustment_planning.py",
    "scripts/test_m34_phase3_step3_lifecycle_governance.py",
    "scripts/test_m34_phase3_step4_pretrade_auto_approval.py",
    "scripts/test_m34_phase3_step4_pretrade_escalation.py",
    "scripts/test_m34_phase3_step4_pretrade_rejection.py",
    "scripts/test_m34_phase3_step4_pretrade_override.py",
    "scripts/test_m34_phase3_step5_dashboard_reporting.py",
    "scripts/test_m34_phase3_step5_blocked_dashboard.py",
)


def main() -> None:
    missing = []
    failures = []

    for script in SCRIPTS:
        try:
            completed = subprocess.run(
                [sys.executable, script],
                text=True,
                capture_output=True,
            )
        except OSError as exc:
            failures.append(f"{script}: {exc}")
            continue

        if completed.returncode == 2 and "No such file" in completed.stderr:
            missing.append(script)
            continue

        if completed.returncode != 0:
            failures.append(
                f"{script}\nSTDOUT:\n{completed.stdout}\n"
                f"STDERR:\n{completed.stderr}"
            )

    if missing:
        raise AssertionError(
            "Missing Phase 3 regression scripts:\n"
            + "\n".join(missing)
        )

    if failures:
        raise AssertionError(
            "Phase 3 regression failures:\n"
            + "\n\n".join(failures)
        )

    print(
        "All Milestone 34 Phase 3 full-regression "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
