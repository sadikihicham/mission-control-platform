"""Plan de contrôle des projets & tâches V1 (P8) — tenant-scoped, fail-closed.

Toute requête est bornée à `installation_id` du `HostContext` (résolu serveur,
ADR-0003) **dès la première ligne** : jamais de recherche par id seul. Un projet
ou une tâche d'un autre tenant est un 404 (pas de fuite d'existence, §11), jamais
un 403. Les tâches héritent du tenant de leur projet (cohérence garantie ici).

Les projets vitrine (`is_seed=True`) restent en **lecture seule** via l'API (même
invariant qu'en V0) : toute mutation est refusée par `state_conflict`, pour ne
jamais corrompre la fixture d'orchestration démonstrative.
"""
from __future__ import annotations

import base64
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import Select, func, select, tuple_
from sqlalchemy.orm import Session

from apps.api.agent_control.projects.schemas import (
    AcProjectCreate,
    AcProjectUpdate,
    AcTaskAssign,
    AcTaskCreate,
    AcTaskUpdate,
)
from apps.api.integrations.errors import Conflict, ResourceNotFound, StateConflict, ValidationFailed
from apps.api.integrations.host_context import HostContext
from apps.api.models import Agent, Project, ProjectStatus, Task

_PROJECT_STATUSES = frozenset(s.value for s in ProjectStatus)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _now() -> datetime:
    return datetime.now(UTC)


def _as_uuid(value) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def _scoped(ctx: HostContext) -> uuid.UUID | None:
    """UUID d'installation du contexte (tenant), pour borner toute requête."""
    return _as_uuid(ctx.installation.id)


def _encode_cursor(*parts) -> str:
    raw = "|".join(str(p) for p in parts)
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> list[str] | None:
    try:
        return base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
    except (ValueError, TypeError):
        return None


def _slugify(name: str) -> str:
    base = _SLUG_RE.sub("-", name.strip().lower()).strip("-")[:100] or "projet"
    return f"{base}-{uuid.uuid4().hex[:6]}"


# --- Sérialisation ------------------------------------------------------------


