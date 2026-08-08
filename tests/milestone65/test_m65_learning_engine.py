from trading_ai.performance_learning.outcome_engine import Milestone65LearningService

def test_calibration_metrics_are_governed():
 rows=[{'predicted_probability':.8,'realized_return_pct':5,'outcome':'WIN'},{'predicted_probability':.7,'realized_return_pct':-2,'outcome':'LOSS'}]
 x=Milestone65LearningService.calibration_metrics(rows)
 assert x['sample_size']==2 and x['brier_score']>0 and x['log_loss']>0

def test_empty_calibration_is_safe():
 assert Milestone65LearningService.calibration_metrics([])['sample_size']==0

def test_m65_models_registered():
 from trading_ai.database.base import Base
 import trading_ai.database.models
 for t in ('performance_trade_outcomes','performance_attribution_snapshots','performance_calibration_snapshots','performance_counterfactual_outcomes','performance_learning_publications'):assert t in Base.metadata.tables
