from __future__ import annotations

from dataclasses import asdict, is_dataclass
from math import exp, log
from statistics import median
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.preprocessing import StandardScaler

from .contracts import OutcomeProbabilityAssessment
from .features import NUMERIC_FEATURES, PointInTimeFeatureBuilder
from .policy import OutcomeProbabilityPolicy


TARGET_COLUMNS = (
    "target_1_before_stop",
    "target_2_before_stop",
    "target_3_before_stop",
    "profitable_at_horizon",
    "thesis_invalidation",
)
REGRESSION_COLUMNS = (
    "maximum_favorable_excursion_pct",
    "maximum_adverse_excursion_pct",
    "days_to_target_1",
    "days_to_stop",
)


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = exp(-value)
        return 1.0 / (1.0 + z)
    z = exp(value)
    return z / (1.0 + z)


def _logit(value: float) -> float:
    p = min(0.999999, max(0.000001, float(value)))
    return log(p / (1.0 - p))


def _ece(probabilities: np.ndarray, labels: np.ndarray, bins: int = 10) -> float:
    result = 0.0
    for lower in np.linspace(0.0, 0.9, bins):
        upper = lower + 0.1
        mask = (probabilities >= lower) & ((probabilities < upper) | ((upper >= 1.0) & (probabilities <= upper)))
        if mask.any():
            result += float(mask.mean()) * abs(float(probabilities[mask].mean()) - float(labels[mask].mean()))
    return float(result)


def _as_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if is_dataclass(value):
        return asdict(value)
    return dict(vars(value))


