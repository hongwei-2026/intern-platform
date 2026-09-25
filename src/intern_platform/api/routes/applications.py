"""申请路由：查询/更新/提交/状态迁移（仅经 ApplicationWorkflowService）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from intern_platform.db.session import get_db
from intern_platform.dependencies.auth import AuthUser, get_current_user
from intern_platform.dependencies.ledger import (
    LedgerRequestContext,
    get_ledger_context,
    require_idempotency_key,
)
from intern_platform.schemas.application import TransitionRequest, TransitionResponse
from intern_platform.schemas.business import ApplicationOut, ApplicationUpdate
from intern_platform.services.application_presenters import application_to_out
from intern_platform.services.application_service import ApplicationService
from intern_platform.services.application_workflow import (
    ApplicationWorkflowService,
    OptimisticLockError,
    TransitionContext,
)
from intern_platform.services.notification_service import NotificationService
from intern_platform.services.state_machine import IllegalTransitionError

router = APIRouter(prefix="/applications", tags=["applications"])


def _notify_party(*, user_id: int, title: str, body: str, kind: str, project_id: int | None, application_id: int, db: Session) -> None:
    NotificationService(db).create(
        user_id=user_id,
        title=title,
        body=body,
        kind=kind,
        project_id=project_id,
        application_id=application_id,
        commit=True,
    )


@router.get("/mine", response_model=list[ApplicationOut])
def my_applications(
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ApplicationOut]:
    rows = ApplicationService(db).list_mine(auth)
    return [application_to_out(r) for r in rows]


@router.get("/inbox", response_model=list[ApplicationOut])
def inbox_applications(
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ApplicationOut]:
    """导师 / 社区管理员 / 组委会的待审队列。"""
    if not auth.has_role("mentor", "community_admin", "committee"):
        raise HTTPException(status_code=403, detail="仅组织端角色可查看待审队列")
    rows = ApplicationService(db).list_inbox(auth)
    return [application_to_out(r) for r in rows]


@router.get("/{application_id}", response_model=ApplicationOut)
def get_application(
    application_id: int,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplicationOut:
    svc = ApplicationService(db)
    app = svc.get(application_id)
    if app is None:
        raise HTTPException(status_code=404, detail="申请不存在")
    if not svc.can_view(auth, app):
        raise HTTPException(status_code=403, detail="无权查看申请")
    return application_to_out(app)


@router.patch("/{application_id}", response_model=ApplicationOut)
def patch_application(
    application_id: int,
    body: ApplicationUpdate,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplicationOut:
    try:
        row = ApplicationService(db).update(auth, application_id, body)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return application_to_out(row)


@router.post("/{application_id}/submit", response_model=ApplicationOut)
def submit_application(
    application_id: int,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    ledger: LedgerRequestContext = Depends(get_ledger_context),
) -> ApplicationOut:
    key = require_idempotency_key(ledger.idempotency_key)
    try:
        row = ApplicationService(db).submit_for_review(auth, application_id, ledger, key)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IllegalTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return application_to_out(row)


@router.post("/{application_id}/start-progress", response_model=TransitionResponse)
def start_progress(
    application_id: int,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    ledger: LedgerRequestContext = Depends(get_ledger_context),
) -> TransitionResponse:
    """名额预留后即可 → in_progress（community_review / committee_review / selected）。"""
    key = require_idempotency_key(ledger.idempotency_key)
    svc = ApplicationService(db)
    app = svc.get(application_id)
    if app is None:
        raise HTTPException(status_code=404, detail="申请不存在")
    if app.student_id != auth.id and not auth.has_role("committee"):
        raise HTTPException(status_code=403, detail="无权启动实习进度")
    actor_role = "committee" if auth.has_role("committee") and app.student_id != auth.id else "student"
    ctx = TransitionContext(
        actor_id=auth.id,
        action="start_progress",
        actor_role=actor_role,
        request_id=ledger.request_id,
        correlation_id=ledger.request_id,
        idempotency_key=key,
        trace_id=ledger.trace_id,
        ip=ledger.ip,
        user_agent=ledger.user_agent,
    )
    try:
        result = ApplicationWorkflowService(db).transition_by_id(
            application_id, ctx, commit=True
        )
    except IllegalTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OptimisticLockError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return TransitionResponse(
        application_id=result.application.id,
        from_status=result.from_status,
        to_status=result.to_status,
        action=result.action,
        idempotent_replay=result.idempotent_replay,
        version=result.application.version,
    )


@router.post("/{application_id}/withdraw", response_model=TransitionResponse)
def withdraw_application(
    application_id: int,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    ledger: LedgerRequestContext = Depends(get_ledger_context),
) -> TransitionResponse:
    """学生放弃接取（录取后 / 开发中）。"""
    key = require_idempotency_key(ledger.idempotency_key)
    svc = ApplicationService(db)
    app = svc.get(application_id)
    if app is None:
        raise HTTPException(status_code=404, detail="申请不存在")
    if app.student_id != auth.id:
        raise HTTPException(status_code=403, detail="仅申请人可放弃任务")
    ctx = TransitionContext(
        actor_id=auth.id,
        action="withdraw",
        actor_role="student",
        comment="学生主动放弃接取",
        request_id=ledger.request_id,
        correlation_id=ledger.request_id,
        idempotency_key=key,
        trace_id=ledger.trace_id,
        ip=ledger.ip,
        user_agent=ledger.user_agent,
    )
    try:
        result = ApplicationWorkflowService(db).transition_by_id(
            application_id, ctx, commit=True
        )
    except IllegalTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OptimisticLockError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    project = result.application.project
    if project is not None and project.mentor_id:
        _notify_party(
            user_id=project.mentor_id,
            title="学生放弃了任务",
            body=f"「{project.title}」申请 #{result.application.id} 已放弃接取，名额已释放。",
            kind="app_withdraw",
            project_id=project.id,
            application_id=result.application.id,
            db=db,
        )
    return TransitionResponse(
        application_id=result.application.id,
        from_status=result.from_status,
        to_status=result.to_status,
        action=result.action,
        idempotent_replay=result.idempotent_replay,
        version=result.application.version,
    )


@router.post("/{application_id}/cancel-assignment", response_model=TransitionResponse)
def cancel_assignment(
    application_id: int,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    ledger: LedgerRequestContext = Depends(get_ledger_context),
) -> TransitionResponse:
    """导师取消学生接取（释放名额）。"""
    key = require_idempotency_key(ledger.idempotency_key)
    svc = ApplicationService(db)
    app = svc.get(application_id)
    if app is None:
        raise HTTPException(status_code=404, detail="申请不存在")
    project = app.project
    if project is None or project.mentor_id != auth.id:
        if not auth.has_role("committee"):
            raise HTTPException(status_code=403, detail="仅项目导师或组委会可取消接取")
    actor_role = "committee" if auth.has_role("committee") and (
        project is None or project.mentor_id != auth.id
    ) else "mentor"
    ctx = TransitionContext(
        actor_id=auth.id,
        action="cancel_assignment",
        actor_role=actor_role,
        comment="导师取消学生接取",
        request_id=ledger.request_id,
        correlation_id=ledger.request_id,
        idempotency_key=key,
        trace_id=ledger.trace_id,
        ip=ledger.ip,
        user_agent=ledger.user_agent,
    )
    try:
        result = ApplicationWorkflowService(db).transition_by_id(
            application_id, ctx, commit=True
        )
    except IllegalTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OptimisticLockError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    project = result.application.project
    _notify_party(
        user_id=result.application.student_id,
        title="导师取消了你的接取",
        body=f"「{project.title if project else '项目'}」申请 #{result.application.id} 已被取消接取。",
        kind="app_cancel",
        project_id=project.id if project else None,
        application_id=result.application.id,
        db=db,
    )
    return TransitionResponse(
        application_id=result.application.id,
        from_status=result.from_status,
        to_status=result.to_status,
        action=result.action,
        idempotent_replay=result.idempotent_replay,
        version=result.application.version,
    )


@router.post(
    "/{application_id}/transitions",
    response_model=TransitionResponse,
    status_code=status.HTTP_200_OK,
)
def transition_application(
    application_id: int,
    body: TransitionRequest,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    ledger: LedgerRequestContext = Depends(get_ledger_context),
) -> TransitionResponse:
    """唯一通用改状态入口（仍禁止路由直接赋值 status）。"""
    key = require_idempotency_key(body.idempotency_key or ledger.idempotency_key)
    # 角色以服务端鉴权为准，不信任客户端 actor_role
    actor_role = auth.primary_actor_role(
        "student", "mentor", "community_admin", "committee"
    )
    svc_app = ApplicationService(db)
    app = svc_app.get(application_id)
    if app is None:
        raise HTTPException(status_code=404, detail="申请不存在")
    if not svc_app.can_view(auth, app):
        raise HTTPException(status_code=403, detail="无权操作申请")

    ctx = TransitionContext(
        actor_id=auth.id,
        action=body.action,
        actor_role=actor_role,
        comment=body.comment,
        request_id=body.request_id or ledger.request_id,
        correlation_id=body.request_id or ledger.request_id,
        idempotency_key=key,
        trace_id=body.trace_id or ledger.trace_id,
        ip=ledger.ip,
        user_agent=ledger.user_agent,
        expected_version=body.version,
    )
    try:
        result = ApplicationWorkflowService(db).transition_by_id(
            application_id, ctx, commit=True
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IllegalTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OptimisticLockError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return TransitionResponse(
        application_id=result.application.id,
        from_status=result.from_status,
        to_status=result.to_status,
        action=result.action,
        idempotent_replay=result.idempotent_replay,
        version=result.application.version,
    )
