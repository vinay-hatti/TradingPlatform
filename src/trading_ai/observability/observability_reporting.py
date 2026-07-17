from __future__ import annotations
from dataclasses import asdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path

class ObservabilityReportBuilder:
    SECTIONS = (
        "Structured Logging and Runtime Instrumentation",
        "Metrics Aggregation and Prometheus Exposition",
        "Distributed Tracing and Export Pipelines",
        "Service-Level Objectives and Error Budgets",
        "Observability Alerts and Governance",
        "Telemetry Retention and Compliance",
    )

    def build(self, *, metrics=(), traces=(), slos=(), budgets=(),
              alerts=(), retention=(), metadata=None):
        metrics, traces, slos = tuple(metrics), tuple(traces), tuple(slos)
        budgets, alerts = tuple(budgets), tuple(alerts)
        retention = tuple(retention)
        summary = {
            "metric_series": len(metrics),
            "completed_traces": len(traces),
            "slo_count": len(slos),
            "slo_violations": sum(not x.compliant for x in slos),
            "exhausted_budgets": sum(x.exhausted for x in budgets),
            "open_alerts": sum(x.status != "RESOLVED" for x in alerts),
            "retention_deleted": sum(x.deleted for x in retention),
        }

        def table(items, fields):
            body = []
            for item in items:
                raw = asdict(item)
                body.append("<tr>" + "".join(
                    f"<td>{escape(str(raw.get(f, '')))}</td>" for f in fields
                ) + "</tr>")
            if not body:
                body.append(
                    f'<tr><td colspan="{len(fields)}">No records available.</td></tr>'
                )
            heads = "".join(f"<th>{escape(f)}</th>" for f in fields)
            return f"<table><thead><tr>{heads}</tr></thead><tbody>{''.join(body)}</tbody></table>"

        cards = "".join(
            f"<div class='card'><b>{escape(k.replace('_',' ').title())}</b>"
            f"<span>{v}</span></div>" for k, v in summary.items()
        )
        sections = [
            f"<h2>{self.SECTIONS[0]}</h2><p>Structured logging, operation instrumentation, runtime metrics, correlation IDs, and trace exemplars.</p>",
            f"<h2>{self.SECTIONS[1]}</h2>" + table(metrics, ("name","metric_type","labels","sample_count","value","sum_value")),
            f"<h2>{self.SECTIONS[2]}</h2>" + table(traces, ("trace_id","service_name","environment","status","started_at","completed_at")),
            f"<h2>{self.SECTIONS[3]}</h2>" + table(slos, ("slo_id","service_name","target","observed","compliant","recommendation")) +
                table(budgets, ("slo_id","consumed_fraction","remaining_fraction","burn_rate","exhausted","recommendation")),
            f"<h2>{self.SECTIONS[4]}</h2>" + table(alerts, ("alert_id","rule_id","service_name","severity","status","occurrence_count","summary")),
            f"<h2>{self.SECTIONS[5]}</h2>" + table(retention, ("telemetry_type","scanned","retained","deleted","archived","compliant","recommendation")),
        ]
        return """<!doctype html><html><head><meta charset="utf-8">
<title>Production Observability Report</title>
<style>body{font-family:Arial;margin:32px;color:#18212f}h2{margin-top:32px;border-bottom:1px solid #ccd4df}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}.card{border:1px solid #ccd4df;border-radius:8px;padding:12px;display:flex;flex-direction:column}
.card span{font-size:24px}table{border-collapse:collapse;width:100%;margin:12px 0}th,td{border:1px solid #d7dde5;padding:7px;text-align:left;font-size:13px}th{background:#f3f6f9}</style>
</head><body>""" + (
            f"<h1>Production Observability Report</h1>"
            f"<p>Generated: {datetime.now(timezone.utc).isoformat()}</p>"
            f"<p>Metadata: {escape(str(metadata or {}))}</p>"
            f"<div class='cards'>{cards}</div>{''.join(sections)}</body></html>"
        )

    def write(self, path, **kwargs):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.build(**kwargs), encoding="utf-8")
        return target
