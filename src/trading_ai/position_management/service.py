from __future__ import annotations
import hashlib, math
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from .policy import PositionManagementPolicy
from .profile import ExitInstruction, MonitoringWorkflowResult, PositionAssessment, utc_now_iso
from .serialization import read_json, write_json_atomic

def _parse_dt(value: str | None) -> datetime:
    if not value: return datetime.now(timezone.utc)
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

def _id(prefix: str, *parts: object) -> str:
    raw = "|".join(str(x) for x in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode()).hexdigest()[:16].upper()}"

def _positions(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list): return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict): return []
    for key in ("positions", "open_positions", "items", "records"):
        value = payload.get(key)
        if isinstance(value, list): return [x for x in value if isinstance(x, dict)]
    snap = payload.get("snapshot")
    return _positions(snap) if snap else []

def _marks(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list): return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("marks", "quotes", "positions", "items"):
            if isinstance(payload.get(key), list): return [x for x in payload[key] if isinstance(x, dict)]
    return []

def _risk_control(payload: Any) -> str:
    if not isinstance(payload, dict): return "UNKNOWN"
    return str(payload.get("trading_control") or payload.get("control") or payload.get("risk_status") or "UNKNOWN").upper()

class PositionMonitoringService:
    def __init__(self, policy: PositionManagementPolicy | None = None):
        self.policy = policy or PositionManagementPolicy(); self.policy.validate()

    def assess(self, registry: Any, marks: Any, risk_control: Any = None, now: datetime | None = None) -> list[PositionAssessment]:
        now = now or datetime.now(timezone.utc)
        mark_rows = _marks(marks)
        by_position = {str(x.get("position_id")): x for x in mark_rows if x.get("position_id")}
        by_symbol = {str(x.get("symbol", "")).upper(): x for x in mark_rows if x.get("symbol")}
        control = _risk_control(risk_control)
        results: list[PositionAssessment] = []
        for row in _positions(registry):
            status = str(row.get("status", "OPEN")).upper()
            if status not in {"OPEN", "ACTIVE", "PARTIALLY_FILLED", "FILLED"}: continue
            pid = str(row.get("position_id") or row.get("id") or "")
            symbol = str(row.get("symbol") or "").upper()
            mark = by_position.get(pid) or by_symbol.get(symbol) or {}
            entry = float(row.get("entry_price") or row.get("average_entry_price") or 0.0)
            current = float(mark.get("price") or mark.get("current_price") or row.get("current_price") or 0.0)
            qty = int(abs(float(row.get("quantity") or row.get("contracts") or 0)))
            opened = _parse_dt(row.get("opened_at") or row.get("created_at"))
            marked = _parse_dt(mark.get("marked_at") or mark.get("updated_at") or row.get("updated_at"))
            holding = max(0, (now - opened).days)
            age = max(0.0, (now - marked).total_seconds() / 60.0)
            pnl = (current - entry) * qty
            ret = ((current - entry) / entry) if entry > 0 else 0.0
            reasons: list[str] = []
            decision, urgency, recommended = "HOLD", "NORMAL", 0
            if current < self.policy.minimum_mark_price or age > self.policy.stale_mark_minutes:
                decision, urgency = "REVIEW", "HIGH"; reasons.append("STALE_OR_INVALID_MARK")
            elif control in {"BLOCK_NEW_RISK", "REDUCE_ONLY"}:
                decision, urgency, recommended = "REDUCE", "CRITICAL", max(1, math.ceil(qty * self.policy.partial_profit_fraction)); reasons.append(f"PORTFOLIO_RISK_{control}")
            elif ret <= self.policy.stop_loss_pct:
                decision, urgency, recommended = "CLOSE", "CRITICAL", qty; reasons.append("STOP_LOSS_TRIGGERED")
            elif ret >= self.policy.take_profit_pct:
                decision, urgency, recommended = "CLOSE", "HIGH", qty; reasons.append("TAKE_PROFIT_TRIGGERED")
            elif ret >= self.policy.partial_profit_pct and qty > 1:
                decision, urgency, recommended = "REDUCE", "MEDIUM", max(1, math.ceil(qty * self.policy.partial_profit_fraction)); reasons.append("PARTIAL_PROFIT_TRIGGERED")
            elif holding >= self.policy.max_holding_days:
                decision, urgency, recommended = "CLOSE", "MEDIUM", qty; reasons.append("MAX_HOLDING_PERIOD")
            else:
                reasons.append("WITHIN_POLICY_BOUNDS")
            aid = _id("M39-A", pid, current, decision, now.date().isoformat())
            results.append(PositionAssessment(aid, pid, str(row.get("portfolio_id") or "PRIMARY"), symbol,
                str(row.get("strategy_type") or row.get("strategy") or "UNKNOWN"), str(row.get("direction") or "UNKNOWN"), qty,
                entry, current, pnl, ret, holding, age, decision, urgency, tuple(reasons), recommended,
                metadata={"risk_control": control, "mark_source": mark.get("source", "")}))
        return results

    def build_instructions(self, assessments: Iterable[PositionAssessment]) -> list[ExitInstruction]:
        output: list[ExitInstruction] = []
        for a in assessments:
            if a.decision not in {"REDUCE", "CLOSE"}: continue
            action = "CLOSE_POSITION" if a.decision == "CLOSE" else "REDUCE_POSITION"
            status = "PENDING_RISK_GATE" if self.policy.require_risk_gate else ("APPROVED" if self.policy.allow_automatic_close else "PENDING_APPROVAL")
            offset = self.policy.limit_offset_pct
            limit = max(self.policy.minimum_mark_price, a.current_price * (1 - offset)) if self.policy.default_order_type == "LIMIT" else None
            output.append(ExitInstruction(_id("M39-X", a.assessment_id, action, a.recommended_quantity), a.assessment_id,
                a.position_id, a.portfolio_id, a.symbol, action, a.recommended_quantity,
                self.policy.default_order_type, round(limit, 4) if limit is not None else None, status, a.urgency, a.reasons,
                metadata={"source": "M39_POSITION_MONITORING", "execution_route": "M38"}))
        return output

    def run(self, registry_file: str, marks_file: str, output_dir: str, risk_control_file: str | None = None) -> MonitoringWorkflowResult:
        registry = read_json(registry_file); marks = read_json(marks_file)
        risk = read_json(risk_control_file, {}) if risk_control_file else {}
        assessments = self.assess(registry, marks, risk)
        instructions = self.build_instructions(assessments)
        out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
        assessment_file = write_json_atomic(out / "position_assessments.json", {"assessments": [x.to_dict() for x in assessments], "generated_at": utc_now_iso()})
        instruction_file = write_json_atomic(out / "exit_instructions.json", {"instructions": [x.to_dict() for x in instructions], "generated_at": utc_now_iso()})
        counts = {k: sum(1 for x in assessments if x.decision == k) for k in ("HOLD", "REDUCE", "CLOSE", "REVIEW")}
        stale = sum(1 for x in assessments if "STALE_OR_INVALID_MARK" in x.reasons)
        result = MonitoringWorkflowResult(_id("M39-RUN", registry_file, marks_file, utc_now_iso()), "COMPLETED", len(assessments),
            counts["HOLD"], counts["REDUCE"], counts["CLOSE"], counts["REVIEW"], stale,
            assessment_file, instruction_file, str(out / "milestone39_closure.html"))
        write_json_atomic(out / "workflow_result.json", result.to_dict())
        return result
