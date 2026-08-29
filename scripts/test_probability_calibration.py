import json

import numpy as np

from trading_ai.strategy_engine.probability_calibration_policy import (
    ProbabilityCalibrationPolicy,
)
from trading_ai.strategy_engine.probability_calibration_serialization import (
    probability_calibration_to_dict,
)
from trading_ai.strategy_engine.probability_calibration_service import (
    ProbabilityCalibrationService,
)


def main():
    rng = np.random.default_rng(42)
    observation_count = 4000

    latent = rng.normal(0.0, 1.0, observation_count)
    true_probability = 1.0 / (1.0 + np.exp(-latent))
    outcomes = rng.binomial(1, true_probability)

    # Deliberately over-confident model probabilities.
    raw_probability = 1.0 / (1.0 + np.exp(-2.25 * latent - 0.35))

    policy = ProbabilityCalibrationPolicy(
        preferred_method="AUTO",
        minimum_observations=200,
        minimum_positive_observations=50,
        minimum_negative_observations=50,
        reliability_bin_count=12,
    )
    service = ProbabilityCalibrationService(policy=policy)
    profile = service.analyze(
        predicted_probabilities=raw_probability,
        outcomes=outcomes,
        symbol="PORTFOLIO",
        strategy="ALL",
        segment="OUT_OF_SAMPLE_BACKTEST",
        timestamps=np.arange(observation_count),
    )

    print("\n========== PROBABILITY CALIBRATION ==========")
    print(f"Model ID              : {profile.model_id}")
    print(f"Method                : {profile.selected_method}")
    print(f"Observations          : {profile.observation_count}")
    print(f"Raw Brier             : {profile.raw_brier_score:.6f}")
    print(f"Calibrated Brier      : {profile.calibrated_brier_score:.6f}")
    print(f"Brier Improvement     : {profile.brier_improvement:.2%}")
    print(f"Raw Log Loss          : {profile.raw_log_loss:.6f}")
    print(f"Calibrated Log Loss   : {profile.calibrated_log_loss:.6f}")
    print(f"Raw ECE               : {profile.raw_ece:.6f}")
    print(f"Calibrated ECE        : {profile.calibrated_ece:.6f}")
    print(f"Calibration Score     : {profile.calibration_score:.2f}")
    print(f"Grade                 : {profile.calibration_grade}")
    print(f"Severity              : {profile.calibration_severity}")
    print(f"Allowed               : {profile.allowed}")

    assert profile.valid is True
    assert profile.allowed is True
    assert profile.selected_method in {"PLATT", "ISOTONIC"}
    assert profile.observation_count == observation_count
    assert profile.validation_count >= policy.minimum_validation_observations
    assert profile.calibrated_brier_score < profile.raw_brier_score
    assert profile.calibrated_log_loss < profile.raw_log_loss
    assert profile.calibrated_ece < profile.raw_ece
    assert 0.0 <= profile.calibration_score <= 100.0
    assert profile.model.fitted is True
    assert len(profile.calibrated_reliability_bins) >= 3

    calibrated = service.calibrate_many(profile, [0.05, 0.25, 0.50, 0.75, 0.95])
    assert np.all(calibrated > 0.0)
    assert np.all(calibrated < 1.0)
    assert np.all(np.diff(calibrated) >= -1e-12)

    payload = probability_calibration_to_dict(profile)
    serialized = json.dumps(payload, sort_keys=True)
    assert 'selected_method' in serialized
    assert 'calibrated_reliability_bins' in serialized
    assert payload['model']['method'] == profile.selected_method

    invalid = service.analyze(
        predicted_probabilities=[0.4, 0.6, 0.7, 0.3],
        outcomes=[0, 1, 1, 0],
        symbol="SMALL",
        strategy="TEST",
    )
    assert invalid.valid is False
    assert invalid.allowed is False
    assert "INSUFFICIENT_CALIBRATION_OBSERVATIONS" in invalid.rejection_reasons

    identity_service = ProbabilityCalibrationService(
        policy=ProbabilityCalibrationPolicy(
            preferred_method="IDENTITY",
            minimum_observations=200,
            minimum_positive_observations=50,
            minimum_negative_observations=50,
        )
    )
    identity = identity_service.analyze(raw_probability, outcomes)
    assert identity.selected_method == "IDENTITY"
    assert abs(identity_service.calibrate(identity, 0.61) - 0.61) < 1e-9

    print("\nAll probability-calibration assertions passed.")


if __name__ == "__main__":
    main()
