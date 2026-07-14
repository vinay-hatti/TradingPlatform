from pathlib import Path
from types import SimpleNamespace
from trading_ai.backtest.report import BacktestReport


def main():
    profile=SimpleNamespace(valid=True,raw_probability=0.62,calibrated_probability=0.57,adjustment=-0.05,segment_key="STRATEGY=BULL_PUT_SPREAD",model_version="v3",model_method="PLATT",model_score=88.0,model_grade="A",model_severity="LOW",allowed=True,metadata={})
    trade=SimpleNamespace(symbol="AAPL",strategy="BULL_PUT_SPREAD",entry_date="2026-01-01",exit_date="2026-01-15",net_pnl=125.0,probability_calibration_profile=profile,raw_probability_of_profit=0.62,calibrated_probability_of_profit=0.57,probability_calibration_adjustment=-0.05,probability_calibration_segment=profile.segment_key,probability_calibration_model_version="v3",probability_calibration_method="PLATT",probability_calibration_score=88.0,probability_calibration_grade="A",probability_calibration_severity="LOW",probability_calibration_allowed=True,calibration_ranking_adjustment=-1.25,calibration_adjusted_ranking_score=76.5,metadata={"probability_calibration_profile":profile})
    path=Path("reports/test_probability_calibration_report.html")
    BacktestReport().generate([trade],path=path)
    html=path.read_text()
    for token in ["Probability Calibration","Raw POP","Calibrated POP","STRATEGY=BULL_PUT_SPREAD","Ranking Δ"]: assert token in html
    unavailable=BacktestReport().probability_calibration_summary_html([SimpleNamespace(metadata={})])
    assert "No valid Phase 6 probability-calibration profiles" in unavailable
    print("All Phase 6 probability-calibration reporting assertions passed.")

if __name__=="__main__": main()
