from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

from .alert_rule_engine import AlertRuleEngine
from .alert_rule_policy import AlertRule, AlertRulePolicy
from .error_budget_engine import ErrorBudgetEngine
from .observability_profile import MetricSample
from .slo_engine import SLOEngine
from .slo_policy import ErrorBudgetPolicy, SLOPolicy
from .slo_profile import SLODefinition
from .telemetry_retention_policy import TelemetryRetentionPolicy
from .telemetry_retention_service import TelemetryRetentionService


class ObservabilityGovernanceService:
    def __init__(
        self,
        *,
        slo_policy: SLOPolicy | None = None,
        error_budget_policy: ErrorBudgetPolicy | None = None,
        alert_policy: AlertRulePolicy | None = None,
        retention_policy: TelemetryRetentionPolicy | None = None,
    ) -> None:
        self.slo = SLOEngine(slo_policy)
        self.error_budget = ErrorBudgetEngine(
            error_budget_policy
        )
        self.alerts = AlertRuleEngine(alert_policy)
        self.retention = TelemetryRetentionService(
            retention_policy
        )

    def evaluate_slo(
        self,
        *,
        definition: SLODefinition,
        samples: Iterable[MetricSample],
        alert_rule: AlertRule | None = None,
    ) -> dict:
        slo = self.slo.evaluate(definition, samples)
        budget = self.error_budget.evaluate(slo)
        alert = None
        if alert_rule is not None:
            alert = self.alerts.evaluate(
                rule=alert_rule,
                value=budget.burn_rate,
                service_name=definition.service_name,
                environment=definition.environment,
                fields={
                    "slo_id": definition.slo_id,
                    "slo_observed": slo.observed,
                    "slo_target": slo.target,
                    "budget_remaining": budget.remaining_fraction,
                },
            )
        return {
            "slo": asdict(slo),
            "error_budget": asdict(budget),
            "alert": asdict(alert) if alert else None,
        }
