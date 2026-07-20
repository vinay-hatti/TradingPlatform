from dataclasses import dataclass,field
from datetime import datetime
from typing import Any
@dataclass(frozen=True)
class OutcomeAttributionProfile:
    attribution_id:str; case_id:str; journal_id:str; symbol:str; strategy_name:str; evaluated_at:datetime
    expected_return_pct:float; realized_return_pct:float; expected_volatility_pct:float; realized_volatility_pct:float
    expected_drawdown_pct:float; realized_drawdown_pct:float; holding_period_days:int; exit_reason:str; pnl_amount:float
    outcome_status:str; data_completeness_score:float; forecast_accuracy:dict[str,Any]; scenario_calibration:dict[str,Any]
    thesis_validation:dict[str,Any]; attribution_factors:tuple[dict[str,Any],...]; research_feedback:dict[str,Any]
    decision_quality_score:float; decision_quality_grade:str; positive_factors:tuple[str,...]=(); warnings:tuple[str,...]=();
    rejection_reasons:tuple[str,...]=(); remediation_actions:tuple[str,...]=(); metadata:dict[str,Any]=field(default_factory=dict)
