from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from trading_ai.backtest.report import BacktestReport


def main():
    drift = SimpleNamespace(regime_population_stability_index=0.08, drift_score=88.0, drift_grade="A", drift_severity="LOW")
    governance = SimpleNamespace(valid=True, champion_version="v1", challenger_version="v2", recommendation="PROMOTE_CHALLENGER", accuracy_improvement=0.04, forecast_accuracy_improvement=0.03, transition_f1_improvement=0.03, critical_false_positive_deterioration=0.001, promotion_eligible=True, promotion_applied=False, confidence_score=87.0, governance_grade="A", risk_severity="LOW", drift_profile=drift, warnings=[], rejection_reasons=[])
    trade = {"symbol": "AAPL", "net_pnl": 100.0, "entry_date": "2026-01-01", "exit_date": "2026-01-02", "metadata": {"market_regime_governance_profile": governance}}
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "report.html"
        BacktestReport().generate([trade], path=path)
        html = path.read_text(encoding="utf-8")
        assert "Market Regime Model Governance &amp; Drift" in html
        assert "Walk-Forward Parameter Governance" in html
        assert "PROMOTE_CHALLENGER" in html
    print("All Phase 8 governance reporting assertions passed.")


if __name__ == "__main__":
    main()
