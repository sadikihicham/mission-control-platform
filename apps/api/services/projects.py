"""Projets : la vitrine d'orchestration (seed, hiérarchie tâche→sous-tâche) +
les projets réels en DB (CRUD). list/get fusionnent les deux.
"""
import re
import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from apps.api.models import ActivityLog, Agent, Project, ProjectStatus
from apps.api.schemas.agent import AgentOut
from apps.api.schemas.project import (
    ProjectCreate,
    ProjectDetail,
    ProjectSummary,
    ProjectUpdate,
    SubTask,
    Task,
)
from apps.api.services import agents_db
from apps.api.services.project_seed import PROJECTS

_SEED_IDS = {p["id"] for p in PROJECTS}


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "projet"


def _agents_by_key() -> dict[str, AgentOut]:
    return {a.agent: a for a in agents_db.list_agents()}


def _subtasks(seed_subs: list[str], agent: AgentOut | None) -> list[SubTask]:
    """Dérive l'état de chaque sous-tâche depuis tasks_done/total de l'agent.

    Sous-tâches < tasks_done → done(100%) ; la courante → working(~50%) si
    l'agent travaille ; les suivantes → idle(0%).
    """
    total = len(seed_subs)
    done = 0
    working_idx = -1
    if agent:
        done = min(agent.tasks_done or 0, total)
        if agent.state in ("working", "stale") and done < total:
            working_idx = done
        # Agent terminé → tout est done.
        if agent.state == "done":
            done = total
    out: list[SubTask] = []
    for i, title in enumerate(seed_subs):
        if i < done:
            out.append(SubTask(title=title, progress=100, state="done", agent=agent.agent if agent else None))
        elif i == working_idx:
            out.append(SubTask(title=title, progress=50, state="working", agent=agent.agent if agent else None))
        else:
            out.append(SubTask(title=title, progress=0, state="idle", agent=agent.agent if agent else None))
    return out


def _build_tasks(seed_tasks: list[dict], by_key: dict[str, AgentOut]) -> list[Task]:
    tasks: list[Task] = []
    for st in seed_tasks:
        agents = [by_key[k] for k in st.get("agents", []) if k in by_key]
        lead = agents[0] if agents else None
        tasks.append(
            Task(
                id=st["id"],
                title=st["title"],
                module=st.get("module"),
                progress=lead.progress if lead else 0,
                state=lead.state if lead else "idle",
                agents=agents,
                subtasks=_subtasks(st.get("subtasks", []), lead),
            )
        )
    return tasks


def _summary_fields(tasks: list[Task]) -> dict:
    agents = [a for t in tasks for a in t.agents]
    progress = round(sum(t.progress for t in tasks) / len(tasks)) if tasks else 0
    return {
        "progress": progress,
        "tasks_total": len(tasks),
        "tasks_done": sum(1 for t in tasks if t.state == "done"),
        "agents_total": len(agents),
        "agents_active": sum(1 for a in agents if a.state in ("working", "stale")),
        "agents_blocked": sum(1 for a in agents if a.state == "blocked"),
    }


# ---------- Projets DB (CRUD réel) ----------

def _linked_agents(db: Session, project_id: uuid.UUID) -> list[AgentOut]:
    rows = db.scalars(select(Agent).where(Agent.project_id == project_id)).all()
    return [agents_db._to_out(a) for a in rows]


def _db_counts(agents: list[AgentOut], stored_progress: int) -> dict:
    progress = round(sum(a.progress for a in agents) / len(agents)) if agents else stored_progress
    return {
        "progress": progress,
        "tasks_total": 0,
        "tasks_done": 0,
        "agents_total": len(agents),
        "agents_active": sum(1 for a in agents if a.state in ("working", "stale")),
        "agents_blocked": sum(1 for a in agents if a.state == "blocked"),
        "editable": True,
    }


def _db_summary(db: Session, p: Project) -> ProjectSummary:
    agents = _linked_agents(db, p.id)
    return ProjectSummary(
        id=str(p.id), name=p.name, description=p.description, repo=p.repo,
        status=p.status.value, **_db_counts(agents, p.progress or 0),
    )


def _db_detail(db: Session, p: Project) -> ProjectDetail:
    agents = _linked_agents(db, p.id)
    return ProjectDetail(
        id=str(p.id), name=p.name, description=p.description, status=p.status.value, repo=p.repo,
        tasks=[], agents=agents, **_db_counts(agents, p.progress or 0),
    )


# ---------- API service ----------

def list_projects(db: Session) -> list[ProjectSummary]:
    by_key = _agents_by_key()
    res: list[ProjectSummary] = []
    # 1) Vitrine d'orchestration (seed)
    for p in PROJECTS:
        tasks = _build_tasks(p["tasks"], by_key)
        res.append(
            ProjectSummary(
                id=p["id"], name=p["name"], description=p.get("description"),
                status=p.get("status", "in_dev"), editable=False, **_summary_fields(tasks),
            )
        )
    # 2) Projets DB (CRUD)
    for p in db.scalars(select(Project)).all():
        res.append(_db_summary(db, p))
    return res


def get_project(db: Session, project_id: str) -> ProjectDetail | None:
    # Seed (vitrine)
    seed = next((x for x in PROJECTS if x["id"] == project_id), None)
    if seed:
        by_key = _agents_by_key()
        tasks = _build_tasks(seed["tasks"], by_key)
        agents = [a for t in tasks for a in t.agents]
        return ProjectDetail(
            id=seed["id"], name=seed["name"], description=seed.get("description"),
            status=seed.get("status", "in_dev"), tasks=tasks, agents=agents,
            editable=False, **_summary_fields(tasks),
        )
    # DB
    p = _get_db_project(db, project_id)
    return _db_detail(db, p) if p else None


def _get_db_project(db: Session, project_id: str) -> Project | None:
    try:
        pid = uuid.UUID(project_id)
    except ValueError:
        return None
    return db.get(Project, pid)


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
    return _db_detail(db, p)


def update_project(db: Session, project_id: str, data: ProjectUpdate) -> ProjectDetail | None:
    p = _get_db_project(db, project_id)
    if not p:
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
    return _db_detail(db, p)


def delete_project(db: Session, project_id: str) -> bool:
    p = _get_db_project(db, project_id)
    if not p:
        return False
    # Détacher les FK avant suppression.
    db.execute(update(Agent).where(Agent.project_id == p.id).values(project_id=None))
    db.execute(update(ActivityLog).where(ActivityLog.project_id == p.id).values(project_id=None))
    db.delete(p)
    db.commit()
    return True
