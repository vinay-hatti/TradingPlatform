from __future__ import annotations

from pathlib import Path
from typing import Any

from .profile import PortfolioRiskAssessment
from .serialization import read_json, write_json_atomic


class PortfolioRiskRepository:
    def __init__(self, history_file: Path, breach_file: Path, remediation_file: Path) -> None:
        self.history_file = history_file
        self.breach_file = breach_file
        self.remediation_file = remediation_file

    def persist(self, assessment: PortfolioRiskAssessment) -> dict[str, int]:
        history = read_json(self.history_file) or {"assessments": []}
        assessments = history.setdefault("assessments", [])
        if not any(item.get("assessment_id") == assessment.assessment_id for item in assessments):
            assessments.append(assessment.to_dict())
        write_json_atomic(self.history_file, history)

        breach_payload = read_json(self.breach_file) or {"breaches": []}
        breaches = breach_payload.setdefault("breaches", [])
        existing = {item.get("breach_id") for item in breaches}
        for breach in assessment.breaches:
            if breach.breach_id not in existing:
                breaches.append(breach.to_dict())
        write_json_atomic(self.breach_file, breach_payload)
        return {"assessment_count": len(assessments), "breach_count": len(breaches)}

    def resolve_breach(self, breach_id: str, resolution: str, resolved_at: str) -> dict[str, Any]:
        payload = read_json(self.breach_file) or {"breaches": []}
        target = None
        for item in payload.get("breaches", []):
            if item.get("breach_id") == breach_id:
                item["status"] = "RESOLVED"
                item["resolution"] = resolution
                item["resolved_at"] = resolved_at
                target = item
                break
        if target is None:
            raise KeyError(breach_id)
        write_json_atomic(self.breach_file, payload)
        remediation = read_json(self.remediation_file) or {"actions": []}
        remediation["actions"].append({"breach_id": breach_id, "resolution": resolution, "resolved_at": resolved_at})
        write_json_atomic(self.remediation_file, remediation)
        return target
