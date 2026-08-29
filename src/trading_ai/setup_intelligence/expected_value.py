from __future__ import annotations

from .contracts import ConditionalProbability, ExpectedValueAssessment


class SetupExpectedValueEngine:
    version = "M78-SETUP-EV-1.0"

    def assess(self, setup, probability: ConditionalProbability, *, risk_pct: float | None = None) -> ExpectedValueAssessment:
        if probability.status != "READY" or probability.target_1_probability is None:
            return ExpectedValueAssessment("INSUFFICIENT_EVIDENCE", str(setup.setup_type), None, None, None, None, None,
                                           {"reason": "setup probability is not ready"})
        reward = abs(float(probability.expected_mfe_pct or probability.expected_return_pct or 0.0))
        risk = abs(float(risk_pct or probability.expected_mae_pct or 0.0))
        if risk <= 0:
            return ExpectedValueAssessment("INSUFFICIENT_RISK_GEOMETRY", str(setup.setup_type), None,
                                           probability.expected_return_pct, None, None, None,
                                           {"reason": "no non-zero empirical/structural risk estimate"})
        p = float(probability.target_1_probability)
        expected_r = (p * (reward / risk)) - ((1.0 - p) * 1.0)
        expected_return = probability.expected_return_pct
        capital_eff = (float(expected_return) / risk) if expected_return is not None else expected_r
        hold = max(float(probability.expected_holding_days or 1.0), 1.0)
        time_eff = capital_eff / hold
        quality = float(getattr(setup, "quality", 0.0)) / 100.0
        confidence = float(probability.confidence) / 100.0
        utility = expected_r * quality * confidence
        return ExpectedValueAssessment("READY", str(setup.setup_type), round(expected_r, 8),
                                       round(float(expected_return), 8) if expected_return is not None else None,
                                       round(capital_eff, 8), round(time_eff, 8), round(utility, 8),
                                       {"reward_pct": reward, "risk_pct": risk, "target_1_probability": p,
                                        "quality": quality, "probability_confidence": confidence})
