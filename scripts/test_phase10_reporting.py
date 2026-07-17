from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import tempfile

REPORT=Path(__file__).resolve().parents[1]/"src/trading_ai/backtest/report.py"
spec=importlib.util.spec_from_file_location("report",REPORT)
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
BacktestReport=module.BacktestReport

def ns(**kwargs): return SimpleNamespace(**kwargs)

components=(ns(name="adaptive",direction="BULLISH",score=86,confidence_score=82,weight=.4,weighted_score=34.4,available=True,allowed=True),ns(name="learning",direction="BULLISH",score=80,confidence_score=76,weight=.25,weighted_score=20,available=True,allowed=True))
strategy=ns(symbol="AAPL",strategy="BULL_CALL_SPREAD",direction="BULLISH",ensemble_score=84,meta_confidence_score=81,consensus_ratio=1.0,score_dispersion=3.2,component_count=2,allowed_component_count=2,allowed=True,components=components)
ensemble=ns(symbol="AAPL",valid=True,allowed=True,selected_strategy="BULL_CALL_SPREAD",selected_direction="BULLISH",ensemble_score=84,meta_confidence_score=81,consensus_ratio=1.0,grade="A",severity="LOW",strategies=(strategy,),warnings=(),rejection_reasons=())
learning=ns(strategy="BULL_CALL_SPREAD",observation_count=120,effective_sample_size=88,weighted_win_rate=.67,weighted_average_return=.12,profit_factor=1.8,maximum_drawdown_pct=.09,performance_score=82,stability_score=78,confidence_score=80,allowed=True)
weight=ns(strategy="BULL_CALL_SPREAD",prior_weight=.25,performance_component=82,stability_component=78,recency_component=90,raw_weight=.43,normalized_weight=.43,confidence_score=80,allowed=True)
weighting=ns(strategy_count=2,concentration_score=.54,effective_strategy_count=1.85,weights=(weight,))
update=ns(strategy="BULL_CALL_SPREAD",current_weight=.35,target_weight=.48,proposed_weight=.40,applied_weight=.40,absolute_change=.05,update_score=84,grade="A",allowed=True)
adaptation=ns(adaptation_score=84,applied_update_count=1,total_absolute_change=.05,concentration_before=.51,concentration_after=.54,updates=(update,),warnings=(),rejection_reasons=())
version=ns(version="ls-002",status="CHALLENGER",adaptation_score=84,source_version="ls-001",actor="system",reason="online update",created_at="2026-07-14T10:00:00")
registry=ns(active_version="ls-001",champion_version="ls-001",challenger_version="ls-002",versions=(version,))
promotion=ns(recommendation="PROMOTE_CHALLENGER",promotion_score=88,allowed=True,warnings=(),rejection_reasons=())
profile=ns(symbol="AAPL",valid=True,allowed=True,selected_strategy="BULL_CALL_SPREAD",adaptive_score=83,adaptive_confidence_score=80,strategy_weight=.43,grade="A",severity="LOW",recommendation="USE_ENSEMBLE_SELECTION",strategy_learning_profile=learning,dynamic_strategy_weighting_profile=weighting,ensemble_decision_profile=ensemble,online_adaptation_profile=adaptation,learning_state_registry_profile=registry,learning_state_promotion_profile=promotion,warnings=("MONITOR_WEIGHT_CONCENTRATION",),rejection_reasons=())
trade={"symbol":"AAPL","net_pnl":100.0,"entry_date":"2026-07-01","exit_date":"2026-07-02","phase10_decision_integration_profile":profile}
report=BacktestReport()
assert "Adaptive Strategy Selection" in report.phase10_adaptive_selection_html([trade])
assert "BULL_CALL_SPREAD" in report.phase10_ensemble_dashboard_html([trade])
assert "Component Attribution" in report.phase10_ensemble_dashboard_html([trade])
assert "Dynamic Strategy Weights" in report.phase10_learning_weights_html([trade])
assert "ls-002" in report.phase10_online_adaptation_html([trade])
assert "MONITOR_WEIGHT_CONCENTRATION" in report.phase10_governance_messages_html([trade])
assert "No valid Phase 10" in report.phase10_adaptive_selection_html([])
with tempfile.TemporaryDirectory() as d:
    path=Path(d)/"report.html"; report.generate([trade],path=path)
    html=path.read_text()
    for heading in ("Adaptive Strategy Selection","Strategy Learning &amp; Dynamic Weighting","Ensemble Decision Intelligence","Online Adaptation &amp; Learning-State Governance","Phase 10 Governance Diagnostics"):
        assert heading in html, heading
print("All Phase 10 reporting and ensemble-dashboard assertions passed.")
