from pathlib import Path
from types import SimpleNamespace
import tempfile

from trading_ai.backtest.report import BacktestReport
from trading_ai.strategy_engine.portfolio_optimization_frontier_profile import (
    PortfolioOptimizationFrontierPoint,
    PortfolioOptimizationFrontierProfile,
)


def build_frontier_profile():
    points = [
        PortfolioOptimizationFrontierPoint(
            point_id="FRONTIER_001", maximum_exposure_pct=0.20,
            maximum_risk_pct=0.08, maximum_concentration_pct=0.25,
            selected_count=2, allocated_capital=12000.0, exposure_pct=0.12,
            maximum_loss=4200.0, risk_pct=0.042, expected_profit=1800.0,
            expected_return_pct=0.018, objective_score=72.0,
            diversification_score=80.0, concentration_score=55.0,
            greek_utilization_score=40.0, optimization_grade="C",
            risk_severity="LOW", allowed=True, valid=True,
            pareto_efficient=True, allocation_ids=["AAPL", "JPM"],
            allocation_weights={"AAPL": 0.07, "JPM": 0.05},
        ),
        PortfolioOptimizationFrontierPoint(
            point_id="FRONTIER_002", maximum_exposure_pct=0.30,
            maximum_risk_pct=0.12, maximum_concentration_pct=0.30,
            selected_count=3, allocated_capital=20000.0, exposure_pct=0.20,
            maximum_loss=7000.0, risk_pct=0.07, expected_profit=3400.0,
            expected_return_pct=0.034, objective_score=82.5,
            diversification_score=88.0, concentration_score=48.0,
            greek_utilization_score=55.0, optimization_grade="B",
            risk_severity="MODERATE", allowed=True, valid=True,
            pareto_efficient=True, allocation_ids=["AAPL", "JPM", "XOM"],
            allocation_weights={"AAPL": 0.08, "JPM": 0.06, "XOM": 0.06},
        ),
        PortfolioOptimizationFrontierPoint(
            point_id="FRONTIER_003", maximum_exposure_pct=0.40,
            maximum_risk_pct=0.16, maximum_concentration_pct=0.35,
            selected_count=3, allocated_capital=24000.0, exposure_pct=0.24,
            maximum_loss=9600.0, risk_pct=0.096, expected_profit=3600.0,
            expected_return_pct=0.036, objective_score=78.0,
            diversification_score=75.0, concentration_score=65.0,
            greek_utilization_score=72.0, optimization_grade="B",
            risk_severity="MODERATE", allowed=True, valid=True,
            pareto_efficient=False, allocation_ids=["AAPL", "MSFT", "JPM"],
            allocation_weights={"AAPL": 0.10, "MSFT": 0.08, "JPM": 0.06},
        ),
    ]
    return PortfolioOptimizationFrontierProfile(
        initial_capital=100000.0, candidate_count=5, point_count=3,
        valid_point_count=3, pareto_point_count=2, best_point_id="FRONTIER_002",
        best_objective_score=82.5, best_expected_return_pct=0.034,
        lowest_risk_pct=0.042, highest_expected_return_pct=0.036,
        objective_range=10.5, expected_return_range=0.018, risk_range=0.054,
        selection_stability_score=72.0, allocation_stability_score=76.0,
        constraint_sensitivity_score=44.0, frontier_score=78.5,
        frontier_grade="B", risk_severity="MODERATE", allowed=True, valid=True,
        points=points, pareto_points=points[:2],
        warnings=["OPTIMIZATION_RECOMMENDATION_ONLY"],
    )


def main():
    profile = build_frontier_profile()
    trade = SimpleNamespace(
        symbol="AAPL", strategy="BULL_PUT_SPREAD", entry_date="2026-01-01",
        exit_date="2026-01-02", net_pnl=100.0,
        metadata={"portfolio_optimization_frontier_profile": profile},
    )
    report = BacktestReport(initial_capital=100000.0)
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "phase5_frontier_report.html"
        report.generate([trade], path=output)
        html = output.read_text(encoding="utf-8")
        assert "Portfolio Optimization Frontier &amp; Sensitivity" in html
        assert "Pareto-Efficient Points" in html
        assert "Selection Stability" in html
        assert "Constraint Sensitivity" in html
        assert "FRONTIER_002" in html
        assert "82.50" in html
        assert "OPTIMIZATION_RECOMMENDATION_ONLY" in html

        unavailable = Path(directory) / "unavailable.html"
        report.generate([SimpleNamespace(symbol="NONE", net_pnl=0.0)], path=unavailable)
        unavailable_html = unavailable.read_text(encoding="utf-8")
        assert "No valid Phase 5 optimization-frontier profile is attached." in unavailable_html

    print("All Phase 5 optimization-frontier reporting assertions passed.")


if __name__ == "__main__":
    main()
