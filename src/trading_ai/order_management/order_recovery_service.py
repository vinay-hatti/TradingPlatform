from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

from .order_linkage_profile import OrderRecoveryCheckpoint


class OrderRecoveryService:
    def __init__(
        self,
        path: str | Path = "data/order_management/recovery_checkpoints.json",
    ) -> None:
        self.path = Path(path)

    def _load(self) -> dict[str, OrderRecoveryCheckpoint]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return {
            checkpoint_id: OrderRecoveryCheckpoint(**raw)
            for checkpoint_id, raw in payload.get("checkpoints", {}).items()
        }

    def _save(self, checkpoints: dict[str, OrderRecoveryCheckpoint]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "checkpoints": {
                        checkpoint_id: asdict(checkpoint)
                        for checkpoint_id, checkpoint in checkpoints.items()
                    }
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    def save(
        self,
        checkpoint: OrderRecoveryCheckpoint,
    ) -> OrderRecoveryCheckpoint:
        checkpoints = self._load()
        checkpoints[checkpoint.checkpoint_id] = checkpoint
        self._save(checkpoints)
        return checkpoint

    def get(
        self,
        checkpoint_id: str,
    ) -> OrderRecoveryCheckpoint | None:
        return self._load().get(checkpoint_id)

    def mark_completed(
        self,
        checkpoint_id: str,
        step: str,
    ) -> OrderRecoveryCheckpoint:
        checkpoints = self._load()
        current = checkpoints[checkpoint_id]
        completed = tuple(dict.fromkeys((*current.completed_steps, step)))
        pending = tuple(
            item for item in current.pending_steps
            if item != step
        )
        updated = replace(
            current,
            completed_steps=completed,
            pending_steps=pending,
            state="COMPLETED" if not pending else "IN_PROGRESS",
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        checkpoints[checkpoint_id] = updated
        self._save(checkpoints)
        return updated

    def mark_failed(
        self,
        checkpoint_id: str,
        error: str,
    ) -> OrderRecoveryCheckpoint:
        checkpoints = self._load()
        current = checkpoints[checkpoint_id]
        updated = replace(
            current,
            state="FAILED",
            retry_count=current.retry_count + 1,
            last_error=error,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        checkpoints[checkpoint_id] = updated
        self._save(checkpoints)
        return updated
