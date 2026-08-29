from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile

from trading_ai.observability.alert_rule_engine import AlertRuleEngine
from trading_ai.observability.alert_rule_policy import AlertRule
from trading_ai.observability.error_budget_engine import ErrorBudgetEngine
from trading_ai.observability.observability_governance_service import (
    ObservabilityGovernanceService,
)
from trading_ai.observability.observability_profile import MetricSample
from trading_ai.observability.slo_engine import SLOEngine
from trading_ai.observability.slo_profile import SLODefinition
from trading_ai.observability.telemetry_retention_policy import (
    TelemetryRetentionRule,
)
from trading_ai.observability.telemetry_retention_service import (
    TelemetryRetentionService,
)


def main() -> None:
    now = datetime.now(timezone.utc)
    definition = SLODefinition(
        slo_id="order-availability",
        service_name="order-management",
        environment="paper",
        indicator_type="AVAILABILITY",
        target=0.99,
        metric_name="operation_success",
        threshold=1.0,
        window_seconds=3600,
        labels={"operation": "submit_order"},
    )
    samples = tuple(
        MetricSample(
            name="operation_success",
            metric_type="GAUGE",
            value=value,
            labels={"operation": "submit_order"},
            timestamp=(
                now - timedelta(minutes=index)
            ).isoformat(),
        )
        for index, value in enumerate(
            [1, 1, 1, 1, 1, 1, 1, 1, 0, 0]
        )
    )
    slo = SLOEngine().evaluate(
        definition,
        samples,
        as_of=now,
    )
    assert slo.sample_count == 10
    assert abs(slo.observed - 0.8) < 1e-12
    assert not slo.compliant
    assert slo.recommendation == "SLO_VIOLATED"

    budget = ErrorBudgetEngine().evaluate(slo)
    assert budget.exhausted
    assert budget.fast_burn
    assert budget.recommendation == "PAGE_FAST_BURN"

    rule = AlertRule(
        rule_id="order-fast-burn",
        signal_type="ERROR_BUDGET_BURN_RATE",
        severity="CRITICAL",
        threshold=14.4,
        comparison="GREATER_THAN_OR_EQUAL",
        consecutive_breaches=2,
    )
    engine = AlertRuleEngine()
    assert engine.evaluate(
        rule=rule,
        value=budget.burn_rate,
        service_name="order-management",
        environment="paper",
    ) is None
    alert = engine.evaluate(
        rule=rule,
        value=budget.burn_rate,
        service_name="order-management",
        environment="paper",
    )
    assert alert is not None
    duplicate = engine.evaluate(
        rule=rule,
        value=budget.burn_rate,
        service_name="order-management",
        environment="paper",
    )
    assert duplicate.occurrence_count == 2
    acknowledged = engine.acknowledge(alert.fingerprint)
    assert acknowledged.status == "ACKNOWLEDGED"
    resolved = engine.resolve(alert.fingerprint)
    assert resolved.status == "RESOLVED"

    governance = ObservabilityGovernanceService()
    outcome = governance.evaluate_slo(
        definition=definition,
        samples=samples,
        alert_rule=AlertRule(
            rule_id="governed-fast-burn",
            signal_type="ERROR_BUDGET_BURN_RATE",
            severity="CRITICAL",
            threshold=14.4,
            comparison="GREATER_THAN_OR_EQUAL",
        ),
    )
    assert outcome["slo"]["compliant"] is False
    assert outcome["error_budget"]["fast_burn"] is True
    assert outcome["alert"] is not None

    retention = TelemetryRetentionService()
    old = (now - timedelta(days=10)).isoformat()
    recent = (now - timedelta(minutes=5)).isoformat()
    records = [
        {"id": "old", "timestamp": old},
        {"id": "recent", "timestamp": recent},
    ]
    retained, archived, result = retention.enforce_records(
        records=records,
        rule=TelemetryRetentionRule(
            telemetry_type="TRACE",
            retention_seconds=86400,
            archive_before_delete=True,
            maximum_records=10,
        ),
        timestamp_field="timestamp",
        as_of=now,
    )
    assert [item["id"] for item in retained] == ["recent"]
    assert [item["id"] for item in archived] == ["old"]
    assert result.deleted == 1
    assert result.archived == 1
    assert result.compliant

    with tempfile.TemporaryDirectory() as temp:
        target = Path(temp) / "traces.json"
        archive = Path(temp) / "archive.json"
        target.write_text(
            '{"traces": ['
            f'{{"id": "old", "timestamp": "{old}"}},'
            f'{{"id": "recent", "timestamp": "{recent}"}}'
            ']}',
            encoding="utf-8",
        )
        result = retention.enforce_json_list(
            path=target,
            list_key="traces",
            rule=TelemetryRetentionRule(
                telemetry_type="TRACE",
                retention_seconds=86400,
                archive_before_delete=True,
            ),
            timestamp_field="timestamp",
            archive_path=archive,
            as_of=now,
        )
        assert result.deleted == 1
        assert archive.exists()
        assert '"recent"' in target.read_text(encoding="utf-8")
        assert '"old"' in archive.read_text(encoding="utf-8")

    print(
        "All SLO, error-budget, alert-rule, and telemetry-retention "
        "governance assertions passed."
    )


if __name__ == "__main__":
    main()
