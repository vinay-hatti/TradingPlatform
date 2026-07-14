from pathlib import Path

from trading_ai.strategy_engine.probability_calibration_model_registry import ProbabilityCalibrationModelRegistry
from trading_ai.strategy_engine.probability_calibration_runtime_policy import ProbabilityCalibrationRuntimePolicy
from trading_ai.strategy_engine.probability_calibration_runtime_profile import ProbabilityCalibrationRuntimeProfile
from trading_ai.strategy_engine.segmented_probability_calibration_service import SegmentedProbabilityCalibrationService


class ProbabilityCalibrationRuntimeService:
    def __init__(self, *, policy=None, registry=None, registry_path=None, calibration_service=None, profile=None):
        self.policy = (policy or ProbabilityCalibrationRuntimePolicy()).validate()
        self.registry = registry
        if self.registry is None and registry_path:
            self.registry = ProbabilityCalibrationModelRegistry(Path(registry_path))
        self.calibration_service = calibration_service or SegmentedProbabilityCalibrationService(registry=self.registry)
        self.profile = profile

    def active_family(self):
        if self.profile is not None:
            return self.profile, "IN_MEMORY"
        if self.registry is None:
            return None, "UNAVAILABLE"
        entry = self.registry.active()
        if entry is None:
            return None, "UNAVAILABLE"
        return entry.profile, entry.version

    def calibrate(self, raw_probability, *, strategy="", market_regime="", direction="", symbol=""):
        if raw_probability is None:
            return ProbabilityCalibrationRuntimeProfile(
                raw_probability=None, calibrated_probability=None, allowed=not self.policy.require_active_model,
                valid=False, warnings=["RAW_PROBABILITY_UNAVAILABLE"],
                rejection_reasons=["RAW_PROBABILITY_UNAVAILABLE"] if self.policy.require_active_model else [],
            )
        raw = min(max(float(raw_probability), 0.0), 1.0)
        if not self.policy.enabled:
            return ProbabilityCalibrationRuntimeProfile(raw, raw, valid=True, segment_key="IDENTITY",
                warnings=["PROBABILITY_CALIBRATION_DISABLED"], metadata={"identity_fallback": True})
        family, version = self.active_family()
        if family is None:
            allowed = not self.policy.require_active_model
            return ProbabilityCalibrationRuntimeProfile(raw, raw, model_version=version, valid=False, allowed=allowed,
                warnings=["ACTIVE_CALIBRATION_MODEL_UNAVAILABLE"],
                rejection_reasons=[] if allowed else ["ACTIVE_CALIBRATION_MODEL_UNAVAILABLE"],
                metadata={"identity_fallback": True})
        try:
            calibrated, segment_key = self.calibration_service.calibrate(
                family, raw, strategy=strategy, market_regime=market_regime, direction=direction, symbol=symbol,
            )
            selected, _ = self.calibration_service.engine.select_profile(
                family, strategy=strategy, market_regime=market_regime, direction=direction, symbol=symbol,
            )
            score = float(getattr(selected, "calibration_score", 0.0) or 0.0) if selected else 0.0
            grade = str(getattr(selected, "calibration_grade", "N/A") or "N/A") if selected else "N/A"
            severity = str(getattr(selected, "calibration_severity", "UNKNOWN") or "UNKNOWN") if selected else "UNKNOWN"
            method = str(getattr(getattr(selected, "model", None), "method", "IDENTITY") or "IDENTITY") if selected else "IDENTITY"
            model_allowed = bool(getattr(selected, "allowed", True)) if selected else True
            adjustment = float(calibrated) - raw
            warnings=[]; rejections=[]
            if abs(adjustment) > self.policy.maximum_probability_adjustment:
                calibrated = raw + (self.policy.maximum_probability_adjustment if adjustment > 0 else -self.policy.maximum_probability_adjustment)
                adjustment = calibrated - raw
                warnings.append("CALIBRATION_ADJUSTMENT_CAPPED")
            allowed = model_allowed and score >= self.policy.minimum_model_score
            if not allowed and self.policy.reject_unapproved_model:
                rejections.append("CALIBRATION_MODEL_NOT_APPROVED")
            else:
                allowed = True
            return ProbabilityCalibrationRuntimeProfile(
                raw_probability=raw, calibrated_probability=min(max(float(calibrated),0.0),1.0),
                adjustment=adjustment, adjustment_pct=(adjustment/raw if raw else 0.0),
                segment_key=segment_key, model_version=version, model_method=method, model_score=score,
                model_grade=grade, model_severity=severity, confidence_score=score, allowed=allowed, valid=True,
                warnings=warnings, rejection_reasons=rejections, metadata={"registry_id": getattr(family,"registry_id","")},
            )
        except Exception as exc:
            allowed = not self.policy.require_active_model
            return ProbabilityCalibrationRuntimeProfile(raw, raw, model_version=version, valid=False, allowed=allowed,
                warnings=[f"PROBABILITY_CALIBRATION_FAILED: {exc}"],
                rejection_reasons=[] if allowed else ["PROBABILITY_CALIBRATION_FAILED"],
                metadata={"identity_fallback": True, "exception_type": type(exc).__name__})
