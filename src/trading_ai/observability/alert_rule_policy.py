from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AlertRule:
    rule_id: str
    signal_type: str
    severity: str
    threshold: float
    comparison: str
    consecutive_breaches: int = 1
    cooldown_seconds: float = 300.0
    enabled: bool = True
    labels: dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if self.comparison not in {
            "GREATER_THAN",
            "GREATER_THAN_OR_EQUAL",
            "LESS_THAN",
            "LESS_THAN_OR_EQUAL",
            "EQUAL",
        }:
            raise ValueError("Unsupported comparison")
        if self.consecutive_breaches <= 0:
            raise ValueError(
                "consecutive_breaches must be positive"
            )
        if self.cooldown_seconds < 0:
            raise ValueError("cooldown_seconds cannot be negative")


@dataclass(frozen=True)
class AlertRulePolicy:
    deduplicate: bool = True
    suppress_during_cooldown: bool = True
    default_status: str = "OPEN"
