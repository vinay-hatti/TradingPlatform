from pathlib import Path
from types import SimpleNamespace
from trading_ai.backtest.report import BacktestReport

drift=SimpleNamespace(drift_score=88.2,drift_grade='A',drift_severity='LOW',probability_psi=.04,brier_change=.002,ece_change=.003)
gov=SimpleNamespace(champion_version='v1',challenger_version='v2',recommendation='PROMOTE_CHALLENGER',promotion_eligible=True,confidence_score=91.0,brier_improvement=.012)
trade={'symbol':'AAPL','entry_date':'2026-01-01','exit_date':'2026-01-02','net_pnl':100.0,'metadata':{'probability_calibration_drift_profile':drift,'probability_calibration_governance_profile':gov}}
out=Path('/tmp/phase6_governance_report.html'); BacktestReport().generate([trade],path=out)
html=out.read_text(encoding='utf-8')
for token in ['Calibration Governance &amp; Drift','PROMOTE_CHALLENGER','Probability PSI','Governance Confidence']: assert token in html, token
print('All Phase 6 governance reporting assertions passed.')
