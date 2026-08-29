from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from trading_ai.strategy_engine.probability_calibration_model_registry import ProbabilityCalibrationModelRegistry
from trading_ai.strategy_engine.segmented_probability_calibration_service import SegmentedProbabilityCalibrationService
from trading_ai.strategy_engine.segmented_probability_calibration_serialization import segmented_probability_calibration_to_dict


def build_records():
    rng = np.random.default_rng(20260713)
    records = []
    for index in range(2400):
        strategy = "BULL_PUT_SPREAD" if index % 2 == 0 else "BEAR_CALL_SPREAD"
        regime = "HIGH_VOL" if index % 3 == 0 else "NORMAL_VOL"
        direction = "CALL" if strategy == "BULL_PUT_SPREAD" else "PUT"
        latent = rng.uniform(0.05, 0.95)
        if strategy == "BULL_PUT_SPREAD":
            true_probability = 0.10 + 0.75 * latent
            raw_probability = min(0.99, 0.18 + 0.78 * latent)
        else:
            true_probability = 0.05 + 0.82 * latent
            raw_probability = min(0.99, 0.10 + 0.88 * latent)
        if regime == "HIGH_VOL":
            true_probability = max(0.01, true_probability - 0.08)
        outcome = int(rng.random() < true_probability)
        records.append({
            "probability_of_profit": raw_probability,
            "net_pnl": 100.0 if outcome else -150.0,
            "symbol": "AAPL" if index % 5 else "MSFT",
            "strategy": strategy,
            "direction": direction,
            "market_regime": regime,
            "exit_date": f"2026-{1 + (index // 200) % 12:02d}-{1 + index % 27:02d}",
        })
    records.extend([{"strategy": "INVALID"}, {"probability_of_profit": "bad", "net_pnl": 1}])
    return records


def main():
    records = build_records()
    with TemporaryDirectory() as temp:
        registry_path = Path(temp) / "calibration_registry.json"
        registry = ProbabilityCalibrationModelRegistry(registry_path)
        service = SegmentedProbabilityCalibrationService(registry=registry)
        profile = service.train(records, register=True, version="v1", metadata={"purpose": "test"})
        assert profile.valid is True
        assert profile.allowed is True
        assert profile.global_profile is not None
        assert profile.segment_count >= 4
        assert profile.valid_segment_count == profile.segment_count
        assert profile.observation_count == 2400
        assert registry.active().version == "v1"
        assert registry_path.exists()

        calibrated, selected_segment = service.calibrate(
            profile, 0.80, strategy="BULL_PUT_SPREAD",
            market_regime="HIGH_VOL", direction="CALL", symbol="AAPL",
        )
        assert 0.0 <= calibrated <= 1.0
        assert selected_segment != "UNAVAILABLE"
        assert "STRATEGY=BULL_PUT_SPREAD" in selected_segment

        fallback, fallback_segment = service.calibrate(
            profile, 0.50, strategy="UNKNOWN", market_regime="UNKNOWN", direction="UNKNOWN"
        )
        assert 0.0 <= fallback <= 1.0
        assert fallback_segment == "GLOBAL"

        payload = segmented_probability_calibration_to_dict(profile)
        assert payload["registry_id"] == profile.registry_id
        assert isinstance(payload["segment_profiles"], dict)

        restored_registry = ProbabilityCalibrationModelRegistry(registry_path)
        restored = restored_registry.active()
        assert restored is not None
        assert restored.profile.registry_id == profile.registry_id
        restored_value, restored_segment = service.calibrate(
            restored.profile, 0.80, strategy="BULL_PUT_SPREAD",
            market_regime="HIGH_VOL", direction="CALL"
        )
        assert abs(restored_value - calibrated) < 1e-12
        assert restored_segment == selected_segment

        second = registry.register(profile, version="v2", activate=True)
        assert second.version == "v2"
        assert registry.active().version == "v2"
        registry.activate("v1")
        assert registry.active().version == "v1"

    print("All segmented probability-calibration assertions passed.")


if __name__ == "__main__":
    main()
