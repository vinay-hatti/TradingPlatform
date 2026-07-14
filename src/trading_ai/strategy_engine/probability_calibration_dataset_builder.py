from __future__ import annotations

from collections import Counter
from math import isfinite
from typing import Iterable

from trading_ai.strategy_engine.probability_calibration_dataset_policy import (
    ProbabilityCalibrationDatasetPolicy,
)
from trading_ai.strategy_engine.probability_calibration_dataset_profile import (
    ProbabilityCalibrationDataset,
    ProbabilityCalibrationObservation,
)


class ProbabilityCalibrationDatasetBuilder:
    def __init__(self, policy: ProbabilityCalibrationDatasetPolicy | None = None):
        self.policy = policy or ProbabilityCalibrationDatasetPolicy()
        self.policy.validate()

    def build(self, records: Iterable) -> ProbabilityCalibrationDataset:
        records = list(records or [])
        observations = []
        rejected = Counter()
        warnings = []
        for index, record in enumerate(records):
            probability = self._first(record, self.policy.probability_fields)
            if probability is None:
                rejected["MISSING_PROBABILITY"] += 1
                if self.policy.discard_missing_probability:
                    continue
            try:
                probability = float(probability)
            except (TypeError, ValueError):
                rejected["INVALID_PROBABILITY"] += 1
                continue
            if not isfinite(probability):
                rejected["NON_FINITE_PROBABILITY"] += 1
                continue
            if self.policy.clamp_probabilities:
                probability = min(max(probability, self.policy.probability_floor), self.policy.probability_ceiling)
            elif not 0.0 <= probability <= 1.0:
                rejected["PROBABILITY_OUT_OF_RANGE"] += 1
                continue

            outcome = self._first(record, self.policy.outcome_fields)
            if outcome is None and self.policy.infer_outcome_from_pnl:
                pnl = self._first(record, self.policy.pnl_fields)
                if pnl is not None:
                    try:
                        outcome = float(pnl) > self.policy.winning_pnl_threshold
                    except (TypeError, ValueError):
                        outcome = None
            normalized = self._outcome(outcome)
            if normalized is None:
                rejected["MISSING_OR_INVALID_OUTCOME"] += 1
                if self.policy.discard_missing_outcome:
                    continue

            weight = self._first(record, self.policy.weight_fields, 1.0)
            try:
                weight = float(weight)
            except (TypeError, ValueError):
                weight = 1.0
                warnings.append("INVALID_SAMPLE_WEIGHT_DEFAULTED")
            if not isfinite(weight) or weight <= 0.0:
                weight = 1.0
                warnings.append("NON_POSITIVE_SAMPLE_WEIGHT_DEFAULTED")

            observations.append(ProbabilityCalibrationObservation(
                probability=probability,
                outcome=int(normalized),
                timestamp=self._first(record, self.policy.timestamp_fields),
                symbol=str(self._first(record, self.policy.symbol_fields, "UNKNOWN") or "UNKNOWN").upper(),
                strategy=str(self._first(record, self.policy.strategy_fields, "UNKNOWN") or "UNKNOWN").upper(),
                direction=str(self._first(record, self.policy.direction_fields, "UNKNOWN") or "UNKNOWN").upper(),
                market_regime=str(self._first(record, self.policy.regime_fields, "UNKNOWN") or "UNKNOWN").upper(),
                sample_weight=weight,
                source_index=index,
                metadata={"source_type": type(record).__name__},
            ))

        return ProbabilityCalibrationDataset(
            observations=observations,
            input_count=len(records),
            accepted_count=len(observations),
            rejected_count=sum(rejected.values()),
            rejection_counts=dict(rejected),
            warnings=sorted(set(warnings)),
            metadata={
                "positive_count": sum(x.outcome for x in observations),
                "negative_count": len(observations) - sum(x.outcome for x in observations),
            },
        )

    def _first(self, record, fields, default=None):
        for field in fields:
            value = record.get(field) if isinstance(record, dict) else getattr(record, field, None)
            if value is not None and value != "":
                return value
        return default

    @staticmethod
    def _outcome(value):
        if isinstance(value, bool):
            return int(value)
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip().upper()
            if normalized in {"1", "TRUE", "YES", "WIN", "WON", "PROFIT", "PROFITABLE", "SUCCESS"}:
                return 1
            if normalized in {"0", "FALSE", "NO", "LOSS", "LOST", "UNPROFITABLE", "FAILURE"}:
                return 0
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if numeric in (0.0, 1.0):
            return int(numeric)
        return None
