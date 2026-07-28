from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


class AutomationRunStateRepository:
    def __init__(self, state_path: str | Path) -> None:
        self.state_path = Path(state_path)

    def load(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"runs": {}}
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def existing_run_keys(self) -> tuple[str, ...]:
        return tuple((self.load().get("runs") or {}).keys())

    def save_run(self, run_key: str, payload: Mapping[str, Any]) -> None:
        state = self.load()
        runs = dict(state.get("runs") or {})
        runs[run_key] = dict(payload)
        state["runs"] = runs
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(state, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.state_path)
