from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


PanelSize = Literal["small", "medium", "large", "full"]
PanelZone = Literal["left", "center", "right", "bottom", "floating"]


class WorkspacePanel(BaseModel):
    panel_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=120)
    view: str = Field(min_length=1, max_length=100)
    zone: PanelZone = "center"
    order: int = Field(default=0, ge=0)
    size: PanelSize = "medium"
    visible: bool = True
    collapsed: bool = False
    width: int | None = Field(default=None, ge=240, le=2400)
    height: int | None = Field(default=None, ge=160, le=1600)
    metadata: dict = Field(default_factory=dict)


class WorkspaceLayout(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=120)
    owner: str = Field(min_length=1, max_length=128)
    theme: Literal["dark", "light", "system"] = "dark"
    density: Literal["compact", "comfortable"] = "compact"
    active_view: str = "dashboard"
    panels: list[WorkspacePanel] = Field(default_factory=list)
    keyboard_shortcuts_enabled: bool = True
    command_palette_enabled: bool = True
    updated_at: datetime
    version: int = Field(default=1, ge=1)


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    owner: str = Field(min_length=1, max_length=128)
    template: Literal["trading", "research", "operations", "blank"] = "trading"


class WorkspaceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    theme: Literal["dark", "light", "system"] | None = None
    density: Literal["compact", "comfortable"] | None = None
    active_view: str | None = Field(default=None, min_length=1, max_length=100)
    panels: list[WorkspacePanel] | None = None
    keyboard_shortcuts_enabled: bool | None = None
    command_palette_enabled: bool | None = None
    expected_version: int = Field(ge=1)


class WorkspaceNotification(BaseModel):
    notification_id: str
    severity: Literal["INFO", "SUCCESS", "WARNING", "CRITICAL"]
    title: str
    message: str
    created_at: datetime
    acknowledged: bool = False


class NotificationCreateRequest(BaseModel):
    severity: Literal["INFO", "SUCCESS", "WARNING", "CRITICAL"] = "INFO"
    title: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=1000)


class CommandDefinition(BaseModel):
    command_id: str
    title: str
    description: str
    category: str
    shortcut: str | None = None
    target_view: str | None = None
    action: str
