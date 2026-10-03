"""申请路由：查询/更新/提交/状态迁移（仅经 ApplicationWorkflowService）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from intern_platform.db.session import get_db
from intern_platform.dependencies.auth import AuthUser, get_current_user
from intern_platform.dependencies.ledger import (
    LedgerRequestContext,
    get_ledger_context,
    require_idempotency_key,
)
from intern_platform.models.application import Application
from intern_platform.models.application_message import ApplicationMessage
from intern_platform.models.project import Project
from intern_platform.models.role import Role, UserRole
from intern_platform.models.user import User
from intern_platform.schemas.application import TransitionRequest, TransitionResponse
from intern_platform.schemas.business import ApplicationOut, ApplicationUpdate, RewardDecision
from intern_platform.services.message_service import MessageService
from intern_platform.services.application_presenters import application_to_out
from intern_platform.services.application_service import ApplicationService
from intern_platform.services.application_workflow import (
    ApplicationWorkflowService,
    OptimisticLockError,
    TransitionContext,
)
from intern_platform.services.message_codec import unpack_deliverable
from intern_platform.services.notification_service import NotificationService
from intern_platform.services.state_machine import IllegalTransitionError

router = APIRouter(prefix="/applications", tags=["applications"])


class CommunityFinalBody(BaseModel):
    note: str = Field(min_length=1, max_length=2000)
    attachment_url: str | None = None
    attachment_name: str | None = None
    report_url: str | None = None
    code_url: str | None = None


class MentorNoticeBody(BaseModel):
    mentor_id: int
    project_id: int
    note: str = Field(min_length=1, max_length=2000)


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


class RewardInboxItem(BaseModel):
    application_id: int
    project_title: str
    student_name: str | None = None
    body: str
    attachment_url: str | None = None
    attachment_name: str | None = None
    created_at: str | None = None
    decision: str = "pending"
    decision_note: str | None = None


class RewardInboxOut(BaseModel):
    years: list[int]
    items: list[RewardInboxItem]


@router.get("/rewards/inbox", response_model=RewardInboxOut)
def reward_inbox(
    year: int | None = Query(default=None, ge=2000, le=2100),
    q: str = "",
    status_filter: str = Query(default="pending", alias="status", pattern="^(all|pending|approved|rejected)$"),
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RewardInboxOut:
    """学生奖励申请只给所属社区管理员，组委会不接收。"""
    cids = auth.community_ids_for("community_admin")
    if not cids:
        raise HTTPException(status_code=403, detail="仅社区管理员可查看奖励申请")
    keyword = q.strip().lower()
    apps = db.execute(
        select(Application, Project, User)
        .join(Project, Project.id == Application.project_id)
        .join(User, User.id == Application.student_id)
        .where(Project.community_id.in_(cids))
    ).all()
    found: list[RewardInboxItem] = []
    years: set[int] = set()
    for app, project, student in apps:
        messages = db.scalars(
            select(ApplicationMessage)
            .where(ApplicationMessage.application_id == app.id)
            .order_by(ApplicationMessage.id.desc())
        ).all()
        for msg in messages:
            parsed = unpack_deliverable(msg.body)
            if parsed.get("kind") != "reward":
                continue
            created = getattr(msg, "created_at", None)
            created_year = created.year if created is not None else None
            if created_year:
                years.add(created_year)
            decision = str(parsed.get("decision") or "pending")
            item = RewardInboxItem(
                application_id=app.id,
                project_title=project.title,
                student_name=student.display_name,
                body=str(parsed.get("text") or ""),
                attachment_url=str(parsed.get("attachment_url") or "") or None,
                attachment_name=str(parsed.get("attachment_name") or "") or None,
                created_at=created.isoformat(sep=" ", timespec="minutes") if created else None,
                decision=decision,
                decision_note=str(parsed.get("decision_note") or "") or None,
            )
            if year is not None and created_year != year:
                break
            if status_filter != "all" and decision != status_filter:
                break
            hay = f"{item.student_name or ''} {item.project_title} {item.body}".lower()
            if keyword and keyword not in hay:
                break
            found.append(item)
            break
    found.sort(key=lambda row: row.created_at or "", reverse=True)
    return RewardInboxOut(years=sorted(years, reverse=True), items=found)


@router.post("/{application_id}/reward-decision")
def reward_decision(
    application_id: int,
    body: RewardDecision,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        MessageService(db).decide_reward(auth, application_id, body.decision, body.note)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


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


@router.post("/{application_id}/community-final", response_model=TransitionResponse)
def submit_community_final(
    application_id: int,
    body: CommunityFinalBody,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    ledger: LedgerRequestContext = Depends(get_ledger_context),
) -> TransitionResponse:
    """导师通过结项后，社区把材料说明交给组委会。"""
    key = require_idempotency_key(ledger.idempotency_key)
    app = ApplicationService(db).get(application_id)
    if app is None or app.project is None:
        raise HTTPException(status_code=404, detail="申请不存在")
    if not auth.has_community_role("community_admin", app.project.community_id):
        raise HTTPException(status_code=403, detail="仅本社区管理员可提交结项材料")
    if app.status != "community_final_review":
        raise HTTPException(status_code=409, detail="当前不在社区报送环节")
    lines = [body.note.strip()]
    if body.attachment_url:
        lines.append(f"交付件：{body.attachment_name or '材料'} {body.attachment_url}")
    if body.report_url:
        lines.append(f"设计文档：{body.report_url}")
    if body.code_url:
        lines.append(f"代码链接：{body.code_url}")
    comment = "\n".join(lines)
    ctx = TransitionContext(
        actor_id=auth.id,
        action="submit_community_final",
        actor_role="community_admin",
        comment=comment,
        request_id=ledger.request_id,
        correlation_id=ledger.request_id,
        idempotency_key=key,
        trace_id=ledger.trace_id,
        ip=ledger.ip,
        user_agent=ledger.user_agent,
    )
    workflow = ApplicationWorkflowService(db)
    from_status = app.status
    try:
        mid = workflow.transition_by_id(application_id, ctx, commit=False)
        # 社区报送后组委会直接接收并完成结项，不再单独终审一次
        result = workflow.transition(
            mid.application,
            TransitionContext(
                actor_id=auth.id,
                action="approve_committee_final",
                actor_role="community_admin",
                comment="社区报送后自动计入组委会结项名单",
                request_id=ledger.request_id,
                correlation_id=ledger.request_id,
                idempotency_key=f"{key}#auto_committee",
                trace_id=ledger.trace_id,
                ip=ledger.ip,
                user_agent=ledger.user_agent,
                expected_version=mid.application.version,
            ),
        )
    except IllegalTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OptimisticLockError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    title = app.project.title
    NotificationService(db).create(
        user_id=app.student_id,
        title="结项已完成",
        body=f"项目「{title}」社区已报送，组委会已自动接收，状态为已结项。",
        kind="review_progress",
        project_id=app.project_id,
        application_id=app.id,
    )
    committee_role = db.scalar(select(Role).where(Role.code == "committee"))
    if committee_role is not None:
        user_ids = db.scalars(
            select(UserRole.user_id).where(UserRole.role_id == committee_role.id)
        ).all()
        for uid in user_ids:
            NotificationService(db).create(
                user_id=uid,
                title="社区已报送结项，已自动接收",
                body=f"「{title}」申请 #{app.id} 已计入结项名单：{comment[:140]}",
                kind="community_final",
                project_id=app.project_id,
                application_id=app.id,
            )
    db.commit()
    return TransitionResponse(
        application_id=result.application.id,
        from_status=from_status,
        to_status=result.to_status,
        action=result.action,
        idempotent_replay=result.idempotent_replay,
        version=result.application.version,
    )


@router.post("/notices/mentor")
def notice_mentor(
    body: MentorNoticeBody,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    from intern_platform.models.project import Project

    project = db.get(Project, body.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not auth.has_community_role("community_admin", project.community_id):
        raise HTTPException(status_code=403, detail="仅本社区管理员可通知导师")
    if project.mentor_id != body.mentor_id:
        raise HTTPException(status_code=400, detail="该导师不是此项目负责人")
    NotificationService(db).create(
        user_id=body.mentor_id,
        title="社区重要通知",
        body=f"「{project.title}」{body.note[:180]}",
        kind="community_mentor",
        project_id=project.id,
        commit=True,
    )
    return {"ok": True}


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
