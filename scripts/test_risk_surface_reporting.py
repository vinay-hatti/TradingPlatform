from pathlib import Path
from types import SimpleNamespace

from trading_ai.backtest.report import BacktestReport
from trading_ai.strategy_engine.risk_surface_service import RiskSurfaceService


def build_trade(symbol, strategy, profile, pnl):
    return SimpleNamespace(
        symbol=symbol, strategy=strategy, signal="CALL", market_regime="TREND_UP",
        entry_date="2026-01-02", exit_date="2026-01-20", strike=100.0,
        expiry="2026-02-20", entry_price=2.0, exit_price=2.5, contracts=1,
        pnl=pnl, net_pnl=pnl, pnl_pct=pnl / 10000.0, gross_pnl=pnl,
        fees=0.0, days_held=18, exit_reason="TEST", rank_score=85.0,
        option_score=82.0, entry_delta=0.25, entry_gamma=0.015,
        entry_theta=-0.04, entry_vega=0.18, entry_volatility=0.30,
        probability_of_profit=0.68, risk_surface_profile=profile,
    )


def main():
    service = RiskSurfaceService()
    profile = service.analyze_strategy(
        symbol="AAPL", strategy="BULL_CALL_SPREAD", underlying_price=200.0,
        implied_volatility=0.30, days_to_expiration=30, capital_required=1000.0,
        initial_capital=100000.0, net_delta=0.30, net_gamma=0.012,
        net_vega=0.20, net_theta=-0.04, net_rho=0.01,
    )
    assert profile.valid and profile.points and profile.attributions
    trade = build_trade("AAPL", "BULL_CALL_SPREAD", profile, 250.0)
    output = Path("reports/phase4_risk_surface_test.html")
    BacktestReport(initial_capital=100000.0).generate([trade], path=output)
    html = output.read_text(encoding="utf-8")
    for expected in [
        "Risk Surfaces &amp; Sensitivity Analytics", "Aggregate Worst-Case P/L",
        "Worst-Point Greek Attribution", "P/L Heatmap", "Surface Approved",
        "Gamma Risk Score", "AAPL", "BULL_CALL_SPREAD",
    ]:
        assert expected in html, expected

    empty_output = Path("reports/phase4_risk_surface_empty_test.html")
    BacktestReport(initial_capital=100000.0).generate([], path=empty_output)
    empty_html = empty_output.read_text(encoding="utf-8")
    assert "No valid Phase 4 risk-surface profiles" in empty_html
    print("All Phase 4 risk-surface reporting assertions passed.")


if __name__ == "__main__":
    main()
