from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from trading_ai.ui.models.executive_reporting import (
    BoardReport,
    BoardSection,
    ExecutiveScorecard,
    KpiMetric,
    RegulatoryExportRecord,
    RegulatoryExportRequest,
)


class ExecutiveReportingService:
    def __init__(
        self,
        reports_root: str | Path = "reports",
        export_root: str | Path = "reports/exports",
    ):
        self.reports_root = Path(reports_root)
        self.export_root = Path(export_root)

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    @staticmethod
    def _num(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _json_files(self):
        return list(self.reports_root.rglob("*.json")) if self.reports_root.exists() else []

    def _jsonl_files(self):
        return list(self.reports_root.rglob("*.jsonl")) if self.reports_root.exists() else []

    def _load_json(self, path):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _portfolio_metrics(self):
        result = {"total_net_pnl": 0.0, "gross_exposure": 0.0, "net_exposure": 0.0}
        for path in self._json_files():
            name = path.name.lower()
            if "portfolio" not in name and "metrics" not in name and "summary" not in name:
                continue
            payload = self._load_json(path)
            if not isinstance(payload, dict):
                continue
            summary = payload.get("summary", payload)
            for key in result:
                if key in summary:
                    result[key] = self._num(summary.get(key))
        return result

    def _performance_metrics(self):
        values = {"win_rate": 0.0, "sharpe_ratio": 0.0, "max_drawdown": 0.0}
        candidates = []
        for path in self._json_files():
            if any(token in path.name.lower() for token in ("metrics", "walk", "backtest", "performance")):
                payload = self._load_json(path)
                if isinstance(payload, dict):
                    candidates.append(payload)
                elif isinstance(payload, list):
                    candidates.extend(x for x in payload if isinstance(x, dict))
        for item in candidates:
            rows = item.get("runs", [item]) if isinstance(item, dict) else []
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                for key in values:
                    if key in row:
                        values[key] = self._num(row[key])
        return values

    def _strategy_count(self):
        for path in self._json_files():
            if "strategy_studio_state" in path.name:
                payload = self._load_json(path)
                if isinstance(payload, dict):
                    promotions = payload.get("promotions", {})
                    deployments = payload.get("deployments", [])
                    return len(promotions) or len({
                        d.get("strategy_id") for d in deployments if isinstance(d, dict)
                    })
        return 0

    def _operations_counts(self):
        incidents = alerts = 0
        for path in self._json_files():
            if "operations_command_center_state" not in path.name:
                continue
            payload = self._load_json(path)
            if not isinstance(payload, dict):
                continue
            incidents = len([
                x for x in payload.get("incidents", [])
                if x.get("status") not in {"RESOLVED", "MITIGATED"}
            ])
            alerts = len([
                x for x in payload.get("alerts", [])
                if x.get("severity") == "CRITICAL" and not x.get("acknowledged", False)
            ])
        return incidents, alerts

    def _open_access_reviews(self):
        for path in self._json_files():
            if "security_compliance_state" in path.name:
                payload = self._load_json(path)
                if isinstance(payload, dict):
                    return len([
                        x for x in payload.get("access_reviews", [])
                        if x.get("status") == "OPEN"
                    ])
        return 0

    @staticmethod
    def _status(value, good=None, bad=None, higher_is_better=True):
        if good is None or bad is None:
            return "UNKNOWN"
        if higher_is_better:
            if value >= good:
                return "GOOD"
            if value <= bad:
                return "BAD"
        else:
            if value <= good:
                return "GOOD"
            if value >= bad:
                return "BAD"
        return "WATCH"

    def scorecard(self):
        portfolio = self._portfolio_metrics()
        performance = self._performance_metrics()
        incidents, alerts = self._operations_counts()
        reviews = self._open_access_reviews()
        strategies = self._strategy_count()

        kpis = [
            KpiMetric(
                metric_id="NET_PNL",
                label="Net P/L",
                value=portfolio["total_net_pnl"],
                unit="USD",
                status=self._status(portfolio["total_net_pnl"], 1, -1),
                source="portfolio summaries",
            ),
            KpiMetric(
                metric_id="WIN_RATE",
                label="Win Rate",
                value=performance["win_rate"],
                unit="ratio",
                status=self._status(performance["win_rate"], 0.55, 0.40),
                source="backtest/walk-forward metrics",
            ),
            KpiMetric(
                metric_id="SHARPE",
                label="Sharpe Ratio",
                value=performance["sharpe_ratio"],
                status=self._status(performance["sharpe_ratio"], 1.0, 0.25),
                source="backtest/walk-forward metrics",
            ),
            KpiMetric(
                metric_id="MAX_DRAWDOWN",
                label="Max Drawdown",
                value=performance["max_drawdown"],
                unit="ratio",
                status=self._status(abs(performance["max_drawdown"]), 0.10, 0.25, higher_is_better=False),
                source="backtest/walk-forward metrics",
            ),
            KpiMetric(
                metric_id="ACTIVE_INCIDENTS",
                label="Active Incidents",
                value=incidents,
                unit="count",
                status=self._status(incidents, 0, 3, higher_is_better=False),
                source="operations state",
            ),
            KpiMetric(
                metric_id="CRITICAL_ALERTS",
                label="Critical Alerts",
                value=alerts,
                unit="count",
                status=self._status(alerts, 0, 1, higher_is_better=False),
                source="operations state",
            ),
        ]
        warnings = []
        if not self.reports_root.exists():
            warnings.append("Reports directory does not exist.")
        if all(k.value == 0 for k in kpis[:4]):
            warnings.append("Performance artifacts were not found or contain zero values.")

        return ExecutiveScorecard(
            generated_at=self._now(),
            as_of_date=date.today(),
            total_net_pnl=portfolio["total_net_pnl"],
            gross_exposure=portfolio["gross_exposure"],
            net_exposure=portfolio["net_exposure"],
            win_rate=performance["win_rate"],
            sharpe_ratio=performance["sharpe_ratio"],
            max_drawdown=performance["max_drawdown"],
            active_strategies=strategies,
            active_incidents=incidents,
            critical_alerts=alerts,
            open_access_reviews=reviews,
            kpis=kpis,
            warnings=warnings,
        )

    def board_report(self):
        score = self.scorecard()
        performance_highlights = [
            f"Net P/L: {score.total_net_pnl:.2f}",
            f"Win rate: {score.win_rate:.2%}",
            f"Sharpe ratio: {score.sharpe_ratio:.2f}",
        ]
        risk_points = [
            f"Gross exposure: {score.gross_exposure:.2f}",
            f"Net exposure: {score.net_exposure:.2f}",
            f"Maximum drawdown: {score.max_drawdown:.2%}",
        ]
        operational_risks = []
        if score.active_incidents:
            operational_risks.append(f"{score.active_incidents} active incidents require review.")
        if score.critical_alerts:
            operational_risks.append(f"{score.critical_alerts} unacknowledged critical alerts.")
        if score.open_access_reviews:
            operational_risks.append(f"{score.open_access_reviews} open access reviews.")

        summary = (
            "Institutional trading platform executive report covering performance, "
            "risk, operations, governance, and compliance evidence. "
            "All metrics are derived from existing report artifacts and are read-only."
        )
        sources = [str(p) for p in self._json_files() + self._jsonl_files()]

        return BoardReport(
            generated_at=self._now(),
            title="Trading Platform Board & Executive Report",
            reporting_period=str(score.as_of_date),
            executive_summary=summary,
            sections=[
                BoardSection(
                    title="Performance",
                    summary="Consolidated strategy and portfolio performance.",
                    highlights=performance_highlights,
                    risks=[],
                ),
                BoardSection(
                    title="Risk",
                    summary="Exposure and downside-risk posture.",
                    highlights=[],
                    risks=risk_points,
                ),
                BoardSection(
                    title="Operations & Resilience",
                    summary="Operational health and incident posture.",
                    highlights=[f"{score.active_strategies} governed strategies recorded."],
                    risks=operational_risks,
                ),
                BoardSection(
                    title="Governance & Compliance",
                    summary="Security, access-review, release, and audit evidence.",
                    highlights=[
                        "Four-eye approvals are enforced for governed changes.",
                        "Secret values are excluded from reporting artifacts.",
                    ],
                    risks=[
                        f"{score.open_access_reviews} access reviews remain open."
                    ] if score.open_access_reviews else [],
                ),
            ],
            approvals=[],
            source_artifacts=sources,
        )

    def regulatory_export(self, request: RegulatoryExportRequest):
        self.export_root.mkdir(parents=True, exist_ok=True)
        export_id = f"export-{uuid4().hex[:16]}"
        output = self.export_root / f"{export_id}_{request.export_type.lower()}.json"

        records = []
        warnings = []
        if request.export_type == "RISK_SUMMARY":
            records = [self.scorecard().model_dump(mode="json")]
        elif request.export_type == "EXECUTION_ACTIVITY":
            for path in self._json_files():
                if any(token in path.name.lower() for token in ("execution", "order", "fill", "trade")):
                    payload = self._load_json(path)
                    if payload is not None:
                        records.append({"source": str(path), "payload": payload})
        elif request.export_type == "GOVERNANCE_AUDIT":
            for path in self._jsonl_files():
                if "audit" not in str(path).lower():
                    continue
                for line in path.read_text(encoding="utf-8").splitlines():
                    try:
                        records.append({"source": str(path), "payload": json.loads(line)})
                    except Exception:
                        warnings.append(f"Skipped invalid JSONL line in {path}.")
        elif request.export_type == "ACCESS_REVIEW":
            for path in self._json_files():
                if "security_compliance_state" in path.name:
                    payload = self._load_json(path) or {}
                    records.extend(payload.get("access_reviews", []))
        else:
            for path in self._json_files():
                payload = self._load_json(path)
                if payload is not None:
                    records.append({
                        "source": str(path) if request.include_source_paths else None,
                        "payload": payload,
                    })
            for path in self._jsonl_files():
                lines = []
                for line in path.read_text(encoding="utf-8").splitlines():
                    try:
                        lines.append(json.loads(line))
                    except Exception:
                        warnings.append(f"Skipped invalid JSONL line in {path}.")
                records.append({
                    "source": str(path) if request.include_source_paths else None,
                    "payload": lines,
                })

        payload = {
            "export_id": export_id,
            "export_type": request.export_type,
            "generated_at": self._now().isoformat(),
            "start_date": request.start_date.isoformat() if request.start_date else None,
            "end_date": request.end_date.isoformat() if request.end_date else None,
            "record_count": len(records),
            "records": records,
            "warnings": warnings,
        }
        serialized = json.dumps(payload, indent=2, sort_keys=True)
        output.write_text(serialized, encoding="utf-8")
        checksum = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return RegulatoryExportRecord(
            export_id=export_id,
            export_type=request.export_type,
            generated_at=self._now(),
            start_date=request.start_date,
            end_date=request.end_date,
            record_count=len(records),
            checksum=checksum,
            output_path=str(output),
            warnings=warnings,
        )
