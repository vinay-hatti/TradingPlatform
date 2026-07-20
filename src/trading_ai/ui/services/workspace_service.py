from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4

from trading_ai.ui.models.workspace import (
    CommandDefinition,
    WorkspaceCreateRequest,
    WorkspaceLayout,
    WorkspaceNotification,
    WorkspacePanel,
    WorkspaceUpdateRequest,
)


class WorkspaceConflictError(RuntimeError):
    pass


class WorkspaceService:
    def __init__(
        self,
        state_path: str | Path = "reports/ui/workspaces.json",
        notification_path: str | Path = "reports/ui/workspace_notifications.json",
    ) -> None:
        self.state_path = Path(state_path)
        self.notification_path = Path(notification_path)
        self._lock = RLock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _read(path: Path, default):
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write(path: Path, payload) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temp.replace(path)

    def _templates(self, name: str) -> list[WorkspacePanel]:
        definitions = {
            "trading": [
                ("opportunities", "Opportunities", "opportunities", "left", "medium"),
                ("paper-order-entry", "Paper Order Entry", "paper-commands", "center", "large"),
                ("positions", "Positions & Risk", "portfolio-risk", "right", "medium"),
                ("execution", "Execution Blotter", "paper-execution", "bottom", "full"),
            ],
            "research": [
                ("symbol-intelligence", "Symbol Intelligence", "symbols", "left", "large"),
                ("opportunities", "Opportunity Scanner", "opportunities", "center", "large"),
                ("reporting", "Research & Audit", "reporting-audit", "bottom", "full"),
            ],
            "operations": [
                ("observability", "Observability", "observability", "center", "large"),
                ("runtime", "Runtime Administration", "admin-runtime", "right", "medium"),
                ("deployment", "Deployment & Recovery", "deployment-recovery", "bottom", "full"),
            ],
            "blank": [],
        }
        return [
            WorkspacePanel(
                panel_id=panel_id,
                title=title,
                view=view,
                zone=zone,
                order=index,
                size=size,
            )
            for index, (panel_id, title, view, zone, size) in enumerate(
                definitions[name]
            )
        ]

    def list_workspaces(self, owner: str | None = None) -> list[WorkspaceLayout]:
        with self._lock:
            records = self._read(self.state_path, [])
            workspaces = [WorkspaceLayout.model_validate(item) for item in records]
            if owner:
                workspaces = [item for item in workspaces if item.owner == owner]
            return sorted(workspaces, key=lambda item: item.updated_at, reverse=True)

    def get_workspace(self, workspace_id: str) -> WorkspaceLayout:
        workspace = next(
            (item for item in self.list_workspaces() if item.workspace_id == workspace_id),
            None,
        )
        if workspace is None:
            raise KeyError(workspace_id)
        return workspace

    def create_workspace(self, request: WorkspaceCreateRequest) -> WorkspaceLayout:
        with self._lock:
            workspace = WorkspaceLayout(
                workspace_id=f"ws-{uuid4().hex[:16]}",
                name=request.name,
                owner=request.owner,
                active_view="dashboard",
                panels=self._templates(request.template),
                updated_at=self._now(),
            )
            records = self._read(self.state_path, [])
            records.append(workspace.model_dump(mode="json"))
            self._write(self.state_path, records)
            return workspace

    def update_workspace(
        self,
        workspace_id: str,
        request: WorkspaceUpdateRequest,
    ) -> WorkspaceLayout:
        with self._lock:
            records = self._read(self.state_path, [])
            index = next(
                (i for i, item in enumerate(records) if item["workspace_id"] == workspace_id),
                None,
            )
            if index is None:
                raise KeyError(workspace_id)
            current = WorkspaceLayout.model_validate(records[index])
            if current.version != request.expected_version:
                raise WorkspaceConflictError(
                    f"Workspace version conflict: expected {request.expected_version}, "
                    f"current {current.version}"
                )
            changes = request.model_dump(exclude_none=True)
            changes.pop("expected_version", None)
            updated = current.model_copy(
                update={
                    **changes,
                    "version": current.version + 1,
                    "updated_at": self._now(),
                }
            )
            records[index] = updated.model_dump(mode="json")
            self._write(self.state_path, records)
            return updated

    def delete_workspace(self, workspace_id: str) -> None:
        with self._lock:
            records = self._read(self.state_path, [])
            filtered = [item for item in records if item["workspace_id"] != workspace_id]
            if len(filtered) == len(records):
                raise KeyError(workspace_id)
            self._write(self.state_path, filtered)

    def list_notifications(self) -> list[WorkspaceNotification]:
        return [
            WorkspaceNotification.model_validate(item)
            for item in self._read(self.notification_path, [])
        ]

    def create_notification(
        self,
        severity: str,
        title: str,
        message: str,
    ) -> WorkspaceNotification:
        with self._lock:
            notification = WorkspaceNotification(
                notification_id=f"note-{uuid4().hex[:16]}",
                severity=severity,
                title=title,
                message=message,
                created_at=self._now(),
            )
            records = self._read(self.notification_path, [])
            records.insert(0, notification.model_dump(mode="json"))
            self._write(self.notification_path, records[:500])
            return notification

    def acknowledge_notification(self, notification_id: str) -> WorkspaceNotification:
        with self._lock:
            records = self._read(self.notification_path, [])
            for index, item in enumerate(records):
                if item["notification_id"] == notification_id:
                    notification = WorkspaceNotification.model_validate(item).model_copy(
                        update={"acknowledged": True}
                    )
                    records[index] = notification.model_dump(mode="json")
                    self._write(self.notification_path, records)
                    return notification
            raise KeyError(notification_id)

    @staticmethod
    def commands() -> list[CommandDefinition]:
        return [
            CommandDefinition(command_id="view-dashboard", title="Open Dashboard", description="Open the main dashboard", category="Navigation", shortcut="G D", target_view="dashboard", action="navigate"),
            CommandDefinition(command_id="view-opportunities", title="Open Opportunities", description="Open opportunity discovery", category="Navigation", shortcut="G O", target_view="opportunities", action="navigate"),
            CommandDefinition(command_id="view-symbols", title="Open Symbol Intelligence", description="Open symbol analytics", category="Navigation", shortcut="G S", target_view="symbols", action="navigate"),
            CommandDefinition(command_id="view-risk", title="Open Portfolio & Risk", description="Open portfolio risk", category="Navigation", shortcut="G R", target_view="portfolio-risk", action="navigate"),
            CommandDefinition(command_id="view-paper-orders", title="Open Paper Order Entry", description="Open governed paper commands", category="Trading", shortcut="G T", target_view="paper-commands", action="navigate"),
            CommandDefinition(command_id="view-execution", title="Open Paper Execution", description="Open execution and reconciliation", category="Trading", shortcut="G E", target_view="paper-execution", action="navigate"),
            CommandDefinition(command_id="view-observability", title="Open Observability", description="Open health, metrics, logs, and alerts", category="Operations", shortcut="G H", target_view="observability", action="navigate"),
            CommandDefinition(command_id="workspace-save", title="Save Workspace", description="Persist the active workspace layout", category="Workspace", shortcut="⌘ S", action="save-workspace"),
            CommandDefinition(command_id="workspace-reset", title="Reset Workspace", description="Restore the current template layout", category="Workspace", action="reset-workspace"),
            CommandDefinition(command_id="theme-toggle", title="Toggle Theme", description="Switch light and dark themes", category="Appearance", shortcut="⌘ ⇧ T", action="toggle-theme"),
        ]
