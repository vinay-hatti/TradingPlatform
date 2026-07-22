from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from .artifacts import ArtifactDocument, ArtifactRepository
from .config import ProductionApiSettings
from .models import WorkflowRunResult


class ProductionApiService:
    WORKFLOWS = {
        "portfolio": "scripts/run_m36_phase2_portfolio_workflow.py",
        "risk": "scripts/run_m37_portfolio_risk_workflow.py",
        "execution": "scripts/run_m38_execution_orchestration.py",
        "positions": "scripts/run_m39_position_monitoring.py",
    }

    def __init__(self, settings: ProductionApiSettings):
        self.settings = settings
        self.artifacts = ArtifactRepository(settings.max_artifact_age_seconds)

    def artifact(self, relative_path: str | Path) -> ArtifactDocument:
        return self.artifacts.read_json(Path(relative_path))

    def platform_state(self) -> dict[str, ArtifactDocument]:
        root = self.settings.artifact_root
        return {
            "portfolio": self.artifact(self.settings.portfolio_registry_file),
            "risk": self.artifact(root / "m37/execution_risk_control.json"),
            "execution": self.artifact(root / "m38/execution_queue.json"),
            "positions": self.artifact(root / "m39/position_assessments.json"),
            "exit_instructions": self.artifact(root / "m39/exit_instructions.json"),
        }

    def readiness(self) -> tuple[bool, dict[str, Any]]:
        state = self.platform_state()
        required = ("portfolio", "risk")
        ready = all(state[name].exists for name in required)
        return ready, {
            name: {
                "exists": doc.exists,
                "stale": doc.stale,
                "path": str(doc.path),
                "age_seconds": doc.age_seconds,
            }
            for name, doc in state.items()
        }

    def run_workflow(self, workflow: str, arguments: list[str]) -> WorkflowRunResult:
        script = self.WORKFLOWS.get(workflow)
        if script is None:
            raise KeyError(workflow)
        command = [sys.executable, script, *arguments]
        completed = subprocess.run(command, text=True, capture_output=True, check=False, timeout=300)
        return WorkflowRunResult(
            workflow=workflow,
            accepted=completed.returncode == 0,
            exit_code=completed.returncode,
            stdout=completed.stdout[-20000:],
            stderr=completed.stderr[-20000:],
            command=command,
        )
