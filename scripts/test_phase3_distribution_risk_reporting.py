from pathlib import Path
from types import SimpleNamespace

from trading_ai.backtest.report import BacktestReport


def build_trade(with_profile=True):
    profile = None
    if with_profile:
        profile = SimpleNamespace(
            valid=True,
            allowed=True,
            observation_count=250,
            historical_var=320.0,
            historical_expected_shortfall=410.0,
            parametric_var=300.0,
            parametric_expected_shortfall=390.0,
            historical_var_99=500.0,
            historical_expected_shortfall_99=625.0,
            downside_deviation=0.025,
            skewness=-0.45,
            excess_kurtosis=2.25,
            probability_of_large_loss=0.04,
            probability_of_severe_loss=0.01,
            probability_of_critical_loss=0.0,
            drawdown_at_risk=0.08,
            expected_drawdown_shortfall=0.10,
            ulcer_index=2.5,
            pain_index=1.2,
            omega_ratio=1.35,
            sortino_ratio=1.20,
            gain_to_pain_ratio=1.10,
            tail_risk_score=84.0,
            tail_risk_grade="B",
            risk_severity="LOW",
        )

    return SimpleNamespace(
        symbol="AAPL",
        entry_date="2026-01-02",
        exit_date="2026-01-10",
        signal="CALL",
        strategy="BULL_CALL_SPREAD",
        market_regime="BULL_TREND",
        entry_price=2.0,
        exit_price=2.5,
        contracts=1,
        net_pnl=50.0,
        pnl=50.0,
        distribution_risk_profile=profile,
    )


def main():
    output = Path("reports/phase3_distribution_risk_report_test.html")
    report = BacktestReport(initial_capital=100000.0)

    report.generate([build_trade(True)], path=output)
    html = output.read_text(encoding="utf-8")

    assert "Distribution Risk &amp; Tail Analytics" in html
    assert "Aggregate Historical VaR 95" in html
    assert "$320.00" in html
    assert "Tail Risk Grade" in html
    assert "Distribution Approved" in html

    fallback_output = Path(
        "reports/phase3_distribution_risk_report_fallback_test.html"
    )
    report.generate([build_trade(False)], path=fallback_output)
    fallback_html = fallback_output.read_text(encoding="utf-8")
    assert "No valid Phase 3 distribution-risk profiles" in fallback_html

    print("Phase 3 reporting assertions passed.")


if __name__ == "__main__":
    main()