class GovernedOutcomeModelTrainer:
    """Chronological train/calibration/test trainer with JSON-only artifacts."""

    version = "M77.0-WALK-FORWARD-META-LABEL-1.0"

    def __init__(self, policy: OutcomeProbabilityPolicy | None = None):
        self.policy = policy or OutcomeProbabilityPolicy()
        self.policy.validate()

    def readiness(self, observations: list[Any]) -> dict[str, Any]:
        observations = self.eligible_observations(observations)
        dates = sorted({str(row.as_of)[:10] for row in observations})
        counts = {}
        for target in TARGET_COLUMNS:
            values = [getattr(row, target) for row in observations if getattr(row, target) is not None]
            counts[target] = {
                "samples": len(values),
                "positive": sum(int(value) for value in values),
                "negative": len(values) - sum(int(value) for value in values),
            }
        primary = counts["target_1_before_stop"]
        ready = (
            primary["samples"] >= self.policy.minimum_training_samples
            and primary["positive"] >= self.policy.minimum_positive_samples
            and primary["negative"] >= self.policy.minimum_negative_samples
            and len(dates) >= self.policy.minimum_distinct_as_of_dates
        )
        return {
            "status": "READY" if ready else "INSUFFICIENT_EVIDENCE",
            "observation_count": len(observations),
            "distinct_as_of_dates": len(dates),
            "targets": counts,
            "requirements": {
                "minimum_training_samples": self.policy.minimum_training_samples,
                "minimum_positive_samples": self.policy.minimum_positive_samples,
                "minimum_negative_samples": self.policy.minimum_negative_samples,
                "minimum_distinct_as_of_dates": self.policy.minimum_distinct_as_of_dates,
            },
        }

    def train(self, observations: list[Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        observations = self.eligible_observations(observations)
        readiness = self.readiness(observations)
        if readiness["status"] != "READY":
            raise ValueError(f"M77 training evidence is not ready: {readiness}")
        ordered = sorted(observations, key=lambda row: (str(row.as_of), str(row.observation_id)))
        dates = sorted({str(row.as_of)[:10] for row in ordered})
        train_end = dates[max(0, int(len(dates) * 0.50) - 1)]
        calibration_end = dates[max(1, int(len(dates) * 0.75) - 1)]
        calibration_start = dates[int(len(dates) * 0.50)]
        test_start = dates[int(len(dates) * 0.75)]
        X = np.asarray(
            [[float((row.features_json or {}).get(name, 0.0)) for name in NUMERIC_FEATURES] for row in ordered],
            dtype=float,
        )
        as_of_dates = np.asarray([str(row.as_of)[:10] for row in ordered])
        horizon_dates = np.asarray([str(row.horizon_end or "")[:10] for row in ordered])
        # Purge labels whose forward horizon overlaps the next partition. This
        # prevents a training label from containing price action observable only
        # after the calibration/test feature timestamp.
        train_mask = (as_of_dates <= train_end) & (horizon_dates < calibration_start)
        calibration_mask = (
            (as_of_dates >= calibration_start)
            & (as_of_dates <= calibration_end)
            & (horizon_dates < test_start)
        )
        test_mask = as_of_dates >= test_start
        if not train_mask.any() or not calibration_mask.any() or not test_mask.any():
            raise ValueError("Chronological train/calibration/test partitions are not all populated")
        scaler = StandardScaler().fit(X[train_mask])
        Xs = scaler.transform(X)

        target_artifacts: dict[str, Any] = {}
        target_evaluations: dict[str, Any] = {}
        for target in TARGET_COLUMNS:
            values = np.asarray([getattr(row, target) if getattr(row, target) is not None else np.nan for row in ordered], dtype=float)
            valid = ~np.isnan(values)
            masks = {
                "train": train_mask & valid,
                "calibration": calibration_mask & valid,
                "test": test_mask & valid,
            }
            counts = {key: int(mask.sum()) for key, mask in masks.items()}
            if any(count < 10 for count in counts.values()) or any(len(np.unique(values[mask])) < 2 for mask in masks.values()):
                target_evaluations[target] = {"status": "INSUFFICIENT_PARTITION_EVIDENCE", "partitions": counts}
                continue
            estimator = LogisticRegression(
                C=0.5,
                class_weight="balanced",
                max_iter=2000,
                random_state=77,
            ).fit(Xs[masks["train"]], values[masks["train"]].astype(int))
            calibration_raw = estimator.predict_proba(Xs[masks["calibration"]])[:, 1]
            calibration_logits = np.asarray([_logit(value) for value in calibration_raw]).reshape(-1, 1)
            calibrator = LogisticRegression(C=1.0, max_iter=1000, random_state=77).fit(
                calibration_logits,
                values[masks["calibration"]].astype(int),
            )
            raw = estimator.predict_proba(Xs[masks["test"]])[:, 1]
            calibrated = calibrator.predict_proba(np.asarray([_logit(value) for value in raw]).reshape(-1, 1))[:, 1]
            y_test = values[masks["test"]].astype(int)
            metrics = {
                "status": "EVALUATED",
                "partitions": counts,
                "test_positive": int(y_test.sum()),
                "test_negative": int(len(y_test) - y_test.sum()),
                "raw_brier": round(float(brier_score_loss(y_test, raw)), 8),
                "calibrated_brier": round(float(brier_score_loss(y_test, calibrated)), 8),
                "raw_log_loss": round(float(log_loss(y_test, raw)), 8),
                "calibrated_log_loss": round(float(log_loss(y_test, calibrated)), 8),
                "calibrated_ece": round(_ece(calibrated, y_test), 8),
                "test_auc": round(float(roc_auc_score(y_test, calibrated)), 8),
            }
            metrics["gate_pass"] = bool(
                metrics["calibrated_brier"] <= self.policy.maximum_test_brier
                and metrics["calibrated_ece"] <= self.policy.maximum_test_ece
                and metrics["test_auc"] >= self.policy.minimum_test_auc
            )
            target_evaluations[target] = metrics
            target_artifacts[target] = {
                "coefficient": estimator.coef_[0].tolist(),
                "intercept": float(estimator.intercept_[0]),
                "calibrator_coefficient": float(calibrator.coef_[0][0]),
                "calibrator_intercept": float(calibrator.intercept_[0]),
                "metrics": metrics,
            }

        regressions: dict[str, Any] = {}
        regression_evaluation: dict[str, Any] = {}
        for target in REGRESSION_COLUMNS:
            values = np.asarray([getattr(row, target) if getattr(row, target) is not None else np.nan for row in ordered], dtype=float)
            valid = ~np.isnan(values)
            fit_mask = (train_mask | calibration_mask) & valid
            evaluate_mask = test_mask & valid
            if int(fit_mask.sum()) < 30 or int(evaluate_mask.sum()) < 10:
                regression_evaluation[target] = {"status": "INSUFFICIENT_PARTITION_EVIDENCE"}
                continue
            estimator = Ridge(alpha=10.0).fit(Xs[fit_mask], values[fit_mask])
            predictions = estimator.predict(Xs[evaluate_mask])
            mae = float(np.mean(np.abs(predictions - values[evaluate_mask])))
            regressions[target] = {
                "coefficient": estimator.coef_.tolist(),
                "intercept": float(estimator.intercept_),
                "minimum": 0.0,
            }
            regression_evaluation[target] = {
                "status": "EVALUATED",
                "train_calibration_samples": int(fit_mask.sum()),
                "test_samples": int(evaluate_mask.sum()),
                "test_mae": round(mae, 8),
            }

        required = ("target_1_before_stop", "profitable_at_horizon", "thesis_invalidation")
        promotion_eligible = all(
            target_evaluations.get(target, {}).get("gate_pass") is True for target in required
        )
        evaluated = [value for value in target_evaluations.values() if value.get("status") == "EVALUATED"]
        confidence = 0.0
        if evaluated:
            sample_factor = min(1.0, len(ordered) / max(self.policy.minimum_training_samples * 2, 1))
            quality_factor = max(0.0, 1.0 - float(np.mean([value["calibrated_brier"] for value in evaluated])))
            confidence = round(100.0 * (sample_factor * 0.45 + quality_factor * 0.55), 4)
        artifact = {
            "version": self.version,
            "feature_names": list(NUMERIC_FEATURES),
            "feature_mean": scaler.mean_.tolist(),
            "feature_scale": scaler.scale_.tolist(),
            "targets": target_artifacts,
            "regressions": regressions,
            "training_distribution": {
                "standardized_mean_abs_p95": round(float(np.percentile(np.mean(np.abs(Xs[train_mask]), axis=1), 95)), 8),
            },
            "model_confidence": confidence,
        }
        evaluation = {
            "version": "M77.0-EVALUATION-1.0",
            "readiness": readiness,
            "partitions": {
                "train_end": train_end,
                "calibration_start": calibration_start,
                "calibration_end": calibration_end,
                "test_start": str(min(as_of_dates[test_mask])),
                "test_end": str(max(as_of_dates[test_mask])),
                "same_as_of_date_cross_partition": False,
                "label_horizon_overlap_cross_partition": False,
                "purged_for_forward_horizon": int(
                    len(ordered) - train_mask.sum() - calibration_mask.sum() - test_mask.sum()
                ),
            },
            "targets": target_evaluations,
            "regressions": regression_evaluation,
            "promotion_eligible": promotion_eligible,
            "model_confidence": confidence,
            "automatic_activation": False,
            "authority_effect": False,
        }
        return artifact, evaluation

    @staticmethod
    def eligible_observations(observations: list[Any]) -> list[Any]:
        return [
            row
            for row in observations
            if getattr(row, "entry_triggered", None) == 1
            and getattr(row, "status", "") in {"REALIZED", "PARTIALLY_AMBIGUOUS", "CENSORED"}
            and bool(getattr(row, "horizon_end", None))
        ]


class OutcomeProbabilityRuntime:
    """Scores an approved shadow artifact; never mutates governed decisions."""

    def __init__(
        self,
        *,
        model_id: str,
        model_version: str,
        artifact: dict[str, Any],
        observations: list[Any],
        policy: OutcomeProbabilityPolicy | None = None,
    ):
        self.model_id = model_id
        self.model_version = model_version
        self.artifact = artifact
        self.observations = observations
        self.policy = policy or OutcomeProbabilityPolicy()
        self.features = PointInTimeFeatureBuilder()

    def score(self, profile: Any) -> OutcomeProbabilityAssessment:
        payload = _as_payload(profile)
        feature_map = self.features.build(payload)
        names = self.artifact["feature_names"]
        vector = np.asarray([feature_map[name] for name in names], dtype=float)
        mean = np.asarray(self.artifact["feature_mean"], dtype=float)
        scale = np.asarray(self.artifact["feature_scale"], dtype=float)
        scale = np.where(scale == 0, 1.0, scale)
        standardized = (vector - mean) / scale
        p95 = max(float((self.artifact.get("training_distribution") or {}).get("standardized_mean_abs_p95") or 1.0), 1e-6)
        distance = float(np.mean(np.abs(standardized)))
        ood = min(1.0, distance / (p95 * 2.0))

        probabilities: dict[str, float | None] = {}
        contributions: list[dict[str, Any]] = []
        targets = self.artifact.get("targets") or {}
        for target in TARGET_COLUMNS:
            config = targets.get(target)
            if not config:
                probabilities[target] = None
                continue
            coefficient = np.asarray(config["coefficient"], dtype=float)
            raw = _sigmoid(float(np.dot(coefficient, standardized) + config["intercept"]))
            calibrated = _sigmoid(
                float(config["calibrator_coefficient"]) * _logit(raw)
                + float(config["calibrator_intercept"])
            )
            probabilities[target] = round(calibrated * 100.0, 4)
            if target == "target_1_before_stop":
                for name, value, coefficient_value in zip(names, standardized, coefficient):
                    contributions.append(
                        {
                            "feature": name,
                            "standardized_value": round(float(value), 5),
                            "coefficient": round(float(coefficient_value), 5),
                            "log_odds_contribution": round(float(value * coefficient_value), 5),
                        }
                    )
        contributions.sort(key=lambda item: abs(item["log_odds_contribution"]), reverse=True)
        previous = probabilities.get("target_1_before_stop")
        for target in ("target_2_before_stop", "target_3_before_stop"):
            current = probabilities.get(target)
            if previous is not None and current is not None:
                current = min(previous, current)
                probabilities[target] = round(current, 4)
            if current is not None:
                previous = current

        regression_values: dict[str, float | None] = {}
        for target in REGRESSION_COLUMNS:
            config = (self.artifact.get("regressions") or {}).get(target)
            if not config:
                regression_values[target] = None
                continue
            value = float(np.dot(np.asarray(config["coefficient"], dtype=float), standardized) + config["intercept"])
            regression_values[target] = round(max(float(config.get("minimum", 0.0)), value), 4)

        confidence = float(self.artifact.get("model_confidence") or 0.0) / 100.0
        uncertainty = min(1.0, max(0.0, (1.0 - confidence) * 0.65 + ood * 0.35))
        plan = payload.get("trade_plan") or {}
        reward_risk = max(0.0, float(plan.get("structural_reward_risk") or 0.0))
        p_t1 = probabilities.get("target_1_before_stop")
        expected_value_r = None if p_t1 is None else round((p_t1 / 100.0) * reward_risk - (1.0 - p_t1 / 100.0), 4)
        disposition = self._disposition(probabilities, expected_value_r, uncertainty, ood)
        warnings = ["SHADOW_ONLY_NO_RANKING_OR_TRADE_AUTHORITY_EFFECT"]
        if ood > self.policy.maximum_trade_ood_score:
            warnings.append("OUT_OF_DISTRIBUTION")
        if uncertainty > self.policy.maximum_trade_uncertainty:
            warnings.append("MODEL_UNCERTAINTY_ABOVE_TRADE_THRESHOLD")
        analogs = self._analogs(feature_map, payload)
        if analogs.get("sample_size", 0) < self.policy.minimum_analogs:
            warnings.append("INSUFFICIENT_SIMILAR_HISTORICAL_ANALOGS")
        return OutcomeProbabilityAssessment(
            status="SHADOW_READY",
            model_id=self.model_id,
            model_version=self.model_version,
            calibration_status="OUT_OF_SAMPLE_EVALUATED",
            target_1_before_stop=p_t1,
            target_2_before_stop=probabilities.get("target_2_before_stop"),
            target_3_before_stop=probabilities.get("target_3_before_stop"),
            profitable_at_horizon=probabilities.get("profitable_at_horizon"),
            thesis_invalidation=probabilities.get("thesis_invalidation"),
            expected_mfe_pct=regression_values.get("maximum_favorable_excursion_pct"),
            expected_mae_pct=regression_values.get("maximum_adverse_excursion_pct"),
            expected_days_to_target_1=regression_values.get("days_to_target_1"),
            expected_days_to_stop=regression_values.get("days_to_stop"),
            expected_value_r=expected_value_r,
            model_confidence=round(confidence * 100.0, 4),
            epistemic_uncertainty=round(uncertainty, 6),
            out_of_distribution_score=round(ood, 6),
            recommended_disposition=disposition,
            analog_evidence=analogs,
            feature_contributions=contributions[:12],
            warnings=warnings,
            lineage={
                **self.features.lineage(payload),
                "model_id": self.model_id,
                "model_version": self.model_version,
                "runtime_mode": "SHADOW",
                "authority_effect": False,
            },
        ).finalize()

    def _disposition(
        self,
        probabilities: dict[str, float | None],
        expected_value_r: float | None,
        uncertainty: float,
        ood: float,
    ) -> str:
        p_t1 = probabilities.get("target_1_before_stop")
        p_profit = probabilities.get("profitable_at_horizon")
        if p_t1 is None or p_profit is None or expected_value_r is None:
            return "ABSTAIN"
        if uncertainty > self.policy.maximum_trade_uncertainty or ood > self.policy.maximum_trade_ood_score:
            return "ABSTAIN"
        if (
            p_t1 / 100.0 >= self.policy.minimum_target_1_probability
            and p_profit / 100.0 >= self.policy.minimum_profitable_probability
            and expected_value_r >= self.policy.minimum_expected_value_r
        ):
            return "TRADE"
        return "WATCH"

    def _analogs(self, features: dict[str, float], payload: dict[str, Any]) -> dict[str, Any]:
        vector = np.asarray([features[name] for name in NUMERIC_FEATURES], dtype=float)
        direction = "BULL" if "BULL" in str(payload.get("direction") or "").upper() else "BEAR"
        candidates = []
        for row in self.observations:
            label = row.label_json or {}
            lineage = row.lineage_json or {}
            historical_direction = str(lineage.get("direction") or label.get("evidence", {}).get("direction") or "").upper()
            if historical_direction and direction not in historical_direction:
                continue
            other = np.asarray([float((row.features_json or {}).get(name, 0.0)) for name in NUMERIC_FEATURES], dtype=float)
            scale = np.maximum(np.abs(vector) + np.abs(other), 1.0)
            distance = float(np.sqrt(np.mean(((vector - other) / scale) ** 2)))
            candidates.append((distance, row))
        selected = [row for _, row in sorted(candidates, key=lambda item: item[0])[: self.policy.analog_limit]]
        if not selected:
            return {"status": "NO_ANALOGS", "sample_size": 0}
        t1 = [row.target_1_before_stop for row in selected if row.target_1_before_stop is not None]
        profit = [row.profitable_at_horizon for row in selected if row.profitable_at_horizon is not None]
        mfe = [row.maximum_favorable_excursion_pct for row in selected if row.maximum_favorable_excursion_pct is not None]
        mae = [row.maximum_adverse_excursion_pct for row in selected if row.maximum_adverse_excursion_pct is not None]
        days = [row.days_to_target_1 for row in selected if row.days_to_target_1 is not None]
        return {
            "status": "READY" if len(selected) >= self.policy.minimum_analogs else "DEVELOPING",
            "sample_size": len(selected),
            "target_1_before_stop_rate_pct": None if not t1 else round(sum(t1) / len(t1) * 100.0, 2),
            "profitable_horizon_rate_pct": None if not profit else round(sum(profit) / len(profit) * 100.0, 2),
            "median_mfe_pct": None if not mfe else round(float(median(mfe)), 4),
            "median_mae_pct": None if not mae else round(float(median(mae)), 4),
            "median_days_to_target_1": None if not days else round(float(median(days)), 2),
            "candidate_ids": [row.candidate_id for row in selected[:5]],
        }
