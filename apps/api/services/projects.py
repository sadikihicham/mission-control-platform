"""Projets : source de vérité **DB** (plus aucune fixture Python à l'exécution).

La structure projet → tâche → sous-tâche est lue depuis les tables `projects` et
`tasks` (persistées par le seed, migration `0010`). Les TAUX et ÉTATS affichés
sont superposés en live depuis la flotte d'agents (`tasks.agent_key` → agent
réel). Le projet vitrine (`is_seed=True`) n'est pas éditable via l'API ; les
projets créés via l'API le sont (`editable=True`).
"""
import re
import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from apps.api.models import ActivityLog, Agent, Project, ProjectStatus, Task
from apps.api.schemas.agent import AgentOut
from apps.api.schemas.project import (
    ProjectCreate,
    ProjectDetail,
    ProjectSummary,
    ProjectUpdate,
    SubTask,
)
from apps.api.schemas.project import (
    Task as TaskDTO,
)
from apps.api.services import agents_db

# États d'agent considérés comme « actifs » pour les compteurs.
_ACTIVE_STATES = ("working", "stale")


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "projet"


def _agents_by_key() -> dict[str, AgentOut]:
    return {a.agent: a for a in agents_db.list_agents()}


# ---------- Superposition live : structure DB + état flotte ----------

def _subtasks(sub_titles: list[str], agent: AgentOut | None) -> list[SubTask]:
    """Dérive l'état de chaque sous-tâche depuis tasks_done/total de l'agent.

    Sous-tâches < tasks_done → done(100%) ; la courante → working(~50%) si
    l'agent travaille ; les suivantes → idle(0%). Sans agent live : tout idle.
    """
    total = len(sub_titles)
    done = 0
    working_idx = -1
    if agent:
        done = min(agent.tasks_done or 0, total)
        if agent.state in _ACTIVE_STATES and done < total:
            working_idx = done
        if agent.state == "done":
            done = total
    key = agent.agent if agent else None
    out: list[SubTask] = []
    for i, title in enumerate(sub_titles):
        if i < done:
            out.append(SubTask(title=title, progress=100, state="done", agent=key))
        elif i == working_idx:
            out.append(SubTask(title=title, progress=50, state="working", agent=key))
        else:
            out.append(SubTask(title=title, progress=0, state="idle", agent=key))
    return out


def _build_tasks(db: Session, project_id: uuid.UUID, by_key: dict[str, AgentOut]) -> list[TaskDTO]:
    """Construit les tâches (racines + sous-tâches) d'un projet depuis la DB."""
    roots = db.scalars(
        select(Task)
        .where(Task.project_id == project_id, Task.parent_id.is_(None))
        .order_by(Task.position, Task.created_at)
    ).all()
    tasks: list[TaskDTO] = []
    for row in roots:
        subs = db.scalars(
            select(Task).where(Task.parent_id == row.id).order_by(Task.position, Task.created_at)
        ).all()
        lead = by_key.get(row.agent_key) if row.agent_key else None
        agents = [lead] if lead else []
        tasks.append(
            TaskDTO(
                id=row.code or str(row.id),
                title=row.title,
                module=row.module,
                progress=lead.progress if lead else (row.progress or 0),
                state=lead.state if lead else "idle",
                agents=agents,
                subtasks=_subtasks([s.title for s in subs], lead),
            )
        )
    return tasks


def _counts_from_tasks(tasks: list[TaskDTO]) -> dict:
    agents = [a for t in tasks for a in t.agents]
    progress = round(sum(t.progress for t in tasks) / len(tasks)) if tasks else 0
    return {
        "progress": progress,
        "tasks_total": len(tasks),
        "tasks_done": sum(1 for t in tasks if t.state == "done"),
        "agents_total": len(agents),
        "agents_active": sum(1 for a in agents if a.state in _ACTIVE_STATES),
        "agents_blocked": sum(1 for a in agents if a.state == "blocked"),
    }


def _linked_agents(db: Session, project_id: uuid.UUID) -> list[AgentOut]:
    rows = db.scalars(select(Agent).where(Agent.project_id == project_id)).all()
    return [agents_db._to_out(a) for a in rows]


