from __future__ import annotations

import hashlib
import math
from typing import Iterable

import numpy as np

from trading_ai.strategy_engine.probability_calibration_policy import (
    ProbabilityCalibrationPolicy,
)
from trading_ai.strategy_engine.probability_calibration_profile import (
    CalibrationBin,
    CalibrationModel,
    ProbabilityCalibrationProfile,
)


class ProbabilityCalibrationEngine:
    """Fit, compare, and apply institutional probability calibrators."""

    def __init__(self, policy: ProbabilityCalibrationPolicy | None = None):
        self.policy = policy or ProbabilityCalibrationPolicy()
        self.policy.validate()

    def analyze(
        self,
        predicted_probabilities: Iterable[float],
        outcomes: Iterable[int | bool | float],
        *,
        sample_weights: Iterable[float] | None = None,
        symbol: str = "PORTFOLIO",
        strategy: str = "ALL",
        segment: str = "GLOBAL",
        timestamps: Iterable | None = None,
    ) -> ProbabilityCalibrationProfile:
        probabilities = self._probability_array(predicted_probabilities)
        labels = self._label_array(outcomes)
        weights = self._weight_array(sample_weights, len(probabilities))

        if len(probabilities) != len(labels):
            raise ValueError("predicted_probabilities and outcomes must have equal length")

        warnings: list[str] = []
        rejections: list[str] = []
        count = len(probabilities)
        positives = int(np.sum(labels == 1.0))
        negatives = int(count - positives)

        if count < self.policy.minimum_observations:
            rejections.append("INSUFFICIENT_CALIBRATION_OBSERVATIONS")
        if positives < self.policy.minimum_positive_observations:
            rejections.append("INSUFFICIENT_POSITIVE_OUTCOMES")
        if negatives < self.policy.minimum_negative_observations:
            rejections.append("INSUFFICIENT_NEGATIVE_OUTCOMES")

        if rejections:
            return self._invalid_profile(
                probabilities, labels, weights, symbol, strategy, segment,
                warnings, rejections,
            )

        train_idx, validation_idx = self._split_indices(count, timestamps)
        train_p, val_p = probabilities[train_idx], probabilities[validation_idx]
        train_y, val_y = labels[train_idx], labels[validation_idx]
        train_w, val_w = weights[train_idx], weights[validation_idx]

        candidates: dict[str, CalibrationModel] = {
            "IDENTITY": CalibrationModel(method="IDENTITY", fitted=True),
            "PLATT": self._fit_platt(train_p, train_y, train_w),
            "ISOTONIC": self._fit_isotonic(train_p, train_y, train_w),
        }

        raw_metrics = self._metrics(val_y, val_p, val_w)
        candidate_metrics: dict[str, dict] = {}
        for method, model in candidates.items():
            calibrated = self.apply_model(model, val_p)
            metrics = self._metrics(val_y, calibrated, val_w)
            metrics["objective"] = self._metric_objective(metrics)
            candidate_metrics[method] = metrics

        selected_method = self._select_method(candidate_metrics, raw_metrics)
        selected_model = candidates[selected_method]

        # Refit the accepted calibrator on all observations before production use.
        if selected_method == "PLATT":
            selected_model = self._fit_platt(probabilities, labels, weights)
        elif selected_method == "ISOTONIC":
            selected_model = self._fit_isotonic(probabilities, labels, weights)

        validation_calibrated = self.apply_model(candidates[selected_method], val_p)
        calibrated_metrics = self._metrics(val_y, validation_calibrated, val_w)
        calibrated_all = self.apply_model(selected_model, probabilities)

        raw_bins = self._reliability_bins(labels, probabilities, weights)
        calibrated_bins = self._reliability_bins(labels, calibrated_all, weights)
        intercept, slope = self._calibration_line(labels, calibrated_all, weights)
        auc = self._auc(labels, probabilities, weights)
        sharpness = float(np.sqrt(np.average((calibrated_all - np.average(calibrated_all, weights=weights)) ** 2, weights=weights)))

        brier_improvement = self._relative_improvement(raw_metrics["brier"], calibrated_metrics["brier"])
        log_improvement = self._relative_improvement(raw_metrics["log_loss"], calibrated_metrics["log_loss"])
        score = self._calibration_score(calibrated_metrics, brier_improvement, log_improvement)
        grade = self._grade(score)
        severity = self._severity(calibrated_metrics["ece"])

        if selected_method == "IDENTITY":
            warnings.append("NO_OUT_OF_SAMPLE_CALIBRATION_IMPROVEMENT")
        if calibrated_metrics["ece"] > self.policy.maximum_acceptable_ece:
            warnings.append("CALIBRATION_ERROR_ABOVE_TARGET")

        allowed = not (
            self.policy.reject_critical_calibration
            and severity == "CRITICAL"
        )
        if not allowed:
            rejections.append("CRITICAL_PROBABILITY_MISCALIBRATION")

        model_id = self._model_id(symbol, strategy, segment, selected_method, count)
        selected_model.metadata.update({
            "model_id": model_id,
            "training_observations": count,
            "validation_method": "CHRONOLOGICAL_HOLDOUT",
        })

        return ProbabilityCalibrationProfile(
            model_id=model_id,
            symbol=symbol,
            strategy=strategy,
            segment=segment,
            selected_method=selected_method,
            preferred_method=self.policy.preferred_method.upper(),
            observation_count=count,
            training_count=len(train_idx),
            validation_count=len(validation_idx),
            positive_count=positives,
            negative_count=negatives,
            base_rate=float(np.average(labels, weights=weights)),
            raw_brier_score=raw_metrics["brier"],
            calibrated_brier_score=calibrated_metrics["brier"],
            brier_improvement=brier_improvement,
            raw_log_loss=raw_metrics["log_loss"],
            calibrated_log_loss=calibrated_metrics["log_loss"],
            log_loss_improvement=log_improvement,
            raw_ece=raw_metrics["ece"],
            calibrated_ece=calibrated_metrics["ece"],
            raw_mce=raw_metrics["mce"],
            calibrated_mce=calibrated_metrics["mce"],
            calibration_intercept=intercept,
            calibration_slope=slope,
            sharpness=sharpness,
            discrimination_auc=auc,
            calibration_score=score,
            calibration_grade=grade,
            calibration_severity=severity,
            allowed=allowed,
            valid=True,
            model=selected_model,
            raw_reliability_bins=raw_bins,
            calibrated_reliability_bins=calibrated_bins,
            candidate_metrics=candidate_metrics,
            warnings=warnings,
            rejection_reasons=rejections,
            metadata={
                "validation_fraction": self.policy.validation_fraction,
                "probability_floor": self.policy.probability_floor,
                "probability_ceiling": self.policy.probability_ceiling,
            },
        )

    def calibrate(self, profile: ProbabilityCalibrationProfile, probability: float) -> float:
        if not profile.valid:
            return self._clip(float(probability))
        return float(self.apply_model(profile.model, [probability])[0])

    def calibrate_many(self, profile: ProbabilityCalibrationProfile, probabilities: Iterable[float]) -> np.ndarray:
        if not profile.valid:
            return self._probability_array(probabilities)
        return self.apply_model(profile.model, probabilities)

    def apply_model(self, model: CalibrationModel, probabilities: Iterable[float]) -> np.ndarray:
        p = self._probability_array(probabilities)
        if model.method == "IDENTITY" or not model.fitted:
            return p
        if model.method == "PLATT":
            a = float(model.parameters.get("a", 1.0))
            b = float(model.parameters.get("b", 0.0))
            z = a * self._logit(p) + b
            return self._clip_array(self._sigmoid(z))
        if model.method == "ISOTONIC":
            if not model.x_thresholds:
                return p
            return self._clip_array(np.interp(
                p,
                np.asarray(model.x_thresholds, dtype=float),
                np.asarray(model.y_values, dtype=float),
                left=model.y_values[0],
                right=model.y_values[-1],
            ))
        raise ValueError(f"Unsupported calibration method: {model.method}")

    def _fit_platt(self, p: np.ndarray, y: np.ndarray, w: np.ndarray) -> CalibrationModel:
        x = self._logit(p)
        design = np.column_stack([x, np.ones_like(x)])
        beta = np.array([1.0, 0.0], dtype=float)
        reg = np.diag([self.policy.l2_regularization, self.policy.l2_regularization])
        for iteration in range(self.policy.maximum_iterations):
            pred = self._sigmoid(design @ beta)
            variance = np.maximum(pred * (1.0 - pred), 1e-9)
            gradient = design.T @ (w * (pred - y)) + reg @ beta
            hessian = design.T @ (design * (w * variance)[:, None]) + reg
            try:
                step = np.linalg.solve(hessian, gradient)
            except np.linalg.LinAlgError:
                step = np.linalg.pinv(hessian) @ gradient
            beta_next = beta - step
            if float(np.max(np.abs(beta_next - beta))) <= self.policy.convergence_tolerance:
                beta = beta_next
                break
            beta = beta_next
        return CalibrationModel(
            method="PLATT",
            fitted=True,
            parameters={"a": float(beta[0]), "b": float(beta[1])},
            metadata={"iterations": iteration + 1},
        )

    def _fit_isotonic(self, p: np.ndarray, y: np.ndarray, w: np.ndarray) -> CalibrationModel:
        order = np.argsort(p, kind="mergesort")
        x, labels, weights = p[order], y[order], w[order]
        blocks = []
        for xi, yi, wi in zip(x, labels, weights):
            blocks.append([float(xi), float(xi), float(wi * yi), float(wi)])
            while len(blocks) >= 2:
                prev = blocks[-2][2] / blocks[-2][3]
                curr = blocks[-1][2] / blocks[-1][3]
                if prev <= curr:
                    break
                right = blocks.pop()
                left = blocks.pop()
                blocks.append([
                    left[0], right[1], left[2] + right[2], left[3] + right[3]
                ])
        thresholds: list[float] = []
        values: list[float] = []
        for lower, upper, success_weight, total_weight in blocks:
            value = success_weight / total_weight
            if not thresholds:
                thresholds.append(lower)
                values.append(value)
            thresholds.append(upper)
            values.append(value)
        return CalibrationModel(
            method="ISOTONIC",
            fitted=True,
            x_thresholds=thresholds,
            y_values=values,
            metadata={"block_count": len(blocks)},
        )

    def _select_method(self, metrics: dict[str, dict], raw_metrics: dict) -> str:
        preferred = self.policy.preferred_method.upper()
        if preferred != "AUTO":
            if preferred == "IDENTITY":
                return preferred
            candidate = metrics[preferred]
            improvement = self._relative_improvement(raw_metrics["brier"], candidate["brier"])
            if not self.policy.require_out_of_sample_improvement or improvement >= self.policy.minimum_relative_improvement:
                return preferred
            return "IDENTITY"
        best = min(metrics, key=lambda name: (metrics[name]["objective"], name))
        if best == "IDENTITY":
            return best
        improvement = self._relative_improvement(raw_metrics["brier"], metrics[best]["brier"])
        if self.policy.require_out_of_sample_improvement and improvement < self.policy.minimum_relative_improvement:
            return "IDENTITY"
        return best

    def _metrics(self, y: np.ndarray, p: np.ndarray, w: np.ndarray) -> dict:
        p = self._clip_array(p)
        brier = float(np.average((p - y) ** 2, weights=w))
        log_loss = float(np.average(-(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)), weights=w))
        bins = self._reliability_bins(y, p, w)
        total = max(float(np.sum(w)), 1e-12)
        ece = sum((item.observation_count / len(y)) * item.calibration_error for item in bins)
        mce = max((item.calibration_error for item in bins), default=0.0)
        return {"brier": brier, "log_loss": log_loss, "ece": float(ece), "mce": float(mce), "weight": total}

    def _reliability_bins(self, y: np.ndarray, p: np.ndarray, w: np.ndarray) -> list[CalibrationBin]:
        edges = np.linspace(0.0, 1.0, self.policy.reliability_bin_count + 1)
        result = []
        for index in range(self.policy.reliability_bin_count):
            lower, upper = float(edges[index]), float(edges[index + 1])
            mask = (p >= lower) & ((p < upper) if index < self.policy.reliability_bin_count - 1 else (p <= upper))
            if not np.any(mask):
                continue
            mean_p = float(np.average(p[mask], weights=w[mask]))
            frequency = float(np.average(y[mask], weights=w[mask]))
            result.append(CalibrationBin(index, lower, upper, int(np.sum(mask)), mean_p, frequency, abs(mean_p - frequency)))
        return result

    def _calibration_line(self, y: np.ndarray, p: np.ndarray, w: np.ndarray) -> tuple[float | None, float | None]:
        try:
            model = self._fit_platt(p, y, w)
            return float(model.parameters["b"]), float(model.parameters["a"])
        except Exception:
            return None, None

    def _auc(self, y: np.ndarray, p: np.ndarray, w: np.ndarray) -> float | None:
        positive = y == 1.0
        negative = ~positive
        if not np.any(positive) or not np.any(negative):
            return None
        order = np.argsort(p, kind="mergesort")
        sorted_y = y[order]
        sorted_w = w[order]
        cumulative_negative = 0.0
        favorable = 0.0
        ties: dict[float, list[int]] = {}
        for idx in order:
            ties.setdefault(float(p[idx]), []).append(int(idx))
        for value in sorted(ties):
            indices = ties[value]
            pos_weight = sum(float(w[i]) for i in indices if y[i] == 1.0)
            neg_weight = sum(float(w[i]) for i in indices if y[i] == 0.0)
            favorable += pos_weight * cumulative_negative + 0.5 * pos_weight * neg_weight
            cumulative_negative += neg_weight
        total_pos = float(np.sum(w[positive]))
        total_neg = float(np.sum(w[negative]))
        return favorable / (total_pos * total_neg) if total_pos and total_neg else None

    def _split_indices(self, count: int, timestamps: Iterable | None) -> tuple[np.ndarray, np.ndarray]:
        order = np.arange(count)
        if timestamps is not None:
            values = np.asarray(list(timestamps))
            if len(values) != count:
                raise ValueError("timestamps must have the same length as probabilities")
            order = np.argsort(values, kind="mergesort")
        validation_count = max(self.policy.minimum_validation_observations, int(round(count * self.policy.validation_fraction)))
        validation_count = min(validation_count, count - self.policy.minimum_validation_observations)
        return order[:-validation_count], order[-validation_count:]

    def _metric_objective(self, metrics: dict) -> float:
        total = self.policy.brier_weight + self.policy.log_loss_weight
        return (
            self.policy.brier_weight * metrics["brier"]
            + self.policy.log_loss_weight * metrics["log_loss"]
        ) / total

    def _calibration_score(self, metrics: dict, brier_improvement: float, log_improvement: float) -> float:
        reliability = max(0.0, 100.0 * (1.0 - metrics["ece"] / max(self.policy.critical_ece_threshold, 1e-12)))
        improvement = max(-20.0, min(20.0, 50.0 * (brier_improvement + log_improvement)))
        return float(max(0.0, min(100.0, reliability + improvement)))

    @staticmethod
    def _relative_improvement(before: float, after: float) -> float:
        return float((before - after) / before) if before > 0 else 0.0

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 90: return "A+"
        if score >= 80: return "A"
        if score >= 70: return "B"
        if score >= 60: return "C"
        if score >= 50: return "D"
        return "F"

    def _severity(self, ece: float) -> str:
        if ece >= self.policy.critical_ece_threshold: return "CRITICAL"
        if ece >= self.policy.severe_ece_threshold: return "SEVERE"
        if ece >= self.policy.maximum_acceptable_ece: return "MODERATE"
        return "LOW"

    def _invalid_profile(self, p, y, w, symbol, strategy, segment, warnings, rejections):
        count = len(p)
        base_rate = float(np.average(y, weights=w)) if count else 0.0
        return ProbabilityCalibrationProfile(
            model_id=self._model_id(symbol, strategy, segment, "IDENTITY", count),
            symbol=symbol, strategy=strategy, segment=segment,
            selected_method="IDENTITY", preferred_method=self.policy.preferred_method.upper(),
            observation_count=count, training_count=0, validation_count=0,
            positive_count=int(np.sum(y == 1.0)), negative_count=int(np.sum(y == 0.0)), base_rate=base_rate,
            raw_brier_score=0.0, calibrated_brier_score=0.0, brier_improvement=0.0,
            raw_log_loss=0.0, calibrated_log_loss=0.0, log_loss_improvement=0.0,
            raw_ece=0.0, calibrated_ece=0.0, raw_mce=0.0, calibrated_mce=0.0,
            calibration_intercept=None, calibration_slope=None, sharpness=0.0,
            discrimination_auc=None, calibration_score=0.0, calibration_grade="F",
            calibration_severity="UNKNOWN", allowed=False, valid=False,
            model=CalibrationModel(method="IDENTITY", fitted=True),
            warnings=warnings, rejection_reasons=rejections,
            metadata={"reason": "INSUFFICIENT_CALIBRATION_DATA"},
        )

    def _probability_array(self, values: Iterable[float]) -> np.ndarray:
        array = np.asarray(list(values), dtype=float)
        if array.ndim != 1:
            raise ValueError("probabilities must be one-dimensional")
        if not np.all(np.isfinite(array)):
            raise ValueError("probabilities contain non-finite values")
        return self._clip_array(array)

    @staticmethod
    def _label_array(values: Iterable[int | bool | float]) -> np.ndarray:
        array = np.asarray(list(values), dtype=float)
        if array.ndim != 1 or not np.all(np.isin(array, [0.0, 1.0])):
            raise ValueError("outcomes must contain only binary 0/1 values")
        return array

    @staticmethod
    def _weight_array(values: Iterable[float] | None, count: int) -> np.ndarray:
        array = np.ones(count, dtype=float) if values is None else np.asarray(list(values), dtype=float)
        if len(array) != count or np.any(array <= 0) or not np.all(np.isfinite(array)):
            raise ValueError("sample_weights must be positive finite values with matching length")
        return array

    def _clip(self, value: float) -> float:
        return float(min(self.policy.probability_ceiling, max(self.policy.probability_floor, value)))

    def _clip_array(self, values: np.ndarray) -> np.ndarray:
        return np.clip(values, self.policy.probability_floor, self.policy.probability_ceiling)

    @staticmethod
    def _sigmoid(values: np.ndarray) -> np.ndarray:
        values = np.clip(values, -50.0, 50.0)
        return 1.0 / (1.0 + np.exp(-values))

    def _logit(self, values: np.ndarray) -> np.ndarray:
        values = self._clip_array(values)
        return np.log(values / (1.0 - values))

    @staticmethod
    def _model_id(symbol: str, strategy: str, segment: str, method: str, count: int) -> str:
        raw = f"{symbol}|{strategy}|{segment}|{method}|{count}".encode("utf-8")
        return "CAL-" + hashlib.sha256(raw).hexdigest()[:16].upper()
