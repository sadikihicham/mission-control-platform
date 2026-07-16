"""Routes projets & tâches V1 (P8) — `/agent-control/v1/projects*` et `/tasks*`.

Lecture (`view`) et mutation (`manage_projects`) selon la matrice figée (§5,
`ROUTE_CAPABILITIES`), toujours bornées au tenant du `HostContext` (ADR-0003).
Les routes ne portent aucune logique métier : elles délèguent au service, qui
applique le bornage tenant et lève 404 (jamais 403) hors tenant.

Un seul routeur, préfixe `/agent-control/v1`, pour couvrir à la fois `/projects*`
et `/tasks/{id}*` (chemins hors de l'arbre `/projects`).
"""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from apps.api.agent_control.projects import service
from apps.api.agent_control.projects.schemas import (
    AcProjectCreate,
    AcProjectListOut,
    AcProjectOut,
    AcProjectUpdate,
    AcTaskAssign,
    AcTaskCreate,
    AcTaskListOut,
    AcTaskOut,
    AcTaskUpdate,
)
from apps.api.core.agent_control_deps import get_host_context
from apps.api.core.db import get_db
from apps.api.integrations.capabilities import Capability
from apps.api.integrations.envelopes import PageInfo
from apps.api.integrations.host_context import HostContext
from apps.api.integrations.permissions import require_capability

router = APIRouter(prefix="/agent-control/v1", tags=["agent-control-projects"])


# --- Projets ------------------------------------------------------------------


@router.get("/projects", response_model=AcProjectListOut)
def list_projects(
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> AcProjectListOut:
    require_capability(ctx, Capability.view)
    rows, next_cursor, has_more = service.list_projects(
        db, ctx, limit=limit, cursor=cursor, status=status
    )
    return AcProjectListOut(
        items=[AcProjectOut(**service.serialize_project(db, p)) for p in rows],
        page_info=PageInfo(next_cursor=next_cursor, limit=limit, has_more=has_more),
    )


@router.post("/projects", response_model=AcProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    body: AcProjectCreate,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> AcProjectOut:
    require_capability(ctx, Capability.manage_projects)
    project = service.create_project(db, ctx, body)
    return AcProjectOut(**service.serialize_project(db, project))


@router.get("/projects/{project_id}", response_model=AcProjectOut)
def get_project(
    project_id: str,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> AcProjectOut:
    require_capability(ctx, Capability.view)
    project = service.get_project(db, ctx, project_id)
    return AcProjectOut(**service.serialize_project(db, project))


@router.patch("/projects/{project_id}", response_model=AcProjectOut)
def update_project(
    project_id: str,
    body: AcProjectUpdate,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> AcProjectOut:
    require_capability(ctx, Capability.manage_projects)
    project = service.update_project(db, ctx, project_id, body)
    return AcProjectOut(**service.serialize_project(db, project))


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: str,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> None:
    require_capability(ctx, Capability.manage_projects)
    service.delete_project(db, ctx, project_id)


# --- Tâches d'un projet -------------------------------------------------------


@router.get("/projects/{project_id}/tasks", response_model=AcTaskListOut)
def list_project_tasks(
    project_id: str,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    status: str | None = Query(default=None),
    parent_id: str | None = Query(default=None),
) -> AcTaskListOut:
    require_capability(ctx, Capability.view)
    rows, next_cursor, has_more = service.list_tasks(
        db, ctx, project_id, limit=limit, cursor=cursor, status=status, parent_id=parent_id
    )
    return AcTaskListOut(
        items=[AcTaskOut(**service.serialize_task(t)) for t in rows],
        page_info=PageInfo(next_cursor=next_cursor, limit=limit, has_more=has_more),
    )


@router.post(
    "/projects/{project_id}/tasks",
    response_model=AcTaskOut,
    status_code=status.HTTP_201_CREATED,
)
def create_project_task(
    project_id: str,
    body: AcTaskCreate,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> AcTaskOut:
    require_capability(ctx, Capability.manage_projects)
    task = service.create_task(db, ctx, project_id, body)
    return AcTaskOut(**service.serialize_task(task))


# --- Tâche unitaire -----------------------------------------------------------


@router.get("/tasks/{task_id}", response_model=AcTaskOut)
def get_task(
    task_id: str,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> AcTaskOut:
    require_capability(ctx, Capability.view)
    return AcTaskOut(**service.serialize_task(service.get_task(db, ctx, task_id)))


@router.patch("/tasks/{task_id}", response_model=AcTaskOut)
def update_task(
    task_id: str,
    body: AcTaskUpdate,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> AcTaskOut:
    require_capability(ctx, Capability.manage_projects)
    return AcTaskOut(**service.serialize_task(service.update_task(db, ctx, task_id, body)))


@router.post("/tasks/{task_id}/assign", response_model=AcTaskOut)
def assign_task(
    task_id: str,
    body: AcTaskAssign,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> AcTaskOut:
    require_capability(ctx, Capability.manage_projects)
    return AcTaskOut(**service.serialize_task(service.assign_task(db, ctx, task_id, body)))
