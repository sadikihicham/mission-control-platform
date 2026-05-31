"""Router projets — lecture (viewer) + CRUD DB (pm minimum)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.api.core.db import get_db
from apps.api.core.roles import Role
from apps.api.routers.auth import require_role
from apps.api.schemas.project import (
    ProjectCreate,
    ProjectDetail,
    ProjectSummary,
    ProjectUpdate,
)
from apps.api.services import projects as svc
from apps.api.services.git import fetch_git

# Lecture protégée : tout utilisateur authentifié (viewer minimum).
router = APIRouter(tags=["projects"], dependencies=[Depends(require_role(Role.viewer))])


@router.get("/projects", response_model=list[ProjectSummary])
def list_projects(db: Session = Depends(get_db)) -> list[ProjectSummary]:
    return svc.list_projects(db)


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def get_project(project_id: str, db: Session = Depends(get_db)) -> ProjectDetail:
    p = svc.get_project(db, project_id)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "projet introuvable")
    return p


@router.get("/projects/{project_id}/git")
def project_git(project_id: str, db: Session = Depends(get_db)) -> dict:
    """Infos GitHub du dépôt lié (commits/branches/PRs), ou {available:false}."""
    p = svc.get_project(db, project_id)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "projet introuvable")
    if not p.repo:
        return {"available": False, "repo": None}
    return fetch_git(p.repo)


@router.post(
    "/projects",
    response_model=ProjectDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.pm))],
)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)) -> ProjectDetail:
    return svc.create_project(db, body)


@router.patch(
    "/projects/{project_id}",
    response_model=ProjectDetail,
    dependencies=[Depends(require_role(Role.pm))],
)
def update_project(
    project_id: str, body: ProjectUpdate, db: Session = Depends(get_db)
) -> ProjectDetail:
    p = svc.update_project(db, project_id, body)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "projet DB introuvable (le seed n'est pas éditable)")
    return p


@router.delete(
    "/projects/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(Role.pm))],
)
def delete_project(project_id: str, db: Session = Depends(get_db)) -> None:
    if not svc.delete_project(db, project_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "projet DB introuvable")
