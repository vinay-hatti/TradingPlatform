from pathlib import Path
from types import SimpleNamespace
import tempfile

from trading_ai.backtest.report import BacktestReport
from trading_ai.strategy_engine.portfolio_optimization_profile import (
    PortfolioOptimizationAllocation, PortfolioOptimizationProfile,
)


def build_profile():
    allocations = [
        PortfolioOptimizationAllocation(
            candidate_id="AAPL-1", symbol="AAPL", strategy="BULL_PUT_SPREAD",
            allocation_dollars=5000.0, allocation_weight_pct=0.05, allocation_multiplier=1.0,
            expected_profit=850.0, maximum_loss=1500.0, expected_return_pct=0.17,
            marginal_objective_score=84.0, ranking_score=91.0, surface_score=86.0,
            sector="TECHNOLOGY", correlation_group="MEGA_CAP_TECH",
        ),
        PortfolioOptimizationAllocation(
            candidate_id="JPM-1", symbol="JPM", strategy="BEAR_CALL_SPREAD",
            allocation_dollars=4000.0, allocation_weight_pct=0.04, allocation_multiplier=1.0,
            expected_profit=600.0, maximum_loss=1200.0, expected_return_pct=0.15,
            marginal_objective_score=79.0, ranking_score=87.0, surface_score=82.0,
            sector="FINANCIALS", correlation_group="BANKS",
        ),
    ]
    return PortfolioOptimizationProfile(
        initial_capital=100000.0, candidate_count=3, selected_count=2,
        total_allocated_capital=9000.0, portfolio_exposure_pct=0.09,
        reserve_cash=91000.0, reserve_cash_pct=0.91, total_maximum_loss=2700.0,
        total_risk_pct=0.027, expected_portfolio_profit=1450.0,
        expected_portfolio_return_pct=0.161111, weighted_ranking_score=89.22,
        weighted_strategy_score=87.0, weighted_surface_score=84.22,
        diversification_score=78.0, capital_efficiency_score=81.0,
        concentration_score=74.0, greek_utilization_score=88.0, objective_score=83.5,
        optimization_grade="B", risk_severity="LOW", allowed=True, valid=True,
        allocations=allocations, rejected_candidates=[{"symbol":"MSFT","reason":"SECTOR_LIMIT"}],
        sector_weights=[{"name":"TECHNOLOGY","weight_pct":0.05,"allocation_dollars":5000.0},{"name":"FINANCIALS","weight_pct":0.04,"allocation_dollars":4000.0}],
        strategy_weights=[{"name":"BULL_PUT_SPREAD","weight_pct":0.05,"allocation_dollars":5000.0},{"name":"BEAR_CALL_SPREAD","weight_pct":0.04,"allocation_dollars":4000.0}],
        correlation_group_weights=[{"name":"MEGA_CAP_TECH","weight_pct":0.05,"allocation_dollars":5000.0},{"name":"BANKS","weight_pct":0.04,"allocation_dollars":4000.0}],
        greek_totals={"delta": 0.12, "gamma": 0.03, "theta": 0.08, "vega": -0.22},
        binding_constraints=["MAXIMUM_POSITION_WEIGHT"], warnings=["OPTIMIZATION_RECOMMENDATION_ONLY"],
    )


def build_trade(symbol, strategy, profile, selected, optimized):
    return SimpleNamespace(
        symbol=symbol, strategy=strategy, entry_date="2026-01-01", exit_date="2026-01-02",
        net_pnl=100.0, selected=selected, optimization_selected=optimized,
        optimization_status="SELECTED" if optimized else "REJECTED",
        optimized_allocation_dollars=5000.0 if optimized else 0.0,
        optimized_allocation_weight_pct=0.05 if optimized else 0.0,
        optimized_expected_profit=850.0 if optimized else 0.0,
        optimized_maximum_loss=1500.0 if optimized else 0.0,
        optimization_marginal_score=84.0 if optimized else 0.0,
        metadata={"portfolio_optimization_profile": profile},
    )


def main():
    profile = build_profile()
    trades = [
        build_trade("AAPL", "BULL_PUT_SPREAD", profile, True, True),
        build_trade("JPM", "BEAR_CALL_SPREAD", profile, False, True),
        build_trade("MSFT", "BULL_CALL_SPREAD", profile, True, False),
    ]
    report = BacktestReport(initial_capital=100000.0)
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "phase5_report.html"
        report.generate(trades, path=output)
        html = output.read_text(encoding="utf-8")
        assert "Portfolio Risk Optimization" in html
        assert "Optimized Allocations" in html
        assert "Legacy vs Optimized Portfolio Selection" in html
        assert "MAXIMUM_POSITION_WEIGHT" in html
        assert "$9,000.00" in html
        assert "AAPL" in html and "JPM" in html
        assert "MEGA_CAP_TECH" in html

        unavailable = Path(directory) / "unavailable.html"
        report.generate([SimpleNamespace(symbol="NONE", net_pnl=0.0)], path=unavailable)
        unavailable_html = unavailable.read_text(encoding="utf-8")
        assert "No valid Phase 5 portfolio-optimization profile is attached." in unavailable_html

    print("All Phase 5 portfolio-optimization reporting assertions passed.")


if __name__ == "__main__":
    main()
