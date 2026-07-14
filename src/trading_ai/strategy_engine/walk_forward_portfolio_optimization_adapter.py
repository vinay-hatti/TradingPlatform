from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, fields, replace
from typing import Any

from .walk_forward_adapter_profile import (
    WalkForwardAdapterDiagnostics,
    WalkForwardEvaluationResult,
)


class WalkForwardPortfolioOptimizationAdapter:
    """Evaluate Phase 5 portfolio policies inside institutional walk-forward windows."""

    def __init__(
        self,
        *,
        initial_capital: float,
        base_policy: Any | None = None,
        optimization_service: Any | None = None,
    ) -> None:
        if initial_capital <= 0.0:
            raise ValueError("initial_capital must be greater than zero")
        self.initial_capital = float(initial_capital)

        if base_policy is None or optimization_service is None:
            try:
                from .portfolio_optimization_policy import PortfolioOptimizationPolicy
                from .portfolio_optimization_service import PortfolioOptimizationService
            except ImportError as exc:
                raise RuntimeError(
                    "Phase 5 portfolio optimization modules must be installed"
                ) from exc
            base_policy = base_policy or PortfolioOptimizationPolicy()
            optimization_service = optimization_service or PortfolioOptimizationService(
                policy=base_policy
            )

        self.base_policy = base_policy
        self.optimization_service = optimization_service
        self.diagnostics = WalkForwardAdapterDiagnostics(
            adapter_name=self.__class__.__name__,
        )
        self._policy_fields = {item.name for item in fields(self.base_policy)}
        self._parameter_signatures: set[tuple[tuple[str, str], ...]] = set()

    def evaluate(
        self,
        observations: Sequence[Any],
        parameters: dict[str, Any],
    ) -> dict[str, float]:
        return self.evaluate_detailed(observations, parameters).as_engine_metrics()

    def evaluate_detailed(
        self,
        observations: Sequence[Any],
        parameters: dict[str, Any],
    ) -> WalkForwardEvaluationResult:
        self.diagnostics.evaluation_count += 1
        self._parameter_signatures.add(
            tuple(sorted((str(k), repr(v)) for k, v in parameters.items()))
        )
        self.diagnostics.parameter_sets_seen = len(self._parameter_signatures)

        try:
            policy = self._policy(parameters)
            service = self._service_for_policy(policy)
            profiles = []
            snapshot_metrics = []
            for snapshot in observations:
                candidates = self._candidates(snapshot)
                if not candidates:
                    continue
                profile = service.optimize(candidates, self.initial_capital)
                profiles.append(profile)
                snapshot_metrics.append(self._metrics(profile))

            if not profiles:
                return WalkForwardEvaluationResult(
                    observation_count=len(observations),
                    valid=False,
                    rejection_reasons=["NO_PORTFOLIO_OPTIMIZATION_SNAPSHOTS"],
                )

            count = len(snapshot_metrics)
            result = WalkForwardEvaluationResult(
                score=sum(item["score"] for item in snapshot_metrics) / count,
                return_pct=sum(item["return"] for item in snapshot_metrics) / count,
                sharpe=self._stability_sharpe(
                    [item["return"] for item in snapshot_metrics]
                ),
                max_drawdown_pct=max(
                    item["max_drawdown_pct"] for item in snapshot_metrics
                ),
                observation_count=len(observations),
                trade_count=sum(item["selected_count"] for item in snapshot_metrics),
                valid=all(bool(getattr(profile, "valid", False)) for profile in profiles),
                warnings=self._unique(
                    warning
                    for profile in profiles
                    for warning in getattr(profile, "warnings", [])
                ),
                rejection_reasons=self._unique(
                    reason
                    for profile in profiles
                    for reason in getattr(profile, "rejection_reasons", [])
                ),
                metadata={
                    "snapshot_count": count,
                    "policy": asdict(policy),
                    "average_exposure_pct": sum(
                        item["exposure"] for item in snapshot_metrics
                    ) / count,
                    "average_risk_pct": sum(
                        item["risk"] for item in snapshot_metrics
                    ) / count,
                },
            )
            self.diagnostics.successful_evaluations += 1
            return result
        except Exception as exc:
            self.diagnostics.failed_evaluations += 1
            self.diagnostics.warnings.append(
                f"PORTFOLIO_WALK_FORWARD_EVALUATION_FAILED:{type(exc).__name__}"
            )
            return WalkForwardEvaluationResult(
                observation_count=len(observations),
                valid=False,
                rejection_reasons=["PORTFOLIO_WALK_FORWARD_EVALUATION_FAILED"],
                metadata={
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                },
            )

    def _policy(self, parameters: dict[str, Any]) -> Any:
        unknown = sorted(set(parameters) - self._policy_fields)
        if unknown:
            raise ValueError(
                "unsupported PortfolioOptimizationPolicy fields: "
                + ", ".join(unknown)
            )
        policy = replace(self.base_policy, **parameters)
        validate = getattr(policy, "validate", None)
        if callable(validate):
            validate()
        return policy

    def _service_for_policy(self, policy: Any) -> Any:
        service_type = type(self.optimization_service)
        try:
            return service_type(policy=policy)
        except TypeError:
            if hasattr(self.optimization_service, "with_policy"):
                return self.optimization_service.with_policy(policy)
            self.optimization_service.policy = policy
            engine = getattr(self.optimization_service, "engine", None)
            if engine is not None and hasattr(engine, "policy"):
                engine.policy = policy
            return self.optimization_service

    @staticmethod
    def _candidates(snapshot: Any) -> list[Any]:
        if isinstance(snapshot, dict):
            for key in ("candidates", "decisions", "positions"):
                if key in snapshot:
                    return list(snapshot[key] or [])
        for key in ("candidates", "decisions", "positions"):
            value = getattr(snapshot, key, None)
            if value is not None:
                return list(value)
        if isinstance(snapshot, (list, tuple)):
            return list(snapshot)
        return []

    @staticmethod
    def _metrics(profile: Any) -> dict[str, float]:
        return {
            "score": float(getattr(profile, "objective_score", 0.0) or 0.0),
            "return": float(
                getattr(profile, "expected_portfolio_return_pct", 0.0) or 0.0
            ),
            "max_drawdown_pct": abs(
                float(getattr(profile, "total_risk_pct", 0.0) or 0.0)
            ),
            "exposure": float(
                getattr(profile, "portfolio_exposure_pct", 0.0) or 0.0
            ),
            "risk": float(getattr(profile, "total_risk_pct", 0.0) or 0.0),
            "selected_count": int(getattr(profile, "selected_count", 0) or 0),
        }

    @staticmethod
    def _stability_sharpe(returns: list[float]) -> float:
        if len(returns) < 2:
            return 0.0
        mean = sum(returns) / len(returns)
        variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
        standard_deviation = variance ** 0.5
        return mean / standard_deviation if standard_deviation > 0.0 else 0.0

    @staticmethod
    def _unique(values) -> list[str]:
        return list(dict.fromkeys(str(value) for value in values if value))
