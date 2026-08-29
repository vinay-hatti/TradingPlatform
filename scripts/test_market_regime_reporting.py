from pathlib import Path
from types import SimpleNamespace
from trading_ai.backtest.report import BacktestReport

def main():
 p=SimpleNamespace(current_regime="BULL_TREND",forecast_regime="BULL_TREND",portfolio_regime="BULL_TREND",strategy_alignment="ALIGNED",regime_score=80,confidence_score=78,strategy_score_adjustment=5,ranking_score_adjustment=3.75,allowed=True)
 t=SimpleNamespace(symbol="AAPL",strategy="BULL_PUT_SPREAD",market_regime_integration_profile=p,net_pnl=100,entry_date="2026-01-01",exit_date="2026-01-02")
 r=BacktestReport(); html=r.market_regime_summary_html([t]); assert "Market Regime Analytics" in html and "BULL_TREND" in html and "ALIGNED" in html
 print("All Phase 8 market-regime reporting assertions passed.")
if __name__=="__main__": main()
