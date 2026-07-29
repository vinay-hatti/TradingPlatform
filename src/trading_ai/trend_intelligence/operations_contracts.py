from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any

@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    message: str
    blocking: bool = False
    component: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

@dataclass
class OperationalAssessment:
    name: str
    status: str
    score: float
    snapshot_timestamp: str
    metrics: dict[str, Any] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "status": self.status, "score": round(float(self.score), 4),
            "snapshot_timestamp": self.snapshot_timestamp, "metrics": self.metrics,
            "findings": [asdict(x) for x in self.findings],
        }
