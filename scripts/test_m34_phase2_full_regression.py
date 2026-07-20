import subprocess
import sys


SCRIPTS = (
    "scripts/test_m34_phase2_step1_candidate_analysis_engine.py",
    "scripts/test_m34_phase2_step1_candidate_analysis_warnings.py",
    "scripts/test_m34_phase2_step2_option_chain_explorer.py",
    "scripts/test_m34_phase2_step2_option_chain_edge_cases.py",
    "scripts/test_m34_phase2_step3_greeks_payoff_backend.py",
    "scripts/test_m34_phase2_step3_strategy_edge_cases.py",
    "scripts/test_m34_phase2_step4_institutional_explainability.py",
    "scripts/test_m34_phase2_step4_scenario_stress.py",
    "scripts/test_m34_phase2_step5_dashboard_reporting.py",
)


def main() -> None:
    for script in SCRIPTS:
        completed = subprocess.run(
            [sys.executable, script],
            check=False,
            text=True,
            capture_output=True,
        )
        if completed.returncode != 0:
            print(completed.stdout)
            print(completed.stderr, file=sys.stderr)
            raise SystemExit(
                f"Phase 2 regression failed: {script}"
            )
        print(completed.stdout.strip())

    print(
        "All Milestone 34 Phase 2 full-regression assertions passed."
    )


if __name__ == "__main__":
    main()
