"""项目路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from intern_platform.db.session import get_db
from intern_platform.dependencies.auth import (
    AuthUser,
    get_current_user,
    get_optional_user,
    require_roles,
)
from intern_platform.dependencies.ledger import LedgerRequestContext, get_ledger_context
from intern_platform.schemas.business import (
    ApplicationCreate,
    ApplicationOut,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    TaskDynamicsRow,
)
from intern_platform.services.application_service import ApplicationService
from intern_platform.services.project_presenters import project_to_out, projects_to_out
from intern_platform.services.project_service import ProjectService
from intern_platform.services.task_dynamics import list_task_dynamics

router = APIRouter(prefix="/projects", tags=["projects"])


def _owned_project_rows(auth: AuthUser, db: Session) -> list:
    svc = ProjectService(db)
    if auth.has_role("community_admin") or auth.has_role("committee"):
        cids = auth.community_ids_for("community_admin") if auth.has_role("community_admin") else []
        if auth.has_role("committee") and not cids:
            return svc.list_for_mentor(auth) if auth.has_role("mentor") else []
        seen: set[int] = set()
        rows = []
        for cid in cids:
            for p in svc.list_for_community(cid):
                if p.id not in seen:
                    seen.add(p.id)
                    rows.append(p)
        if auth.has_role("mentor"):
            for p in svc.list_for_mentor(auth):
                if p.id not in seen:
                    seen.add(p.id)
                    rows.append(p)
        return rows
    return svc.list_for_mentor(auth)


@router.get("", response_model=list[ProjectOut])
def list_projects(
    status: str | None = Query(default=None),
    community_id: int | None = None,
    owned: bool = Query(default=False, description="仅返回当前账号负责/管理的项目"),
    auth: AuthUser | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> list[ProjectOut]:
    if owned:
        if auth is None:
            raise HTTPException(status_code=401, detail="需要登录")
        if not auth.has_role("mentor", "community_admin", "committee"):
            raise HTTPException(status_code=403, detail="无权查看负责项目")
        rows = _owned_project_rows(auth, db)
        if status:
            rows = [r for r in rows if r.status == status]
        return projects_to_out(db, rows)

    effective_status = status if status is not None else "published"
    rows = ProjectService(db).list_projects(status=effective_status, community_id=community_id)
    if effective_status == "published":
        closed = ProjectService(db).list_projects(status="closed", community_id=community_id)
        rows = list(rows) + list(closed)
    return projects_to_out(db, rows)


@router.get("/mine", response_model=list[ProjectOut])
def list_my_projects(
    auth: AuthUser = Depends(require_roles("mentor", "community_admin", "committee")),
    db: Session = Depends(get_db),
) -> list[ProjectOut]:
    """兼容旧路径；推荐使用 GET /projects?owned=true。"""
    return projects_to_out(db, _owned_project_rows(auth, db))


@router.get("/{project_id:int}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)) -> ProjectOut:
    row = ProjectService(db).get(project_id)
    if row is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project_to_out(db, row)


@router.get("/{project_id:int}/task-dynamics", response_model=list[TaskDynamicsRow])
def get_project_task_dynamics(
    project_id: int,
    db: Session = Depends(get_db),
) -> list[TaskDynamicsRow]:
    """公开：任务动态表（脱敏昵称 + 进展/验收汇总）。"""
    try:
        return list_task_dynamics(db, project_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(
    body: ProjectCreate,
    auth: AuthUser = Depends(require_roles("community_admin", "committee")),
    db: Session = Depends(get_db),
) -> ProjectOut:
    try:
        row = ProjectService(db).create(auth, body)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return project_to_out(db, row)


@router.patch("/{project_id:int}", response_model=ProjectOut)
def update_project(
    project_id: int,
    body: ProjectUpdate,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectOut:
    try:
        row = ProjectService(db).update(auth, project_id, body)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return project_to_out(db, row)


@router.post("/{project_id:int}/publish", response_model=ProjectOut)
def publish_project(
    project_id: int,
    auth: AuthUser = Depends(require_roles("mentor", "community_admin", "committee")),
    db: Session = Depends(get_db),
    ledger: LedgerRequestContext = Depends(get_ledger_context),
) -> ProjectOut:
    try:
        row = ProjectService(db).publish(auth, project_id, ledger)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return project_to_out(db, row)


@router.post("/{project_id:int}/close", response_model=ProjectOut)
def close_project(
    project_id: int,
    auth: AuthUser = Depends(require_roles("mentor", "committee")),
    db: Session = Depends(get_db),
) -> ProjectOut:
    try:
        row = ProjectService(db).close(auth, project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return project_to_out(db, row)


@router.post("/{project_id:int}/applications", response_model=ApplicationOut, status_code=201)
def create_application(
    project_id: int,
    body: ApplicationCreate,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    ledger: LedgerRequestContext = Depends(get_ledger_context),
) -> ApplicationOut:
    from intern_platform.dependencies.ledger import require_idempotency_key

    key = None
    if body.submit:
        key = require_idempotency_key(ledger.idempotency_key)
    try:
        row = ApplicationService(db).create(auth, project_id, body, ledger, key)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    from intern_platform.services.application_presenters import application_to_out

    return application_to_out(ApplicationService(db).get(row.id) or row)


@router.get("/{project_id:int}/my-application", response_model=ApplicationOut | None)
def my_application_for_project(
    project_id: int,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplicationOut | None:
    from intern_platform.services.application_presenters import application_to_out

    row = ApplicationService(db).get_mine_for_project(auth, project_id)
    if row is None:
        return None
    return application_to_out(row)
