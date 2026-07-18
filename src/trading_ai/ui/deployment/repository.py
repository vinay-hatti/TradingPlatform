from __future__ import annotations

import json
from pathlib import Path
from threading import RLock


class DeploymentRecoveryRepository:
    def __init__(
        self,
        state_path: Path | str = "reports/deployment/deployment_recovery_state.json",
    ):
        self.state_path = Path(state_path)
        self._lock = RLock()

    def load(self) -> dict:
        with self._lock:
            if not self.state_path.exists():
                return {
                    "packages": [],
                    "promotions": [],
                    "runtime_components": [],
                    "backups": [],
                }
            return json.loads(self.state_path.read_text(encoding="utf-8"))

    def save(self, payload: dict) -> None:
        with self._lock:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.state_path.with_suffix(".tmp")
            temp.write_text(
                json.dumps(payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            temp.replace(self.state_path)
