from __future__ import annotations
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path

class ObservabilityDashboardBuilder:
    def build(self, *, metrics=(), traces=(), slos=(), budgets=(),
              alerts=(), retention=()):
        metrics, traces, slos = tuple(metrics), tuple(traces), tuple(slos)
        budgets, alerts, retention = tuple(budgets), tuple(alerts), tuple(retention)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "metric_series": len(metrics),
                "completed_traces": len(traces),
                "slo_count": len(slos),
                "slo_violations": sum(not x.compliant for x in slos),
                "exhausted_budgets": sum(x.exhausted for x in budgets),
                "open_alerts": sum(x.status != "RESOLVED" for x in alerts),
                "retention_deleted": sum(x.deleted for x in retention),
            },
            "metrics": [asdict(x) for x in metrics],
            "traces": [asdict(x) for x in traces],
            "slos": [asdict(x) for x in slos],
            "error_budgets": [asdict(x) for x in budgets],
            "alerts": [asdict(x) for x in alerts],
            "retention": [asdict(x) for x in retention],
        }

    def write(self, path, **kwargs):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.build(**kwargs), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return target
