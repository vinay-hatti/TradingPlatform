from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
import tempfile

REPORT_PATH = Path(__file__).resolve().parents[1] / "src" / "trading_ai" / "backtest" / "report.py"
spec = spec_from_file_location("report", REPORT_PATH)
module = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
BacktestReport = module.BacktestReport


def ns(**kwargs):
    return SimpleNamespace(**kwargs)


def build_trade():
    metric = ns(
        metric_name="implementation_shortfall_bps",
        baseline_mean=4.0,
        current_mean=5.5,
        relative_change=0.375,
        standardized_shift=0.75,
        population_stability_index=0.18,
        drift_score=72.0,
        drift_grade="B",
        drift_severity="MODERATE",
        deteriorated=True,
        allowed=True,
    )
    segment = ns(
        segment_type="VENUE",
        segment_name="CBOE",
        baseline_observation_count=450,
        current_observation_count=220,
        metric_count=7,
        aggregate_psi=0.12,
        maximum_psi=0.21,
        drift_score=78.0,
        drift_grade="B",
        drift_severity="MODERATE",
        allowed=True,
    )
    governance = ns(
        valid=True,
        allowed=True,
        baseline_name="production-baseline-v1",
        current_name="rolling-30d",
        baseline_observation_count=1200,
        current_observation_count=600,
        metric_count=7,
        segment_count=2,
        aggregate_psi=0.14,
        maximum_metric_psi=0.21,
        deteriorated_metric_count=1,
        governance_score=82.5,
        governance_grade="A",
        drift_severity="MODERATE",
        recommendation="MONITOR",
        metric_profiles=(metric,),
        segment_profiles=(segment,),
        warnings=("Shortfall drift requires monitoring",),
        rejection_reasons=(),
    )
    champion = ns(
        version="route-v1", route_type="VENUE", route_name="CBOE",
        status="ACTIVE", observation_count=1000, route_score=88.0,
        average_shortfall_bps=4.5, average_fill_ratio=0.97,
        average_latency_seconds=0.35, average_spread_bps=2.1,
        governance_score=91.0, governance_grade="A", governance_allowed=True,
        active=True, champion=True, challenger=False,
    )
    challenger = ns(
        version="route-v2", route_type="VENUE", route_name="ISE",
        status="CHALLENGER", observation_count=500, route_score=91.0,
        average_shortfall_bps=3.8, average_fill_ratio=0.98,
        average_latency_seconds=0.31, average_spread_bps=1.9,
        governance_score=93.0, governance_grade="A", governance_allowed=True,
        active=False, champion=False, challenger=True,
    )
    registry = ns(
        valid=True, route_count=2, active_version="route-v1",
        champion_version="route-v1", challenger_versions=("route-v2",),
        retired_versions=(), versions=(champion, challenger), audit_event_count=7,
    )
    comparison_metric = ns(
        metric="implementation_shortfall_bps", champion_value=4.5,
        challenger_value=3.8, absolute_change=-0.7, relative_change=-0.1556,
        improvement=0.7, favorable=True, weighted_score=18.5,
        severity="LOW",
    )
    comparison = ns(
        valid=True, allowed=True, champion_version="route-v1",
        challenger_version="route-v2", champion_route_name="CBOE",
        challenger_route_name="ISE", evaluation_score=92.0,
        confidence_score=89.0, evaluation_grade="A",
        governance_severity="LOW", recommendation="PROMOTE_CHALLENGER",
        promoted=False, metric_comparisons=(comparison_metric,),
    )
    integration = ns(
        valid=True, allowed=True, governance_available=True,
        governance_score=82.5, governance_grade="A",
        governance_severity="MODERATE", aggregate_psi=0.14,
        maximum_metric_psi=0.21, deteriorated_metric_count=1,
        governance_recommendation="MONITOR", route_registry_available=True,
        route_count=2, active_route_version="route-v1",
        champion_route_version="route-v1", challenger_route_versions=("route-v2",),
        champion_challenger_available=True, challenger_version="route-v2",
        challenger_evaluation_score=92.0,
        challenger_recommendation="PROMOTE_CHALLENGER",
        route_promotion_recommended=True,
        execution_governance_profile=governance,
        execution_route_registry_profile=registry,
        execution_champion_challenger_profile=comparison,
        warnings=(), rejection_reasons=(),
    )
    return ns(
        symbol="AAPL", strategy="CALL", entry_date="2026-01-01",
        exit_date="2026-01-02", net_pnl=100.0, pnl=100.0,
        execution_governance_integration_profile=integration,
        execution_governance_profile=governance,
        execution_route_registry_profile=registry,
        execution_champion_challenger_profile=comparison,
        metadata={},
    )


def main():
    report = BacktestReport()
    trade = build_trade()

    summary = report.execution_governance_summary_html([trade])
    assert "Execution Governance" in summary
    assert "82.50" in summary
    assert "route-v1" in summary
    assert "Promotion Recommended" in summary

    drift = report.execution_governance_drift_html([trade])
    assert "Population Stability" in drift
    assert "implementation_shortfall_bps" in drift
    assert "CBOE" in drift
    assert "0.1800" in drift

    registry = report.execution_route_registry_html([trade])
    assert "Execution Route Registry" in registry
    assert "route-v2" in registry
    assert "CHALLENGER" in registry

    comparison = report.execution_champion_challenger_html([trade])
    assert "Champion–Challenger Routing Governance" in comparison
    assert "PROMOTE_CHALLENGER" in comparison
    assert "ISE" in comparison

    unavailable = report.execution_governance_summary_html([ns(metadata={})])
    assert "No valid Phase 9 Step 5 execution-governance profile" in unavailable

    with tempfile.TemporaryDirectory() as temp_dir:
        output = Path(temp_dir) / "execution_governance_report.html"
        report.generate([trade], path=output, rejected=[])
        html = output.read_text(encoding="utf-8")
        assert "Execution Governance" in html
        assert "Execution Drift Monitoring &amp; Population Stability" in html
        assert "Execution Route Registry" in html
        assert "Champion–Challenger Routing Governance" in html
        assert "PROMOTE_CHALLENGER" in html

    print("All execution-governance reporting assertions passed.")


if __name__ == "__main__":
    main()
