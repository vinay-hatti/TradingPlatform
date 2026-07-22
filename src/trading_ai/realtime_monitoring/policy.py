from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class AlertRule:
    rule_id: str; source: str; field: str; operator: str; value: Any; severity: str; title: str

DEFAULT_RULES = (
    AlertRule("RISK_BLOCKED", "risk", "trading_control", "in", ["BLOCK_NEW_RISK","REDUCE_ONLY"], "CRITICAL", "Portfolio risk control active"),
    AlertRule("STALE_RISK", "risk", "stale", "eq", True, "WARNING", "Risk artifact is stale"),
    AlertRule("EXECUTION_BLOCKED", "execution", "blocked_orders", "gt", 0, "WARNING", "Execution orders blocked"),
    AlertRule("EXIT_URGENT", "exits", "urgent_count", "gt", 0, "CRITICAL", "Urgent exit instructions pending"),
)

def matches(rule: AlertRule, payload: dict[str, Any]) -> bool:
    current = payload.get(rule.field)
    if rule.operator == "eq": return current == rule.value
    if rule.operator == "gt":
        try: return float(current or 0) > float(rule.value)
        except (TypeError, ValueError): return False
    if rule.operator == "in": return current in rule.value
    return False
