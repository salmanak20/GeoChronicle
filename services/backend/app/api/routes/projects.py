from datetime import UTC, datetime
from math import ceil
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.routes.health import authorize
from app.db.session import get_session
from app.models import Project
from app.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectPatch,
    ProjectResponse,
    ProjectStats,
    ProjectStatus,
)

router = APIRouter(prefix="/projects", tags=["projects"], dependencies=[Depends(authorize)])


def _not_found(project_id: int) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"code": "project_not_found", "message": f"Project {project_id} was not found"},
    )


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={"code": "project_conflict", "message": "Project data conflicts with a database constraint"},
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail={"code": "database_unavailable", "message": "Project data could not be saved"},
        ) from exc


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_session)) -> Project:
    project = Project(**payload.model_dump(), status=ProjectStatus.DRAFT.value)
    db.add(project)
    _commit(db)
    db.refresh(project)
    return project


@router.get("", response_model=ProjectListResponse)
def list_projects(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    status: ProjectStatus | None = None,
    sort_by: Literal["created_at", "updated_at"] = "updated_at",
    sort_order: Literal["asc", "desc"] = "desc",
    db: Session = Depends(get_session),
) -> ProjectListResponse:
    query = select(Project)
    count_query = select(func.count(Project.id))
    if search and search.strip():
        term = f"%{search.strip()}%"
        predicate = or_(Project.name.ilike(term), Project.topic.ilike(term))
        query = query.where(predicate)
        count_query = count_query.where(predicate)
    if status is not None:
        query = query.where(Project.status == status.value)
        count_query = count_query.where(Project.status == status.value)
    total = db.scalar(count_query) or 0
    sort_column = Project.created_at if sort_by == "created_at" else Project.updated_at
    ordering = sort_column.asc() if sort_order == "asc" else sort_column.desc()
    items = db.scalars(
        query.order_by(ordering, Project.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return ProjectListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=ceil(total / page_size) if total else 0,
    )


@router.get("/stats", response_model=ProjectStats)
def project_stats(db: Session = Depends(get_session)) -> ProjectStats:
    counts = dict(
        db.execute(select(Project.status, func.count(Project.id)).group_by(Project.status)).all()
    )
    recent = db.scalars(select(Project).order_by(Project.updated_at.desc(), Project.id.desc()).limit(5)).all()
    return ProjectStats(
        total=sum(counts.values()),
        draft=counts.get(ProjectStatus.DRAFT.value, 0),
        in_progress=counts.get(ProjectStatus.IN_PROGRESS.value, 0),
        completed=counts.get(ProjectStatus.COMPLETED.value, 0),
        recently_updated=recent,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_session)) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise _not_found(project_id)
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: int, payload: ProjectPatch, db: Session = Depends(get_session)) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise _not_found(project_id)
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates and not updates["name"]:
        raise HTTPException(status_code=422, detail={"code": "invalid_name", "message": "Project name cannot be blank"})
    for field in ("aspect_ratio", "language", "visual_style"):
        if field in updates and updates[field] is None:
            raise HTTPException(status_code=422, detail={"code": "invalid_project_field", "message": f"{field} cannot be null"})
    if "status" in updates:
        if updates["status"] is None:
            raise HTTPException(status_code=422, detail={"code": "invalid_status", "message": "Status cannot be null"})
        updates["status"] = updates["status"].value
    for field, value in updates.items():
        setattr(project, field, value)
    project.updated_at = datetime.now(UTC)
    _commit(db)
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_session)) -> Response:
    project = db.get(Project, project_id)
    if project is None:
        raise _not_found(project_id)
    db.delete(project)
    _commit(db)
    return Response(status_code=204)
