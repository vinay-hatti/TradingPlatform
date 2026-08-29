from types import SimpleNamespace

from trading_ai.strategy_engine.probability_calibration_runtime_policy import ProbabilityCalibrationRuntimePolicy
from trading_ai.strategy_engine.probability_calibration_runtime_service import ProbabilityCalibrationRuntimeService
from trading_ai.strategy_engine.probability_calibration_runtime_serialization import probability_calibration_runtime_to_dict


class FakeEngine:
    calibration_engine = None
    def select_profile(self, family, **context):
        return family.global_profile, "STRATEGY=BULL_PUT_SPREAD|MARKET_REGIME=HIGH_VOL"

class FakeCalibrationService:
    def __init__(self): self.engine = FakeEngine()
    def calibrate(self, family, probability, **context):
        return max(0.0, min(1.0, probability - 0.08)), "STRATEGY=BULL_PUT_SPREAD|MARKET_REGIME=HIGH_VOL"


def main():
    profile = SimpleNamespace(
        global_profile=SimpleNamespace(
            calibration_score=91.0, calibration_grade="A", calibration_severity="LOW", allowed=True,
            model=SimpleNamespace(method="PLATT"),
        ), registry_id="CAL-001",
    )
    service = ProbabilityCalibrationRuntimeService(
        policy=ProbabilityCalibrationRuntimePolicy(maximum_probability_adjustment=0.20),
        calibration_service=FakeCalibrationService(), profile=profile,
    )
    result = service.calibrate(0.72, strategy="BULL_PUT_SPREAD", market_regime="HIGH_VOL", direction="CALL", symbol="AAPL")
    assert result.valid is True
    assert abs(result.raw_probability - 0.72) < 1e-12
    assert abs(result.calibrated_probability - 0.64) < 1e-12
    assert result.segment_key.startswith("STRATEGY=")
    assert result.model_method == "PLATT"
    assert result.model_score == 91.0
    assert result.allowed is True
    payload = probability_calibration_runtime_to_dict(result)
    assert payload["calibrated_probability"] == result.calibrated_probability

    fallback = ProbabilityCalibrationRuntimeService().calibrate(0.55, strategy="IRON_CONDOR")
    assert fallback.calibrated_probability == 0.55
    assert fallback.valid is False
    assert fallback.allowed is True

    strict = ProbabilityCalibrationRuntimeService(
        policy=ProbabilityCalibrationRuntimePolicy(require_active_model=True)
    ).calibrate(0.55)
    assert strict.allowed is False
    assert "ACTIVE_CALIBRATION_MODEL_UNAVAILABLE" in strict.rejection_reasons

    capped_service = ProbabilityCalibrationRuntimeService(
        policy=ProbabilityCalibrationRuntimePolicy(maximum_probability_adjustment=0.05),
        calibration_service=FakeCalibrationService(), profile=profile,
    )
    capped = capped_service.calibrate(0.72, strategy="BULL_PUT_SPREAD")
    assert abs(capped.calibrated_probability - 0.67) < 1e-12
    assert "CALIBRATION_ADJUSTMENT_CAPPED" in capped.warnings
    print("All probability-calibration integration assertions passed.")

if __name__ == "__main__": main()
