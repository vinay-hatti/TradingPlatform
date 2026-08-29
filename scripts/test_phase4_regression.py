from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_TESTS = (
    "scripts/test_distribution_risk_engine.py",
    "scripts/test_risk_surface_engine.py",
    "scripts/test_portfolio_risk_surface.py",
    "scripts/test_institutional_decision_engine.py",
    "scripts/test_risk_surface_reporting.py",
)

OPTIONAL_TESTS = (
    "scripts/test_probability_engine.py",
    "scripts/test_scenario_engine.py",
)


def run(command: list[str]) -> None:
    print(f"\n$ {' '.join(command)}")
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def validate_serialization() -> None:
    from trading_ai.strategy_engine.decision_serialization import serialize_value
    from trading_ai.strategy_engine.risk_surface_policy import RiskSurfacePolicy
    from trading_ai.strategy_engine.risk_surface_service import RiskSurfaceService

    service = RiskSurfaceService(policy=RiskSurfacePolicy())
    profile = service.analyze_strategy(
        symbol="REGRESSION",
        strategy="BULL_CALL_SPREAD",
        underlying_price=100.0,
        implied_volatility=0.30,
        days_to_expiration=30,
        capital_required=5000.0,
        initial_capital=100000.0,
        net_delta=0.35,
        net_gamma=0.025,
        net_vega=0.18,
        net_theta=-0.04,
        net_rho=0.01,
    )

    payload = serialize_value(profile)
    encoded = json.dumps(payload, sort_keys=True)

    assert payload["valid"] is True
    assert payload["point_count"] > 0
    assert isinstance(payload["points"], list)
    assert "surface_score" in payload
    assert "worst_case_pnl" in payload
    assert len(encoded) > 100

    portfolio = service.analyze_portfolio(
        profiles=[profile, profile],
        initial_capital=100000.0,
        allocations=[1.0, 0.5],
        position_metadata=[
            {
                "position_id": "R1",
                "symbol": "REGRESSION",
                "strategy": "BULL_CALL_SPREAD",
                "sector": "TEST",
                "correlation_group": "TEST_GROUP",
            },
            {
                "position_id": "R2",
                "symbol": "REGRESSION2",
                "strategy": "BULL_CALL_SPREAD",
                "sector": "TEST",
                "correlation_group": "TEST_GROUP",
            },
        ],
    )
    portfolio_payload = serialize_value(portfolio)
    json.dumps(portfolio_payload, sort_keys=True)

    assert portfolio_payload["valid"] is True
    assert portfolio_payload["position_count"] == 2
    assert len(portfolio_payload["position_contributions"]) == 2


def validate_report_artifacts() -> None:
    generated = ROOT / "reports" / "phase4_risk_surface_test.html"
    fallback = ROOT / "reports" / "phase4_risk_surface_empty_test.html"

    for path in (generated, fallback):
        assert path.exists(), f"Expected report was not generated: {path}"
        content = path.read_text(encoding="utf-8")
        assert "<html" in content.lower()
        assert "Risk Surface" in content

    generated_text = generated.read_text(encoding="utf-8")
    assert "Heatmap at +0 Days" in generated_text
    assert "Portfolio Risk Surface" in generated_text
    assert "Greek Attribution" in generated_text

    fallback_text = fallback.read_text(encoding="utf-8")
    assert "No valid Phase 4 risk-surface profiles" in fallback_text


def main() -> None:
    missing = [item for item in REQUIRED_TESTS if not (ROOT / item).exists()]
    if missing:
        print("Missing regression test files:")
        for item in missing:
            print(f"  - {item}")
        raise SystemExit(2)

    run([sys.executable, "-m", "compileall", "-q", "src", "scripts"])

    for test_path in REQUIRED_TESTS:
        run([sys.executable, test_path])

    optional_results = {}
    for test_path in OPTIONAL_TESTS:
        if (ROOT / test_path).exists():
            run([sys.executable, test_path])
            optional_results[test_path] = "PASS"
        else:
            print(f"\nSKIP optional legacy test: {test_path}")
            optional_results[test_path] = "SKIPPED (not present)"

    validate_serialization()
    validate_report_artifacts()

    print("\n========== PHASE 4 REGRESSION SUMMARY ==========")
    print("Compilation                 : PASS")
    print(
        "Probability analytics       : "
        + optional_results["scripts/test_probability_engine.py"]
    )
    print(
        "Scenario analytics          : "
        + optional_results["scripts/test_scenario_engine.py"]
    )
    print("Distribution risk           : PASS")
    print("Position risk surfaces      : PASS")
    print("Portfolio risk surfaces     : PASS")
    print("Decision Engine integration : PASS")
    print("Institutional reporting     : PASS")
    print("Serialization               : PASS")
    print("Graceful degradation        : PASS")
    print("Milestone 29 Phase 4        : COMPLETE")


if __name__ == "__main__":
    main()
