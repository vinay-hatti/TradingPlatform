from pathlib import Path
from types import SimpleNamespace
import tempfile

from trading_ai.backtest.report import BacktestReport
from trading_ai.strategy_engine.walk_forward_governance_profile import WalkForwardGovernanceProfile


def main():
    governance = WalkForwardGovernanceProfile(
        valid=True, allowed=True, recommendation="PROMOTE_CHALLENGER",
        champion_version="v1", challenger_version="v2",
        champion_score=68.0, challenger_score=76.0, score_improvement=8.0,
        oos_return_improvement=0.04, sharpe_improvement=0.23,
        promotion_eligible=True, confidence_score=88.0,
        governance_grade="A", risk_severity="LOW",
        challenger_profile=SimpleNamespace(parameter_stability_score=78.0),
    )
    trade = SimpleNamespace(symbol="AAPL", net_pnl=100.0, entry_date="2026-01-01", exit_date="2026-01-02", metadata={"walk_forward_governance_profile": governance})
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "report.html"
        BacktestReport().generate([trade], path=path)
        html = path.read_text(encoding="utf-8")
        assert "Walk-Forward Parameter Governance" in html
        assert "PROMOTE_CHALLENGER" in html
        assert "v2" in html
    print("All Phase 7 governance reporting assertions passed.")


if __name__ == "__main__":
    main()
