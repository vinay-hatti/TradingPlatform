from pathlib import Path
from types import SimpleNamespace
from trading_ai.backtest.report import BacktestReport


def main():
    result = SimpleNamespace(
        window_id="WF_001", train_score=70.0, validation_score=68.0,
        test_score=65.0, test_return=0.04, test_sharpe=1.1,
        test_max_drawdown_pct=0.08, degradation_pct=0.05,
        selected_parameters={"threshold": 0.7},
    )
    profile = SimpleNamespace(
        valid=True, allowed=True, window_count=1, completed_window_count=1,
        aggregate_oos_return=0.04, average_oos_sharpe=1.1,
        worst_oos_drawdown_pct=0.08, average_degradation_pct=0.05,
        parameter_stability_score=90.0, window_consistency_score=100.0,
        walk_forward_score=85.0, walk_forward_grade="A",
        risk_severity="LOW", results=[result], raw_profile=None,
    )
    trade = SimpleNamespace(
        symbol="AAPL", entry_date="2026-01-01", exit_date="2026-01-02",
        pnl=100.0, net_pnl=100.0, metadata={"walk_forward_profile": profile},
    )
    path = Path("/tmp/phase7_walk_forward_report.html")
    BacktestReport().generate([trade], path=path)
    html = path.read_text()
    assert "Walk-Forward Validation" in html
    assert "Out-of-Sample Return by Window" in html
    assert "WF_001" in html
    assert "Parameter Stability" in html
    empty = BacktestReport().walk_forward_summary_html([])
    assert "No valid Phase 7 walk-forward profile" in empty
    print("All Phase 7 walk-forward reporting assertions passed.")


if __name__ == "__main__":
    main()
