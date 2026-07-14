from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np

from trading_ai.strategy_engine.probability_calibration_model_registry import ProbabilityCalibrationModelRegistry
from trading_ai.strategy_engine.walk_forward_policy import WalkForwardPolicy
from trading_ai.strategy_engine.walk_forward_probability_calibration_policy import WalkForwardProbabilityCalibrationPolicy
from trading_ai.strategy_engine.walk_forward_probability_calibration_serialization import walk_forward_probability_calibration_to_dict
from trading_ai.strategy_engine.walk_forward_probability_calibration_service import WalkForwardProbabilityCalibrationService


def build_records(count: int = 1200):
    rng = np.random.default_rng(20260713)
    records = []
    for index in range(count):
        latent = rng.beta(2.2, 2.4)
        raw = min(0.98, max(0.02, 0.12 + 0.72 * latent))
        # Deliberately under-confident / biased model suitable for calibration.
        true_probability = min(0.98, max(0.02, 0.03 + 1.08 * raw))
        outcome = int(rng.random() < true_probability)
        strategy = "BULL_PUT_SPREAD" if index % 2 == 0 else "BEAR_CALL_SPREAD"
        regime = "HIGH_VOL" if index % 3 == 0 else "NORMAL_VOL"
        records.append({
            "probability_of_profit": raw,
            "outcome": outcome,
            "timestamp": index,
            "symbol": "AAPL" if index % 4 else "MSFT",
            "strategy": strategy,
            "direction": "CALL" if strategy == "BULL_PUT_SPREAD" else "PUT",
            "market_regime": regime,
        })
    return records


def main():
    records = build_records()
    wf_policy = WalkForwardPolicy(
        train_size=450,
        validation_size=150,
        test_size=150,
        step_size=150,
        purge_size=0,
        embargo_size=0,
        minimum_windows=3,
        minimum_train_observations=300,
        minimum_validation_observations=100,
        minimum_test_observations=100,
    )
    calibration_policy = WalkForwardProbabilityCalibrationPolicy(
        minimum_train_observations=300,
        minimum_validation_observations=100,
        minimum_test_observations=100,
        minimum_completed_windows=3,
        minimum_oos_brier_improvement=-0.05,
        minimum_oos_log_loss_improvement=-0.05,
        maximum_oos_ece=0.20,
        maximum_oos_mce=0.40,
        minimum_segment_coverage=0.40,
        register_window_models=True,
        activate_latest_model=True,
    )
    grid = [
        {
            "preferred_method": "PLATT",
            "minimum_observations": 100,
            "minimum_positive_observations": 25,
            "minimum_negative_observations": 25,
            "minimum_segment_observations": 100,
            "minimum_segment_positive_observations": 25,
            "minimum_segment_negative_observations": 25,
            "maximum_segment_depth": 2,
        },
        {
            "preferred_method": "ISOTONIC",
            "minimum_observations": 100,
            "minimum_positive_observations": 25,
            "minimum_negative_observations": 25,
            "minimum_segment_observations": 100,
            "minimum_segment_positive_observations": 25,
            "minimum_segment_negative_observations": 25,
            "maximum_segment_depth": 1,
        },
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        registry_path = Path(temp_dir) / "calibration_registry.json"
        registry = ProbabilityCalibrationModelRegistry(registry_path)
        service = WalkForwardProbabilityCalibrationService(
            walk_forward_policy=wf_policy,
            calibration_walk_forward_policy=calibration_policy,
            registry=registry,
        )
        profile = service.run(records, grid, version_prefix="test-wf")

        print(f"Windows                 : {profile.window_count}")
        print(f"Completed               : {profile.completed_window_count}")
        print(f"Average Brier Improve   : {profile.average_oos_brier_improvement:.2%}")
        print(f"Average LogLoss Improve : {profile.average_oos_log_loss_improvement:.2%}")
        print(f"Average OOS ECE         : {profile.average_oos_ece:.4f}")
        print(f"Segment Coverage        : {profile.average_segment_coverage:.2%}")
        print(f"Model Stability         : {profile.model_stability_score:.2f}")
        print(f"Calibration WF Score    : {profile.calibration_walk_forward_score:.2f}")
        print(f"Calibration WF Grade    : {profile.calibration_walk_forward_grade}")
        print(f"Active Model Version    : {profile.active_model_version}")

        assert profile.valid is True
        assert profile.completed_window_count >= 3
        assert len(profile.results) == profile.completed_window_count
        assert 0.0 <= profile.average_oos_ece <= 1.0
        assert 0.0 <= profile.average_segment_coverage <= 1.0
        assert 0.0 <= profile.model_stability_score <= 100.0
        assert 0.0 <= profile.calibration_walk_forward_score <= 100.0
        assert profile.calibration_walk_forward_grade in {"A", "B", "C", "D", "F"}
        assert profile.active_model_version != "UNAVAILABLE"
        assert registry.active() is not None
        assert len(registry.list_versions()) == profile.completed_window_count
        for result in profile.results:
            assert result.validation_metrics.valid
            assert result.test_metrics.valid
            assert result.test_metrics.observation_count >= 100
            assert result.model_registry_id != "UNAVAILABLE"
            assert result.model_version != "UNAVAILABLE"
            assert result.model_segment_count >= result.model_valid_segment_count

        payload = walk_forward_probability_calibration_to_dict(profile)
        encoded = json.dumps(payload)
        assert "average_oos_brier_improvement" in encoded
        assert "selected_parameters" in encoded
        assert "test_metrics" in encoded

    print("All walk-forward probability-calibration assertions passed.")


if __name__ == "__main__":
    main()
