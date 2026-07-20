from fastapi import APIRouter, Depends, HTTPException, Query

from trading_ai.ui.models.workspace import (
    NotificationCreateRequest,
    WorkspaceCreateRequest,
    WorkspaceUpdateRequest,
)
from trading_ai.ui.services.workspace_service import (
    WorkspaceConflictError,
    WorkspaceService,
)

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


def service() -> WorkspaceService:
    return WorkspaceService()


@router.get("")
def list_workspaces(
    owner: str | None = Query(default=None),
    workspace_service: WorkspaceService = Depends(service),
):
    return workspace_service.list_workspaces(owner)


@router.post("")
def create_workspace(
    request: WorkspaceCreateRequest,
    workspace_service: WorkspaceService = Depends(service),
):
    return workspace_service.create_workspace(request)


@router.get("/commands")
def commands(workspace_service: WorkspaceService = Depends(service)):
    return workspace_service.commands()


@router.get("/notifications")
def notifications(workspace_service: WorkspaceService = Depends(service)):
    return workspace_service.list_notifications()


@router.post("/notifications")
def create_notification(
    request: NotificationCreateRequest,
    workspace_service: WorkspaceService = Depends(service),
):
    return workspace_service.create_notification(
        request.severity,
        request.title,
        request.message,
    )


@router.post("/notifications/{notification_id}/acknowledge")
def acknowledge_notification(
    notification_id: str,
    workspace_service: WorkspaceService = Depends(service),
):
    try:
        return workspace_service.acknowledge_notification(notification_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Notification not found")


@router.get("/{workspace_id}")
def get_workspace(
    workspace_id: str,
    workspace_service: WorkspaceService = Depends(service),
):
    try:
        return workspace_service.get_workspace(workspace_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Workspace not found")


@router.put("/{workspace_id}")
def update_workspace(
    workspace_id: str,
    request: WorkspaceUpdateRequest,
    workspace_service: WorkspaceService = Depends(service),
):
    try:
        return workspace_service.update_workspace(workspace_id, request)
    except KeyError:
        raise HTTPException(status_code=404, detail="Workspace not found")
    except WorkspaceConflictError as error:
        raise HTTPException(status_code=409, detail=str(error))


@router.delete("/{workspace_id}", status_code=204)
def delete_workspace(
    workspace_id: str,
    workspace_service: WorkspaceService = Depends(service),
):
    try:
        workspace_service.delete_workspace(workspace_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Workspace not found")
