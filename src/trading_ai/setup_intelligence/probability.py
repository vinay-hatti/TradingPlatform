from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean
from typing import Any

from .contracts import ConditionalProbability, stable_hash
from .policy import DEFAULT_POLICY, SetupIntelligencePolicy

TARGETS = ("target_1_before_stop", "target_2_before_stop", "target_3_before_stop", "profitable_at_horizon")
CONTEXT_KEYS = ("market_regime", "gamma_regime", "sector_regime", "volatility_regime")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _valid_binary(rows: list[Any], name: str) -> list[int]:
    return [int(getattr(row, name)) for row in rows if getattr(row, name, None) is not None]


def _average(rows: list[Any], name: str) -> float | None:
    values = [float(getattr(row, name)) for row in rows if getattr(row, name, None) is not None]
    return mean(values) if values else None


class HierarchicalSetupProbabilityEngine:
    """Interpretable empirical conditional model with governed shrinkage.

    M78 intentionally begins with a transparent hierarchical estimator instead of
    an opaque global model. Local context cells shrink toward setup-specific priors.
    """

    version = "M78-HIERARCHICAL-EMPIRICAL-1.0"

    def __init__(self, policy: SetupIntelligencePolicy = DEFAULT_POLICY):
        self.policy = policy

    def readiness(self, rows: list[Any]) -> dict[str, Any]:
        closed = [r for r in rows if str(getattr(r, "status", "")).upper() in {"CLOSED", "MATURE", "LABELED"}]
        by_setup: dict[str, list[Any]] = defaultdict(list)
        for row in closed:
            by_setup[str(row.setup_type)].append(row)
        setups = {}
        for stype, sample in sorted(by_setup.items()):
            y = _valid_binary(sample, "target_1_before_stop")
            dates = {str(r.as_of)[:10] for r in sample}
            pos = sum(y); neg = len(y) - pos
            ready = len(y) >= self.policy.minimum_setup_prior_observations and pos >= self.policy.minimum_positive_observations and neg >= self.policy.minimum_negative_observations and len(dates) >= self.policy.minimum_distinct_dates
            setups[stype] = {"status": "READY" if ready else "INSUFFICIENT_EVIDENCE", "observations": len(y), "positive": pos, "negative": neg, "distinct_dates": len(dates)}
        return {"status": "READY" if any(v["status"] == "READY" for v in setups.values()) else "INSUFFICIENT_EVIDENCE",
                "model_version": self.version, "setups": setups,
                "requirements": {"minimum_setup_prior_observations": self.policy.minimum_setup_prior_observations,
                "minimum_positive_observations": self.policy.minimum_positive_observations,
                "minimum_negative_observations": self.policy.minimum_negative_observations,
                "minimum_distinct_dates": self.policy.minimum_distinct_dates}}

    def train(self, rows: list[Any], model_version: str) -> tuple[dict[str, Any], dict[str, Any]]:
        readiness = self.readiness(rows)
        if readiness["status"] != "READY":
            raise ValueError(f"M78 setup evidence is not ready: {readiness}")
        closed = [r for r in rows if str(getattr(r, "status", "")).upper() in {"CLOSED", "MATURE", "LABELED"}]
        priors: dict[str, Any] = {}
        cells: dict[str, Any] = {}
        for stype in sorted({str(r.setup_type) for r in closed}):
            sample = [r for r in closed if str(r.setup_type) == stype]
            if readiness["setups"].get(stype, {}).get("status") != "READY":
                continue
            priors[stype] = self._summarize(sample)
            grouped: dict[tuple[str, ...], list[Any]] = defaultdict(list)
            for row in sample:
                grouped[tuple(str(getattr(row, key, "UNKNOWN") or "UNKNOWN") for key in CONTEXT_KEYS)].append(row)
            for key, local in grouped.items():
                if len(_valid_binary(local, "target_1_before_stop")) < self.policy.minimum_local_cell_observations:
                    continue
                cells["|".join((stype, *key))] = self._summarize(local)
        artifact = {"engine_version": self.version, "model_version": model_version, "created_at": _now(),
                    "priors": priors, "cells": cells, "context_keys": list(CONTEXT_KEYS),
                    "shrinkage_strength": self.policy.shrinkage_strength}
        evaluation = {"readiness": readiness, "setup_priors": len(priors), "conditional_cells": len(cells),
                      "automatic_activation": False, "authority_effect": False, "prospective_certification_required": True}
        artifact["state_hash"] = stable_hash({"artifact": artifact, "evaluation": evaluation})
        return artifact, evaluation

    def predict(self, setup: Any, artifact: dict[str, Any]) -> ConditionalProbability:
        stype = str(setup.setup_type)
        prior = (artifact.get("priors") or {}).get(stype)
        if not prior:
            return ConditionalProbability(status="INSUFFICIENT_EVIDENCE", setup_type=stype, observation_count=0)
        context = getattr(setup, "context_json", None) or getattr(setup, "context", {}) or {}
        key = "|".join((stype, *(str(context.get(name, "UNKNOWN") or "UNKNOWN") for name in CONTEXT_KEYS)))
        local = (artifact.get("cells") or {}).get(key)
        summary = prior
        population = {"level": "SETUP_PRIOR", "setup_type": stype}
        if local:
            n = float(local["observation_count"])
            k = float(artifact.get("shrinkage_strength", self.policy.shrinkage_strength))
            w = n / (n + k)
            summary = {}
            for name in ("target_1_probability", "target_2_probability", "target_3_probability", "profitable_probability",
                         "expected_mfe_pct", "expected_mae_pct", "expected_return_pct", "expected_holding_days"):
                lv, pv = local.get(name), prior.get(name)
                if lv is None: summary[name] = pv
                elif pv is None: summary[name] = lv
                else: summary[name] = w * float(lv) + (1.0 - w) * float(pv)
            summary["observation_count"] = int(local["observation_count"])
            population = {"level": "CONDITIONAL_CELL_SHRUNK", "cell": key, "local_observations": int(n), "shrinkage_weight": round(w, 6)}
        n = int(summary.get("observation_count") or prior.get("observation_count") or 0)
        confidence = min(100.0, 100.0 * n / max(self.policy.minimum_setup_prior_observations * 2, 1))
        t1 = summary.get("target_1_probability")
        return ConditionalProbability(status="READY", setup_type=stype, observation_count=n,
            target_1_probability=_round(t1), target_2_probability=_round(summary.get("target_2_probability")),
            target_3_probability=_round(summary.get("target_3_probability")),
            stop_probability=_round(1.0 - float(t1)) if t1 is not None else None,
            profitable_probability=_round(summary.get("profitable_probability")), expected_mfe_pct=_round(summary.get("expected_mfe_pct")),
            expected_mae_pct=_round(summary.get("expected_mae_pct")), expected_return_pct=_round(summary.get("expected_return_pct")),
            expected_holding_days=_round(summary.get("expected_holding_days")), confidence=round(confidence, 4), comparable_population=population)

    @staticmethod
    def _summarize(rows: list[Any]) -> dict[str, Any]:
        result: dict[str, Any] = {"observation_count": len(_valid_binary(rows, "target_1_before_stop"))}
        for name, output in (("target_1_before_stop", "target_1_probability"), ("target_2_before_stop", "target_2_probability"),
                             ("target_3_before_stop", "target_3_probability"), ("profitable_at_horizon", "profitable_probability")):
            values = _valid_binary(rows, name); result[output] = mean(values) if values else None
        result["expected_mfe_pct"] = _average(rows, "maximum_favorable_excursion_pct")
        result["expected_mae_pct"] = _average(rows, "maximum_adverse_excursion_pct")
        result["expected_return_pct"] = _average(rows, "realized_return_pct")
        result["expected_holding_days"] = _average(rows, "days_to_target_1")
        return result


def _round(value: Any) -> float | None:
    return round(float(value), 8) if value is not None else None
