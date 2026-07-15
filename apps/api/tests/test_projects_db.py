"""Agent Control P2 — la structure projet/tâche/sous-tâche vient de la DB.

Ces tests prouvent que la vitrine d'orchestration est **persistée** (plus de
fixture Python lue à l'exécution) : projet marqué non éditable, tâches et
sous-tâches réelles en base, seed idempotent, et superposition live de l'état
via `agent_key`.
"""
from sqlalchemy import func, select

from apps.api.models import Project, Task
from apps.api.tests.conftest import auth

SHOWCASE_SLUG = "mission-control-platform"


def _showcase(projects: list[dict]) -> dict | None:
    return next((p for p in projects if p["name"].startswith("Project Mission Control")), None)


def test_showcase_project_is_persisted_and_not_editable(client, admin_token, db):
    # Persistée en DB (pas une fixture) et marquée is_seed.
    row = db.scalar(select(Project).where(Project.slug == SHOWCASE_SLUG))
    assert row is not None and row.is_seed is True

    projects = client.get("/projects", headers=auth(admin_token)).json()
    show = _showcase(projects)
    assert show is not None, "la vitrine doit être listée"
    assert show["editable"] is False
    assert show["tasks_total"] >= 8


def test_showcase_tasks_and_subtasks_persisted_in_db(db):
    project = db.scalar(select(Project).where(Project.slug == SHOWCASE_SLUG))
    roots = db.scalars(
        select(Task).where(Task.project_id == project.id, Task.parent_id.is_(None))
    ).all()
    subs = db.scalar(
        select(func.count()).select_from(Task).where(
            Task.project_id == project.id, Task.parent_id.is_not(None)
        )
    )
    assert len(roots) == 8, "8 tâches racines (M0..M6, M3.5)"
    assert subs >= 40, "les sous-tâches sont persistées comme lignes filles"
    # Chaque tâche racine porte un code stable et un module.
    assert all(r.code and r.module for r in roots)


def test_showcase_detail_exposes_tasks_with_subtasks(client, admin_token):
    detail = client.get(f"/projects/{SHOWCASE_SLUG}", headers=auth(admin_token)).json()
    assert detail["editable"] is False
    assert detail["tasks"], "le détail expose les tâches réelles"
    first = detail["tasks"][0]
    assert set(first) >= {"id", "title", "module", "progress", "state", "agents", "subtasks"}
    assert first["subtasks"], "les sous-tâches persistées sont exposées"


def test_showcase_resolvable_by_uuid_and_slug(client, admin_token, db):
    row = db.scalar(select(Project).where(Project.slug == SHOWCASE_SLUG))
    by_slug = client.get(f"/projects/{SHOWCASE_SLUG}", headers=auth(admin_token))
    by_uuid = client.get(f"/projects/{row.id}", headers=auth(admin_token))
    assert by_slug.status_code == 200 and by_uuid.status_code == 200
    assert by_slug.json()["tasks_total"] == by_uuid.json()["tasks_total"]


def test_showcase_not_editable_via_api(client, pm_token, db):
    row = db.scalar(select(Project).where(Project.slug == SHOWCASE_SLUG))
    # PATCH et DELETE refusés (404 : le seed n'est pas éditable).
    assert client.patch(
        f"/projects/{row.id}", headers=auth(pm_token), json={"status": "done"}
    ).status_code == 404
    assert client.delete(f"/projects/{row.id}", headers=auth(pm_token)).status_code == 404
    # Toujours présent après tentative de suppression.
    assert db.scalar(select(Project).where(Project.slug == SHOWCASE_SLUG)) is not None


def test_seed_showcase_is_idempotent(db):
    from apps.api.seed import _seed_showcase

    project = db.scalar(select(Project).where(Project.slug == SHOWCASE_SLUG))
    before = db.scalar(
        select(func.count()).select_from(Task).where(Task.project_id == project.id)
    )
    _seed_showcase(db)  # rejoué : ne doit rien dupliquer
    after = db.scalar(
        select(func.count()).select_from(Task).where(Task.project_id == project.id)
    )
    assert after == before


def test_live_state_overlaid_on_persisted_structure(client, admin_token, db):
    # La tâche racine M0 est portée par l'agent "socle" (agent_key persisté).
    m0 = db.scalar(
        select(Task).where(Task.code == "M0", Task.parent_id.is_(None))
    )
    assert m0 is not None and m0.agent_key == "socle"

    client.post(
        "/agents/heartbeat",
        headers={"X-MC-Token": "test-ingest"},
        json={
            "agent": "socle", "state": "working", "task": "Socle",
            "progress": 70, "tasks_done": 2, "tasks_total": 6,
        },
    )
    detail = client.get(f"/projects/{SHOWCASE_SLUG}", headers=auth(admin_token)).json()
    task = next(t for t in detail["tasks"] if t["id"] == "M0")
    # L'état/taux viennent de la flotte live, la structure de la DB.
    assert task["state"] == "working" and task["progress"] == 70
    assert task["subtasks"][0]["state"] == "done"  # 1re sous-tâche : tasks_done>=1
    assert any(a["agent"] == "socle" for a in task["agents"])
