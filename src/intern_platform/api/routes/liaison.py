"""按人对接：学生只收通知，导师和组委会可以来回回复。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from intern_platform.db.session import engine, get_db
from intern_platform.dependencies.auth import AuthUser, get_current_user
from intern_platform.models.application import Application
from intern_platform.models.application_message import ApplicationMessage
from intern_platform.models.community import Community
from intern_platform.models.cooperation_case import CooperationCase
from intern_platform.models.liaison_message import LiaisonMessage
from intern_platform.models.project import Project
from intern_platform.models.role import Role, UserRole
from intern_platform.models.user import User
from intern_platform.services.message_codec import pack_message
from intern_platform.services.notification_service import NotificationService

router = APIRouter(prefix="/liaison", tags=["liaison"])


def _ensure_table() -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS liaison_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    community_id INTEGER NOT NULL,
                    channel VARCHAR(16) NOT NULL,
                    peer_user_id INTEGER,
                    application_id INTEGER,
                    sender_id INTEGER NOT NULL,
                    body TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS cooperation_cases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    community_id INTEGER NOT NULL,
                    application_id INTEGER NOT NULL,
                    student_id INTEGER NOT NULL,
                    kind VARCHAR(16) NOT NULL,
                    status VARCHAR(16) NOT NULL,
                    reason_code VARCHAR(32),
                    reason TEXT NOT NULL DEFAULT '',
                    evidence TEXT,
                    decided_by INTEGER,
                    decision_note TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )


class LiaisonPost(BaseModel):
    community_id: int
    channel: str = Field(pattern="^(student|mentor|committee)$")
    peer_user_id: int | None = None
    application_id: int | None = None
    body: str = Field(min_length=1, max_length=12000)


def _plain(body: str) -> str:
    text = (body or "").strip()
    if text.startswith("{") and '"v"' in text:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict) and data.get("v") == 1:
            words = str(data.get("text") or "").strip()
            files = data.get("files") or []
            extra = f"（附 {len(files)} 份材料）" if files else ""
            return (words or "发来了材料") + extra
    return text


def _guard_community(auth: AuthUser, community_id: int) -> None:
    if auth.has_role("committee"):
        return
    if not auth.has_community_role("community_admin", community_id):
        raise HTTPException(status_code=403, detail="仅本社区管理员可对接")


@router.get("/committee")
def committee_threads(
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    _ensure_table()
    if not auth.has_role("committee"):
        raise HTTPException(status_code=403, detail="仅组委会可查看")
    rows = db.scalars(
        select(LiaisonMessage)
        .where(LiaisonMessage.channel == "committee", LiaisonMessage.peer_user_id.is_(None))
        .order_by(LiaisonMessage.id.desc())
    ).all()
    latest: dict[int, LiaisonMessage] = {}
    for row in rows:
        latest.setdefault(row.community_id, row)
    communities = db.scalars(select(Community).order_by(Community.name)).all()
    out = []
    for community in communities:
        if community.status == "rejected" and community.id not in latest:
            continue
        hit = latest.get(community.id)
        out.append(
            {
                "community_id": community.id,
                "community_name": community.name,
                "preview": _plain(hit.body) if hit else "还没有消息",
                "last_id": hit.id if hit else 0,
            }
        )
    out.sort(key=lambda item: (item["last_id"] == 0, -item["last_id"], item["community_name"]))
    return out


TAKEN_STATUSES = (
    "community_review",
    "committee_review",
    "selected",
    "in_progress",
    "final_submitted",
    "mentor_final_review",
    "community_final_review",
    "committee_final_review",
    "final_rejected",
    "completed",
)
REASON_LABEL = {
    "idle": "不做",
    "silent": "不回复",
    "messy": "乱做",
    "abuse": "辱骂",
    "other": "其他严重问题",
}


def _case_map(db: Session, community_id: int) -> dict[int, CooperationCase]:
    rows = db.scalars(
        select(CooperationCase)
        .where(CooperationCase.community_id == community_id)
        .order_by(CooperationCase.id.desc())
    ).all()
    latest: dict[int, CooperationCase] = {}
    for row in rows:
        latest.setdefault(row.application_id, row)
    return latest


@router.get("/people")
def people(
    community_id: int,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _ensure_table()
    _guard_community(auth, community_id)
    apps = db.scalars(
        select(Application)
        .join(Project, Project.id == Application.project_id)
        .where(
            Project.community_id == community_id,
            Application.status.in_(TAKEN_STATUSES),
        )
    ).all()
    cases = _case_map(db, community_id)
    students = []
    for app in apps:
        student = db.get(User, app.student_id)
        project = app.project or db.get(Project, app.project_id)
        if not student or not project:
            continue
        case = cases.get(app.id)
        ended = bool(case and (case.kind == "close" or case.status == "approved"))
        students.append(
            {
                "user_id": student.id,
                "name": student.display_name,
                "email": student.email,
                "project_id": project.id,
                "project_title": project.title,
                "application_id": app.id,
                "status": app.status,
                "ended": ended,
                "case_kind": case.kind if case else None,
                "case_status": case.status if case else None,
            }
        )
    role = db.scalar(select(Role).where(Role.code == "mentor"))
    mentor_ids = []
    if role:
        mentor_ids = list(
            db.scalars(
                select(UserRole.user_id).where(
                    UserRole.role_id == role.id,
                    UserRole.community_id == community_id,
                )
            ).all()
        )
    projects = db.scalars(select(Project).where(Project.community_id == community_id)).all()
    mentors = []
    for uid in mentor_ids:
        mentor = db.get(User, uid)
        if not mentor:
            continue
        titles = [p.title for p in projects if p.mentor_id == uid]
        mentors.append(
            {
                "user_id": mentor.id,
                "name": mentor.display_name,
                "email": mentor.email,
                "projects": titles,
            }
        )
    return {"students": students, "mentors": mentors}


@router.get("/thread")
def thread(
    community_id: int,
    channel: str,
    peer_user_id: int | None = None,
    application_id: int | None = None,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    _ensure_table()
    if not (
        auth.has_role("committee")
        or auth.has_community_role("community_admin", community_id)
        or (channel == "mentor" and peer_user_id == auth.id)
    ):
        raise HTTPException(status_code=403, detail="无权查看这段对话")
    stmt = select(LiaisonMessage).where(
        LiaisonMessage.community_id == community_id,
        LiaisonMessage.channel == channel,
    )
    if channel == "committee":
        stmt = stmt.where(LiaisonMessage.peer_user_id.is_(None))
    else:
        stmt = stmt.where(LiaisonMessage.peer_user_id == peer_user_id)
    if channel == "student" and application_id:
        stmt = stmt.where(LiaisonMessage.application_id == application_id)
    rows = db.scalars(stmt.order_by(LiaisonMessage.id.asc())).all()
    out = []
    for row in rows:
        sender = db.get(User, row.sender_id)
        out.append(
            {
                "id": row.id,
                "sender_id": row.sender_id,
                "sender_name": sender.display_name if sender else "用户",
                "body": row.body,
                "mine": row.sender_id == auth.id,
                "created_at": row.created_at,
            }
        )
    return out


@router.post("")
def post_message(
    body: LiaisonPost,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _ensure_table()
    replying = auth.has_role("committee") or (
        body.channel == "mentor" and body.peer_user_id == auth.id
    )
    if not replying:
        _guard_community(auth, body.community_id)
    if body.channel != "committee" and not body.peer_user_id:
        raise HTTPException(status_code=400, detail="请先选择具体的人")
    if body.channel == "student":
        app_check = db.get(Application, body.application_id) if body.application_id else None
        if app_check is None or app_check.status not in TAKEN_STATUSES:
            raise HTTPException(status_code=400, detail="这位学生还没有接取本组织的项目")
        case = _case_map(db, body.community_id).get(app_check.id)
        if case and (case.kind == "close" or case.status == "approved"):
            raise HTTPException(status_code=400, detail="与这位学生的对接已经结束")
    row = LiaisonMessage(
        community_id=body.community_id,
        channel=body.channel,
        peer_user_id=None if body.channel == "committee" else body.peer_user_id,
        application_id=body.application_id,
        sender_id=auth.id,
        body=body.body.strip(),
    )
    db.add(row)
    db.flush()
    ns = NotificationService(db)
    text = _plain(body.body)[:180]
    if body.channel == "student" and body.peer_user_id and body.application_id:
        community = db.get(Community, body.community_id)
        label = community.name if community else "社区"
        app = db.get(Application, body.application_id)
        db.add(
            ApplicationMessage(
                application_id=body.application_id,
                sender_id=auth.id,
                body=pack_message("official", json.dumps({"community": label, "text": text}, ensure_ascii=False)),
            )
        )
        ns.create(
            user_id=body.peer_user_id,
            title=f"{label}通知",
            body=text,
            kind="community_student",
            application_id=body.application_id,
        )
    elif body.channel == "mentor" and body.peer_user_id:
        target = body.peer_user_id if auth.id != body.peer_user_id else None
        admin_ids = []
        if target is None:
            role = db.scalar(select(Role).where(Role.code == "community_admin"))
            if role:
                admin_ids = list(
                    db.scalars(
                        select(UserRole.user_id).where(
                            UserRole.role_id == role.id,
                            UserRole.community_id == body.community_id,
                        )
                    ).all()
                )
        else:
            admin_ids = [target]
        for uid in admin_ids:
            if uid == auth.id:
                continue
            ns.create(
                user_id=uid,
                title="社区对接",
                body=text,
                kind="community_mentor",
            )
    elif body.channel == "committee":
        role = db.scalar(select(Role).where(Role.code == "committee"))
        admin = db.scalar(select(Role).where(Role.code == "community_admin"))
        targets: set[int] = set()
        if role:
            targets.update(db.scalars(select(UserRole.user_id).where(UserRole.role_id == role.id)).all())
        if admin:
            targets.update(
                db.scalars(
                    select(UserRole.user_id).where(
                        UserRole.role_id == admin.id,
                        UserRole.community_id == body.community_id,
                    )
                ).all()
            )
        for uid in targets:
            if uid == auth.id:
                continue
            ns.create(user_id=uid, title="社区对接", body=text, kind="community_committee")
    db.commit()
    return {"ok": True, "id": row.id}


class CloseBody(BaseModel):
    community_id: int
    application_id: int


class TerminateBody(BaseModel):
    community_id: int
    application_id: int
    reason_code: str = Field(pattern="^(idle|silent|messy|abuse|other)$")
    reason: str = Field(min_length=8, max_length=2000)
    evidence: str = Field(min_length=8, max_length=4000)


class DecideBody(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    note: str = Field(min_length=2, max_length=1000)


def _taken_app(db: Session, community_id: int, application_id: int) -> Application:
    app = db.get(Application, application_id)
    project = app.project if app else None
    if app is None or project is None or project.community_id != community_id:
        raise HTTPException(status_code=404, detail="找不到这位学生的项目")
    if app.status not in TAKEN_STATUSES:
        raise HTTPException(status_code=400, detail="这位学生还没有接取项目")
    return app


def _evidence_links(raw: str) -> str:
    lines = [part.strip() for part in raw.replace("，", "\n").replace(",", "\n").splitlines() if part.strip()]
    if not lines or any(not item.startswith(("http://", "https://")) for item in lines):
        raise HTTPException(status_code=400, detail="请附上可打开的图片或页面链接，一行一个")
    return "\n".join(lines)


@router.post("/close")
def close_liaison(
    body: CloseBody,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _ensure_table()
    _guard_community(auth, body.community_id)
    app = _taken_app(db, body.community_id, body.application_id)
    if app.status != "completed":
        raise HTTPException(status_code=400, detail="学生结项并得到结果后，才能结束对接")
    existing = _case_map(db, body.community_id).get(app.id)
    if existing and (existing.kind == "close" or existing.status == "approved"):
        raise HTTPException(status_code=400, detail="对接已经结束")
    db.add(
        CooperationCase(
            community_id=body.community_id,
            application_id=app.id,
            student_id=app.student_id,
            kind="close",
            status="closed",
            reason="结项完成后结束对接",
        )
    )
    community = db.get(Community, body.community_id)
    label = community.name if community else "社区"
    NotificationService(db).create(
        user_id=app.student_id,
        title=f"{label}已结束对接",
        body="结项已经完成，社区关闭了之后的正式通知。",
        kind="community_student",
        application_id=app.id,
    )
    db.commit()
    return {"ok": True}


@router.post("/terminate")
def request_terminate(
    body: TerminateBody,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _ensure_table()
    _guard_community(auth, body.community_id)
    app = _taken_app(db, body.community_id, body.application_id)
    if app.status == "completed":
        raise HTTPException(status_code=400, detail="已经结项的学生请使用结束对接")
    existing = _case_map(db, body.community_id).get(app.id)
    if existing and existing.kind == "terminate" and existing.status == "pending":
        raise HTTPException(status_code=400, detail="这份申请还在等组委会查证")
    if existing and existing.status == "approved":
        raise HTTPException(status_code=400, detail="合作已经终止")
    links = _evidence_links(body.evidence)
    community = db.get(Community, body.community_id)
    label = community.name if community else "社区"
    student = db.get(User, app.student_id)
    project = app.project
    db.add(
        CooperationCase(
            community_id=body.community_id,
            application_id=app.id,
            student_id=app.student_id,
            kind="terminate",
            status="pending",
            reason_code=body.reason_code,
            reason=body.reason.strip(),
            evidence=links,
        )
    )
    role = db.scalar(select(Role).where(Role.code == "committee"))
    if role:
        title = f"{label}申请终止合作"
        brief = f"{student.display_name if student else '学生'} · {project.title if project else ''} · {REASON_LABEL.get(body.reason_code, body.reason_code)}"
        for uid in db.scalars(select(UserRole.user_id).where(UserRole.role_id == role.id)).all():
            NotificationService(db).create(user_id=uid, title=title, body=brief, kind="community_committee")
    db.commit()
    return {"ok": True}


@router.get("/terminations")
def list_terminations(
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    _ensure_table()
    if not auth.has_role("committee"):
        raise HTTPException(status_code=403, detail="仅组委会可查看")
    rows = db.scalars(
        select(CooperationCase)
        .where(CooperationCase.kind == "terminate")
        .order_by(CooperationCase.id.desc())
    ).all()
    out = []
    for row in rows:
        student = db.get(User, row.student_id)
        community = db.get(Community, row.community_id)
        app = db.get(Application, row.application_id)
        project = app.project if app else None
        out.append(
            {
                "id": row.id,
                "community_name": community.name if community else "社区",
                "student_name": student.display_name if student else "学生",
                "project_title": project.title if project else "",
                "reason_code": row.reason_code,
                "reason_label": REASON_LABEL.get(row.reason_code or "", row.reason_code or ""),
                "reason": row.reason,
                "evidence": [line for line in (row.evidence or "").splitlines() if line],
                "status": row.status,
                "decision_note": row.decision_note,
            }
        )
    return out


@router.post("/terminations/{case_id}")
def decide_termination(
    case_id: int,
    body: DecideBody,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _ensure_table()
    if not auth.has_role("committee"):
        raise HTTPException(status_code=403, detail="仅组委会可以裁定")
    case = db.get(CooperationCase, case_id)
    if case is None or case.kind != "terminate" or case.status != "pending":
        raise HTTPException(status_code=404, detail="没有待查证的申请")
    case.decided_by = auth.id
    case.decision_note = body.note.strip()
    case.status = "approved" if body.decision == "approve" else "rejected"
    app = db.get(Application, case.application_id)
    community = db.get(Community, case.community_id)
    label = community.name if community else "社区"
    if body.decision == "approve" and app is not None and app.status != "withdrawn":
        from intern_platform.services.application_workflow import (
            ApplicationWorkflowService,
            IllegalTransitionError,
            TransitionContext,
        )

        try:
            ApplicationWorkflowService(db).transition_by_id(
                app.id,
                TransitionContext(
                    actor_id=auth.id,
                    action="cancel_assignment",
                    actor_role="committee",
                    comment=f"组委会核准终止合作：{body.note.strip()}",
                ),
                commit=False,
            )
        except (IllegalTransitionError, LookupError):
            app.status = "withdrawn"
    note = body.note.strip()
    if app is not None:
        title = f"{label}合作已终止" if body.decision == "approve" else f"{label}的终止申请未通过"
        detail = note if body.decision == "approve" else f"组委会未核准终止。{note}"
        NotificationService(db).create(
            user_id=app.student_id,
            title=title,
            body=detail,
            kind="community_student",
            application_id=app.id,
        )
    admin = db.scalar(select(Role).where(Role.code == "community_admin"))
    if admin:
        for uid in db.scalars(
            select(UserRole.user_id).where(
                UserRole.role_id == admin.id,
                UserRole.community_id == case.community_id,
            )
        ).all():
            NotificationService(db).create(
                user_id=uid,
                title="组委会已处理终止申请",
                body=note,
                kind="community_committee",
            )
    db.commit()
    return {"ok": True, "status": case.status}
