from trading_ai.strategy_engine.probability_calibration_ranking_policy import ProbabilityCalibrationRankingPolicy
from trading_ai.strategy_engine.probability_calibration_ranking_profile import ProbabilityCalibrationRankingProfile


class ProbabilityCalibrationRankingService:
    def __init__(self, policy=None):
        self.policy = (policy or ProbabilityCalibrationRankingPolicy()).validate()

    @staticmethod
    def _bounded(value, low, high):
        return max(low, min(high, float(value)))

    def evaluate(self, raw_ranking_score, calibration_profile=None):
        raw_score = self._bounded(raw_ranking_score or 0.0, 0.0, 100.0)
        policy = self.policy
        if not policy.enabled or calibration_profile is None or not getattr(calibration_profile, "valid", False):
            return ProbabilityCalibrationRankingProfile(
                raw_ranking_score=raw_score, adjusted_ranking_score=raw_score,
                warnings=[] if policy.enabled else ["CALIBRATION_RANKING_DISABLED"],
                metadata={"fallback": "RAW_RANKING"},
            )

        raw_probability = getattr(calibration_profile, "raw_probability", None)
        calibrated_probability = getattr(calibration_profile, "calibrated_probability", None)
        model_score = float(getattr(calibration_profile, "model_score", 0.0) or 0.0)
        confidence = float(getattr(calibration_profile, "confidence_score", model_score) or 0.0)
        probability_adjustment = 0.0
        if raw_probability is not None and calibrated_probability is not None:
            probability_adjustment = float(calibrated_probability) - float(raw_probability)

        raw_adjustment = probability_adjustment * 100.0 * policy.calibration_weight
        adjustment = self._bounded(
            raw_adjustment, -policy.maximum_ranking_adjustment, policy.maximum_ranking_adjustment
        )
        warnings = list(getattr(calibration_profile, "warnings", []) or [])
        rejections = []
        severity = str(getattr(calibration_profile, "model_severity", "UNKNOWN") or "UNKNOWN").upper()
        calibration_allowed = bool(getattr(calibration_profile, "allowed", True))
        allowed = True
        if model_score < policy.minimum_model_score:
            warnings.append("CALIBRATION_MODEL_SCORE_BELOW_RANKING_THRESHOLD")
            adjustment = 0.0
        if policy.reject_unapproved_calibration and not calibration_allowed:
            rejections.append("CALIBRATION_MODEL_NOT_APPROVED_FOR_RANKING")
            allowed = False
        if policy.reject_critical_calibration and severity == "CRITICAL":
            rejections.append("CRITICAL_CALIBRATION_RISK")
            allowed = False

        adjusted = self._bounded(raw_score + adjustment, 0.0, 100.0)
        return ProbabilityCalibrationRankingProfile(
            raw_ranking_score=raw_score, adjusted_ranking_score=adjusted,
            ranking_adjustment=adjusted-raw_score, raw_probability=raw_probability,
            calibrated_probability=calibrated_probability, probability_adjustment=probability_adjustment,
            calibration_weight=policy.calibration_weight, model_score=model_score,
            confidence_score=confidence, segment_key=str(getattr(calibration_profile, "segment_key", "UNAVAILABLE")),
            model_version=str(getattr(calibration_profile, "model_version", "UNAVAILABLE")),
            method=str(getattr(calibration_profile, "model_method", "IDENTITY")),
            grade=str(getattr(calibration_profile, "model_grade", "N/A")), severity=severity,
            allowed=allowed, valid=True, warnings=list(dict.fromkeys(warnings)),
            rejection_reasons=list(dict.fromkeys(rejections)),
            metadata={"uncapped_ranking_adjustment": raw_adjustment, "calibration_allowed": calibration_allowed},
        )
