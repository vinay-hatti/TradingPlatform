from __future__ import annotations

from pathlib import Path
from typing import Any

from .dashboard_workflow_profile import (
    DashboardWorkflowReport,
    DashboardWorkflowStage,
    utc_now_iso,
)


class DashboardWorkflowService:
    STAGES = (
        "MARKET_SCAN",
        "CANDIDATE_INSPECTION",
        "OPTION_CHAIN",
        "STRATEGY_COMPARISON",
        "INSTITUTIONAL_DECISION",
        "PAPER_TRADE_PREPARATION",
        "PAPER_TRADE_LIFECYCLE",
        "PERFORMANCE",
    )

    def build_report(
        self,
        artifacts: dict[str, tuple[Path, dict[str, Any] | None]],
    ) -> DashboardWorkflowReport:
        stages: list[DashboardWorkflowStage] = []
        warnings: list[str] = []
        symbol = ""
        direction = ""

        for stage_name in self.STAGES:
            path, payload = artifacts.get(
                stage_name,
                (Path(), None),
            )
            stage = self._build_stage(
                stage_name,
                path,
                payload,
            )
            stages.append(stage)

            if payload:
                symbol = symbol or str(
                    payload.get("symbol", "")
                ).upper()
                direction = direction or str(
                    payload.get("direction", "")
                ).upper()

        completed = sum(
            1 for stage in stages if stage.status == "COMPLETE"
        )
        failed = any(
            stage.status == "FAILED" for stage in stages
        )
        missing = any(
            stage.status == "MISSING" for stage in stages
        )

        if failed:
            workflow_status = "FAILED"
        elif missing:
            workflow_status = "INCOMPLETE"
        else:
            workflow_status = "COMPLETE"

        prep_payload = artifacts.get(
            "PAPER_TRADE_PREPARATION",
            (Path(), None),
        )[1] or {}
        lifecycle_payload = artifacts.get(
            "PAPER_TRADE_LIFECYCLE",
            (Path(), None),
        )[1] or {}
        performance_payload = artifacts.get(
            "PERFORMANCE",
            (Path(), None),
        )[1] or {}

        paper_trade_ready = bool(
            prep_payload.get("paper_trade_ready")
        )
        position = lifecycle_payload.get("position")
        position_open = (
            isinstance(position, dict)
            and str(
                position.get("status", "")
            ).upper()
            == "OPEN"
        )
        performance_available = isinstance(
            performance_payload.get("summary"),
            dict,
        )

        if workflow_status != "COMPLETE":
            warnings.append(
                "DASHBOARD_WORKFLOW_NOT_FULLY_COMPLETE"
            )
        if paper_trade_ready and not position_open:
            warnings.append(
                "PAPER_TRADE_READY_WITHOUT_OPEN_POSITION"
            )

        return DashboardWorkflowReport(
            generated_at=utc_now_iso(),
            symbol=symbol,
            direction=direction,
            workflow_status=workflow_status,
            completed_stages=completed,
            total_stages=len(self.STAGES),
            paper_trade_ready=paper_trade_ready,
            position_open=position_open,
            performance_available=performance_available,
            stages=tuple(stages),
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def _build_stage(
        self,
        stage_name: str,
        path: Path,
        payload: dict[str, Any] | None,
    ) -> DashboardWorkflowStage:
        if payload is None:
            return DashboardWorkflowStage(
                name=stage_name,
                status="MISSING",
                artifact_path=str(path) if str(path) else None,
                warnings=("ARTIFACT_NOT_FOUND",),
            )

        summary = self._summarize(stage_name, payload)
        status = self._status(stage_name, payload)
        warnings = tuple(
            payload.get("warnings", [])
            if isinstance(payload.get("warnings"), list)
            else ()
        )

        return DashboardWorkflowStage(
            name=stage_name,
            status=status,
            artifact_path=str(path),
            summary=summary,
            warnings=warnings,
        )

    def _status(
        self,
        stage_name: str,
        payload: dict[str, Any],
    ) -> str:
        if stage_name == "INSTITUTIONAL_DECISION":
            return (
                "COMPLETE"
                if str(
                    payload.get("decision", "")
                ).upper()
                in {"APPROVE", "REJECT"}
                else "FAILED"
            )

        if stage_name == "PAPER_TRADE_PREPARATION":
            return (
                "COMPLETE"
                if str(
                    payload.get("decision", "")
                ).upper()
                in {"READY", "REJECT"}
                else "FAILED"
            )

        if stage_name == "PAPER_TRADE_LIFECYCLE":
            order = payload.get("order")
            if not isinstance(order, dict):
                return "FAILED"
            return (
                "COMPLETE"
                if str(order.get("status", "")).upper()
                in {"SUBMITTED", "FILLED", "REJECTED"}
                else "FAILED"
            )

        if stage_name == "PERFORMANCE":
            return (
                "COMPLETE"
                if isinstance(payload.get("summary"), dict)
                else "FAILED"
            )

        return "COMPLETE" if payload else "FAILED"

    def _summarize(
        self,
        stage_name: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if stage_name == "STRATEGY_COMPARISON":
            return {
                "generated_strategies": payload.get(
                    "generated_strategies"
                ),
                "ranked_strategies": payload.get(
                    "ranked_strategies"
                ),
            }

        if stage_name == "INSTITUTIONAL_DECISION":
            return {
                "decision": payload.get("decision"),
                "selected_strategy_id": payload.get(
                    "selected_strategy_id"
                )
                or (
                    payload.get("selected_strategy", {})
                    .get("strategy_id")
                    if isinstance(
                        payload.get("selected_strategy"),
                        dict,
                    )
                    else None
                ),
                "paper_trade_ready": payload.get(
                    "paper_trade_ready"
                ),
            }

        if stage_name == "PAPER_TRADE_PREPARATION":
            return {
                "decision": payload.get("decision"),
                "paper_trade_ready": payload.get(
                    "paper_trade_ready"
                ),
                "refreshed_debit": payload.get(
                    "refreshed_debit"
                ),
                "reward_risk_ratio": payload.get(
                    "reward_risk_ratio"
                ),
            }

        if stage_name == "PAPER_TRADE_LIFECYCLE":
            order = payload.get("order", {})
            position = payload.get("position")
            return {
                "order_status": (
                    order.get("status")
                    if isinstance(order, dict)
                    else None
                ),
                "position_status": (
                    position.get("status")
                    if isinstance(position, dict)
                    else None
                ),
                "duplicate_submission": payload.get(
                    "duplicate_submission"
                ),
            }

        if stage_name == "PERFORMANCE":
            summary = payload.get("summary", {})
            return {
                "total_positions": summary.get(
                    "total_positions"
                ),
                "total_pnl": summary.get("total_pnl"),
                "win_rate": summary.get("win_rate"),
            }

        return {
            key: payload.get(key)
            for key in (
                "symbol",
                "direction",
                "status",
                "count",
            )
            if key in payload
        }
