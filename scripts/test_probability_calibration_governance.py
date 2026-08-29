import json, tempfile
import numpy as np
from pathlib import Path
from trading_ai.strategy_engine.probability_calibration_engine import ProbabilityCalibrationEngine
from trading_ai.strategy_engine.probability_calibration_policy import ProbabilityCalibrationPolicy
from trading_ai.strategy_engine.probability_calibration_drift_service import ProbabilityCalibrationDriftService
from trading_ai.strategy_engine.probability_calibration_governance_service import ProbabilityCalibrationGovernanceService
from trading_ai.strategy_engine.probability_calibration_governance_policy import ProbabilityCalibrationGovernancePolicy
from trading_ai.strategy_engine.probability_calibration_governance_serialization import probability_calibration_governance_to_dict

rng=np.random.default_rng(42)
latent=rng.uniform(.05,.95,3000); outcomes=rng.binomial(1,latent)
champion_raw=np.clip(.5+(latent-.5)*1.65,.01,.99)
challenger_raw=np.clip(.5+(latent-.5)*1.20,.01,.99)
policy=ProbabilityCalibrationPolicy(minimum_observations=200,minimum_positive_observations=50,minimum_negative_observations=50)
engine=ProbabilityCalibrationEngine(policy)
champion=engine.analyze(champion_raw[:2000],outcomes[:2000],segment='GLOBAL')
challenger=engine.analyze(challenger_raw[:2000],outcomes[:2000],segment='GLOBAL')
recent_p=challenger_raw[2000:]; recent_y=outcomes[2000:]
drift=ProbabilityCalibrationDriftService().analyze(challenger_raw[:1000],outcomes[:1000],recent_p,recent_y,model_version='v2')
gov=ProbabilityCalibrationGovernanceService(policy=ProbabilityCalibrationGovernancePolicy(minimum_evaluation_observations=500,minimum_brier_improvement=-1.0,minimum_log_loss_improvement=-1.0)).evaluate(champion,challenger,recent_p,recent_y,champion_version='v1',challenger_version='v2',drift_profile=drift)
assert drift.valid and 0<=drift.drift_score<=100
assert gov.valid and gov.recommendation in {'PROMOTE_CHALLENGER','RETAIN_CHAMPION'}
assert gov.champion_version=='v1' and gov.challenger_version=='v2'
json.dumps(probability_calibration_governance_to_dict(gov))
print('All probability-calibration governance assertions passed.')
