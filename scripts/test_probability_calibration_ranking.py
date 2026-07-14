from types import SimpleNamespace
from trading_ai.strategy_engine.probability_calibration_ranking_policy import ProbabilityCalibrationRankingPolicy
from trading_ai.strategy_engine.probability_calibration_ranking_service import ProbabilityCalibrationRankingService
from trading_ai.strategy_engine.probability_calibration_ranking_serialization import probability_calibration_ranking_to_dict


def main():
    service=ProbabilityCalibrationRankingService(ProbabilityCalibrationRankingPolicy(calibration_weight=0.5,maximum_ranking_adjustment=8.0))
    positive=SimpleNamespace(valid=True,raw_probability=0.55,calibrated_probability=0.70,model_score=90.0,confidence_score=88.0,segment_key="STRATEGY=BULL_PUT_SPREAD",model_version="v1",model_method="PLATT",model_grade="A",model_severity="LOW",allowed=True,warnings=[])
    p=service.evaluate(70.0,positive)
    assert p.valid and p.adjusted_ranking_score>70.0 and p.ranking_adjustment<=8.0
    negative=SimpleNamespace(**{**positive.__dict__,"calibrated_probability":0.35})
    n=service.evaluate(70.0,negative)
    assert n.adjusted_ranking_score<70.0 and n.ranking_adjustment>=-8.0
    fallback=service.evaluate(70.0,None)
    assert fallback.adjusted_ranking_score==70.0 and not fallback.valid
    data=probability_calibration_ranking_to_dict(p)
    assert data["segment_key"].startswith("STRATEGY")
    print("All probability-calibration ranking assertions passed.")

if __name__=="__main__": main()