def serialize_project(db: Session, project: Project) -> dict:
    """Projette un `Project` ORM vers le DTO de contrat `AcProjectOut`."""
    task_count = db.scalar(
        select(func.count(Task.id)).where(Task.project_id == project.id)
    ) or 0
    status = project.status.value if hasattr(project.status, "value") else str(project.status)
    return {
        "id": str(project.id),
        "installation_id": str(project.installation_id) if project.installation_id else "",
        "slug": project.slug,
        "name": project.name,
        "description": project.description,
        "status": status,
        "progress": project.progress or 0,
        "repo": project.repo,
        "is_seed": bool(project.is_seed),
        "task_count": int(task_count),
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


def serialize_task(task: Task) -> dict:
    """Projette une `Task` ORM vers le DTO de contrat `AcTaskOut`."""
    return {
        "id": str(task.id),
        "installation_id": str(task.installation_id) if task.installation_id else "",
        "project_id": str(task.project_id),
        "parent_id": str(task.parent_id) if task.parent_id else None,
        "agent_id": str(task.agent_id) if task.agent_id else None,
        "code": task.code,
        "title": task.title,
        "module": task.module,
        "status": task.status,
        "progress": task.progress or 0,
        "position": task.position or 0,
        "agent_key": task.agent_key,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


# --- Lecture projets tenant-scoped --------------------------------------------


def list_projects(
    db: Session,
    ctx: HostContext,
    *,
    limit: int = 50,
    cursor: str | None = None,
    status: str | None = None,
) -> tuple[list[Project], str | None, bool]:
    """Liste paginée (curseur) des projets du tenant, récence décroissante."""
    limit = max(1, min(limit, 200))
    stmt: Select = select(Project).where(Project.installation_id == _scoped(ctx))
    if status:
        stmt = stmt.where(Project.status == status)
    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded and len(decoded) == 2:
            c_created, c_id = decoded
            cid = _as_uuid(c_id)
            if cid is not None:
                stmt = stmt.where(
                    tuple_(Project.created_at, Project.id)
                    < (datetime.fromisoformat(c_created), cid)
                )
    stmt = stmt.order_by(Project.created_at.desc(), Project.id.desc()).limit(limit + 1)
    rows = list(db.scalars(stmt).all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = _encode_cursor(last.created_at.isoformat(), last.id)
    return rows, next_cursor, has_more


def get_project(db: Session, ctx: HostContext, project_id: str) -> Project:
    """Charge un projet borné au tenant. 404 hors tenant/inexistant."""
    pid = _as_uuid(project_id)
    if pid is None:
        raise ResourceNotFound("projet introuvable", details={"project_id": project_id})
    project = db.scalar(
        select(Project).where(
            Project.id == pid, Project.installation_id == _scoped(ctx)
        )
    )
    if project is None:
        raise ResourceNotFound("projet introuvable", details={"project_id": project_id})
    return project


# --- Mutations projets (manage_projects) --------------------------------------


def _validate_status(status: str | None) -> None:
    if status is not None and status not in _PROJECT_STATUSES:
        raise ValidationFailed(
            "statut de projet invalide", details={"status": status}
        )


def _guard_editable(project: Project) -> None:
    """Refuse toute mutation d'un projet vitrine (invariant V0 préservé)."""
    if project.is_seed:
        raise StateConflict(
            "projet vitrine en lecture seule", details={"project_id": str(project.id)}
        )


def create_project(db: Session, ctx: HostContext, body: AcProjectCreate) -> Project:
    """Crée un projet dans le tenant courant. `installation_id` = contexte."""
    _validate_status(body.status)
    slug = (body.slug or "").strip() or _slugify(body.name)
    if db.scalar(select(Project.id).where(Project.slug == slug)) is not None:
        raise Conflict("slug de projet déjà utilisé", details={"slug": slug})
    project = Project(
        installation_id=_scoped(ctx),
        slug=slug,
        name=body.name.strip(),
        description=body.description,
        status=ProjectStatus(body.status) if body.status else ProjectStatus.in_dev,
        repo=body.repo,
        is_seed=False,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def update_project(
    db: Session, ctx: HostContext, project_id: str, body: AcProjectUpdate
) -> Project:
    project = get_project(db, ctx, project_id)
    _guard_editable(project)
    _validate_status(body.status)
    data = body.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        project.name = data["name"].strip()
    if "description" in data:
        project.description = data["description"]
    if "status" in data and data["status"] is not None:
        project.status = ProjectStatus(data["status"])
    if "progress" in data and data["progress"] is not None:
        project.progress = data["progress"]
    if "repo" in data:
        project.repo = data["repo"]
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, ctx: HostContext, project_id: str) -> None:
    project = get_project(db, ctx, project_id)
    _guard_editable(project)
    db.delete(project)
    db.commit()


# --- Lecture tâches tenant-scoped ---------------------------------------------


def list_tasks(
    db: Session,
    ctx: HostContext,
    project_id: str,
    *,
    limit: int = 50,
    cursor: str | None = None,
    status: str | None = None,
    parent_id: str | None = None,
) -> tuple[list[Task], str | None, bool]:
    """Liste paginée des tâches d'un projet du tenant. 404 si projet hors tenant."""
    project = get_project(db, ctx, project_id)  # borne tenant + 404
    limit = max(1, min(limit, 200))
    stmt: Select = select(Task).where(
        Task.project_id == project.id,
        Task.installation_id == _scoped(ctx),
    )
    if status:
        stmt = stmt.where(Task.status == status)
    pid = _as_uuid(parent_id)
    if parent_id is not None:
        # parent_id="" ou "root" non fourni ⇒ ignoré ; sinon filtre les sous-tâches.
        if pid is not None:
            stmt = stmt.where(Task.parent_id == pid)
    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded and len(decoded) == 2:
            c_created, c_id = decoded
            cid = _as_uuid(c_id)
            if cid is not None:
                stmt = stmt.where(
                    tuple_(Task.created_at, Task.id)
                    < (datetime.fromisoformat(c_created), cid)
                )
    stmt = stmt.order_by(Task.created_at.desc(), Task.id.desc()).limit(limit + 1)
    rows = list(db.scalars(stmt).all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = _encode_cursor(last.created_at.isoformat(), last.id)
    return rows, next_cursor, has_more


def get_task(db: Session, ctx: HostContext, task_id: str) -> Task:
    """Charge une tâche bornée au tenant. 404 hors tenant/inexistant."""
    tid = _as_uuid(task_id)
    if tid is None:
        raise ResourceNotFound("tâche introuvable", details={"task_id": task_id})
    task = db.scalar(
        select(Task).where(Task.id == tid, Task.installation_id == _scoped(ctx))
    )
    if task is None:
        raise ResourceNotFound("tâche introuvable", details={"task_id": task_id})
    return task


# --- Mutations tâches (manage_projects) ---------------------------------------


def _resolve_agent(db: Session, ctx: HostContext, *, agent_id, agent_key) -> Agent:
    """Charge un agent du tenant par id ou clé. 404 hors tenant/inexistant."""
    stmt = select(Agent).where(Agent.installation_id == _scoped(ctx))
    aid = _as_uuid(agent_id)
    if aid is not None:
        stmt = stmt.where(Agent.id == aid)
    elif agent_key:
        stmt = stmt.where(Agent.agent_key == agent_key)
    else:
        raise ValidationFailed("agent_id ou agent_key requis", details={})
    agent = db.scalar(stmt)
    if agent is None:
        raise ResourceNotFound(
            "agent introuvable",
            details={"agent_id": agent_id, "agent_key": agent_key},
        )
    return agent


def create_task(
    db: Session, ctx: HostContext, project_id: str, body: AcTaskCreate
) -> Task:
    """Crée une tâche/sous-tâche dans un projet du tenant. Hérite du tenant."""
    project = get_project(db, ctx, project_id)
    _guard_editable(project)
    parent_id = _as_uuid(body.parent_id)
    if body.parent_id is not None and parent_id is None:
        raise ValidationFailed("parent_id invalide", details={"parent_id": body.parent_id})
    if parent_id is not None:
        parent = db.scalar(
            select(Task).where(
                Task.id == parent_id,
                Task.project_id == project.id,
                Task.installation_id == _scoped(ctx),
            )
        )
        if parent is None:
            raise ResourceNotFound(
                "tâche parente introuvable", details={"parent_id": body.parent_id}
            )
        if parent.parent_id is not None:
            raise ValidationFailed(
                "hiérarchie limitée à un niveau (pas de sous-sous-tâche)",
                details={"parent_id": body.parent_id},
            )
    code = (body.code or "").strip() or None
    if code is not None and db.scalar(
        select(Task.id).where(Task.project_id == project.id, Task.code == code)
    ) is not None:
        raise Conflict("code de tâche déjà utilisé dans ce projet", details={"code": code})
    task = Task(
        project_id=project.id,
        installation_id=_scoped(ctx),
        parent_id=parent_id,
        code=code,
        title=body.title.strip(),
        module=body.module,
        status=(body.status or "todo"),
        position=body.position or 0,
        agent_key=body.agent_key,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task(
    db: Session, ctx: HostContext, task_id: str, body: AcTaskUpdate
) -> Task:
    task = get_task(db, ctx, task_id)
    data = body.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is not None:
        task.title = data["title"].strip()
    for field in ("module", "status", "progress", "position", "agent_key"):
        if field in data and data[field] is not None:
            setattr(task, field, data[field])
    db.commit()
    db.refresh(task)
    return task


def assign_task(
    db: Session, ctx: HostContext, task_id: str, body: AcTaskAssign
) -> Task:
    """Affecte un agent (du tenant) à une tâche. Renseigne `agent_id`+`agent_key`."""
    task = get_task(db, ctx, task_id)
    agent = _resolve_agent(db, ctx, agent_id=body.agent_id, agent_key=body.agent_key)
    task.agent_id = agent.id
    task.agent_key = agent.agent_key
    db.commit()
    db.refresh(task)
    return task