def _counts_from_agents(agents: list[AgentOut], stored_progress: int) -> dict:
    progress = round(sum(a.progress for a in agents) / len(agents)) if agents else stored_progress
    return {
        "progress": progress,
        "tasks_total": 0,
        "tasks_done": 0,
        "agents_total": len(agents),
        "agents_active": sum(1 for a in agents if a.state in _ACTIVE_STATES),
        "agents_blocked": sum(1 for a in agents if a.state == "blocked"),
    }


def _summary(db: Session, p: Project, by_key: dict[str, AgentOut]) -> ProjectSummary:
    tasks = _build_tasks(db, p.id, by_key)
    counts = _counts_from_tasks(tasks) if tasks else _counts_from_agents(
        _linked_agents(db, p.id), p.progress or 0
    )
    return ProjectSummary(
        id=str(p.id), name=p.name, description=p.description, repo=p.repo,
        status=p.status.value, editable=not p.is_seed, **counts,
    )


def _detail(db: Session, p: Project, by_key: dict[str, AgentOut]) -> ProjectDetail:
    tasks = _build_tasks(db, p.id, by_key)
    if tasks:
        counts = _counts_from_tasks(tasks)
        agents = [a for t in tasks for a in t.agents]
    else:
        agents = _linked_agents(db, p.id)
        counts = _counts_from_agents(agents, p.progress or 0)
    return ProjectDetail(
        id=str(p.id), name=p.name, description=p.description, status=p.status.value, repo=p.repo,
        tasks=tasks, agents=agents, editable=not p.is_seed, **counts,
    )


# ---------- Résolution / API service ----------

def _resolve_project(db: Session, project_id: str) -> Project | None:
    """Résout un projet par UUID (primaire) ou, à défaut, par slug (vitrine)."""
    try:
        pid = uuid.UUID(project_id)
    except ValueError:
        pass
    else:
        p = db.get(Project, pid)
        if p:
            return p
    return db.scalar(select(Project).where(Project.slug == project_id))


def list_projects(db: Session) -> list[ProjectSummary]:
    by_key = _agents_by_key()
    # Vitrine (is_seed) d'abord, puis projets CRUD par ancienneté.
    projects = db.scalars(
        select(Project).order_by(Project.is_seed.desc(), Project.created_at)
    ).all()
    return [_summary(db, p, by_key) for p in projects]


def get_project(db: Session, project_id: str) -> ProjectDetail | None:
    p = _resolve_project(db, project_id)
    if not p:
        return None
    return _detail(db, p, _agents_by_key())


def create_project(db: Session, data: ProjectCreate) -> ProjectDetail:
    status = ProjectStatus(data.status) if data.status else ProjectStatus.proposed
    base = data.slug or slugify(data.name)
    slug, n = base, 1
    while db.scalar(select(Project).where(Project.slug == slug)):
        n += 1
        slug = f"{base}-{n}"
    p = Project(slug=slug, name=data.name, description=data.description, status=status, repo=data.repo)
    db.add(p)
    db.commit()
    db.refresh(p)
    return _detail(db, p, _agents_by_key())


def update_project(db: Session, project_id: str, data: ProjectUpdate) -> ProjectDetail | None:
    p = _resolve_project(db, project_id)
    # Le projet vitrine (seed) n'est pas éditable : 404 côté router.
    if not p or p.is_seed:
        return None
    if data.name is not None:
        p.name = data.name
    if data.description is not None:
        p.description = data.description
    if data.status is not None:
        p.status = ProjectStatus(data.status)
    if data.progress is not None:
        p.progress = data.progress
    if data.repo is not None:
        p.repo = data.repo.strip() or None
    db.commit()
    db.refresh(p)
    return _detail(db, p, _agents_by_key())


def delete_project(db: Session, project_id: str) -> bool:
    p = _resolve_project(db, project_id)
    # Le projet vitrine (seed) n'est pas supprimable.
    if not p or p.is_seed:
        return False
    # Détacher les FK / purger les tâches avant suppression.
    db.execute(update(Agent).where(Agent.project_id == p.id).values(project_id=None))
    db.execute(update(ActivityLog).where(ActivityLog.project_id == p.id).values(project_id=None))
    db.execute(Task.__table__.delete().where(Task.project_id == p.id))
    db.delete(p)
    db.commit()
    return True
