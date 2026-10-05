"""组委会站点内容、公示草稿和账号目录。内容存在集成配置里。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from intern_platform.db.session import engine, get_db
from intern_platform.dependencies.auth import AuthUser, get_current_user
from intern_platform.dependencies.ledger import LedgerRequestContext, get_ledger_context
from intern_platform.models.application import Application
from intern_platform.models.community import Community
from intern_platform.models.integration_setting import IntegrationSetting
from intern_platform.models.notification import Notification
from intern_platform.models.project import Project
from intern_platform.models.review_record import ReviewRecord
from intern_platform.models.role import Role, UserRole
from intern_platform.models.user import User
from intern_platform.repositories.audit_log import AuditLogRepository
from intern_platform.services.notification_service import NotificationService

router = APIRouter(tags=["committee-ops"])
public_router = APIRouter(prefix="/site", tags=["site"])


def _as_dt(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace(" ", "T"))

KEYS = {
    "slides": "site.slides",
    "news": "site.news",
    "guide": "site.guide",
    "queue": "publicity.queue",
}


def _ensure_disabled() -> None:
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(users)")).fetchall()
        names = {row[1] for row in rows}
        if "disabled" not in names:
            conn.execute(text("ALTER TABLE users ADD COLUMN disabled INTEGER NOT NULL DEFAULT 0"))


def _load(db: Session, key: str, fallback: Any) -> Any:
    row = db.get(IntegrationSetting, key)
    if row is None or not row.value:
        return fallback
    try:
        return json.loads(row.value)
    except json.JSONDecodeError:
        return fallback


def _save(db: Session, key: str, value: Any) -> None:
    row = db.get(IntegrationSetting, key)
    payload = json.dumps(value, ensure_ascii=False)
    if row is None:
        db.add(IntegrationSetting(key=key, value=payload))
    else:
        row.value = payload
    db.commit()


def _committee(auth: AuthUser) -> None:
    if not auth.has_role("committee"):
        raise HTTPException(status_code=403, detail="仅组委会可操作")


def _news_signature(item: dict) -> tuple:
    texts: list[str] = []
    for block in item.get("blocks") or []:
        if isinstance(block, dict) and block.get("type", "text") == "text":
            texts.append(str(block.get("text") or "").strip())
    return (
        str(item.get("title") or "").strip(),
        item.get("kind") or "news",
        (item.get("summary") or "").strip(),
        (item.get("body") or "").strip(),
        "\n".join(texts),
        bool(item.get("live", True)),
    )


def _news_excerpt(item: dict) -> str:
    texts: list[str] = []
    for block in item.get("blocks") or []:
        if isinstance(block, dict) and block.get("type", "text") == "text" and str(block.get("text") or "").strip():
            texts.append(str(block.get("text")).strip())
    raw = "\n".join(texts) or str(item.get("summary") or item.get("body") or "")
    return raw[:160]


def _notify_changed_news(db: Session, before: list[dict], after: list[dict]) -> None:
    old = {str(item.get("id") or ""): _news_signature(item) for item in before if isinstance(item, dict)}
    labels = {"news": "最新动态", "general": "公告", "selection": "中选公示", "final": "最新动态"}
    notes = NotificationService(db)
    sent = False
    for item in after:
        if not isinstance(item, dict) or not item.get("live", True):
            continue
        item_id = str(item.get("id") or "")
        title = str(item.get("title") or "").strip()
        if not item_id or not title or old.get(item_id) == _news_signature(item):
            continue
        label = labels.get(str(item.get("kind") or "news"), "最新动态")
        notes.notify_students(
            title=f"{label}：{title}",
            body=_news_excerpt(item) or "点开查看这条动态。",
            kind=f"site_news:{item_id}"[:64],
        )
        sent = True
    if sent:
        db.commit()


class SiteBody(BaseModel):
    items: list[dict] = Field(default_factory=list)
    books: list[dict] = Field(default_factory=list)


@public_router.get("/slides")
def public_slides(db: Session = Depends(get_db)) -> list[dict]:
    items = _load(db, KEYS["slides"], [])
    return [item for item in items if item.get("live", True)]


@public_router.get("/slides/{slide_id}")
def public_slide(slide_id: str, db: Session = Depends(get_db)) -> dict:
    items = _load(db, KEYS["slides"], [])
    hit = next((item for item in items if str(item.get("id")) == slide_id), None)
    if hit is None:
        raise HTTPException(status_code=404, detail="这张首页大图不存在")
    return hit


@public_router.get("/news")
def public_news(db: Session = Depends(get_db)) -> list[dict]:
    items = _load(db, KEYS["news"], [])
    return [item for item in items if item.get("live", True)]


@public_router.get("/guide")
def public_guide(db: Session = Depends(get_db)) -> dict:
    data = _load(db, KEYS["guide"], [])
    return {"books": data if isinstance(data, list) else []}


@router.get("/committee/community-applications")
def pending_community_applications(
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """待办：尚未准入的新社区申请。"""
    if not auth.has_role("committee"):
        raise HTTPException(status_code=403, detail="仅组委会可处理社区申请")
    rows = db.scalars(
        select(Community).where(Community.status == "pending").order_by(Community.id.desc())
    ).all()
    out: list[dict[str, Any]] = []
    for community in rows:
        applicant = db.get(User, community.applicant_user_id) if community.applicant_user_id else None
        created = getattr(community, "created_at", None)
        out.append(
            {
                "id": community.id,
                "name": community.name,
                "slug": community.slug,
                "description": community.description,
                "homepage_url": community.homepage_url,
                "applicant_name": applicant.display_name if applicant else None,
                "applicant_email": applicant.email if applicant else None,
                "created_at": created.isoformat(sep=" ", timespec="minutes") if created else None,
            }
        )
    return out


@router.get("/committee/completions")
def list_completions(
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """导师验收通过后进社区报送；社区报送后自动完成并计入名单，供组委会做公示。"""
    if not auth.has_role("committee"):
        raise HTTPException(status_code=403, detail="仅组委会可查看结项名单")
    rows = db.execute(
        select(Application, Project, Community, User)
        .join(Project, Project.id == Application.project_id)
        .join(Community, Community.id == Project.community_id)
        .join(User, User.id == Application.student_id)
        .where(
            Application.status.in_(
                ("community_final_review", "committee_final_review", "completed")
            )
        )
        .order_by(Application.id.desc())
    ).all()
    passed_at: dict[int, datetime] = {}
    for app_id, created in db.execute(
        select(ReviewRecord.application_id, ReviewRecord.created_at)
        .where(ReviewRecord.action == "approve_mentor_final")
        .order_by(ReviewRecord.id.desc())
    ).all():
        if created is not None and app_id not in passed_at:
            parsed = _as_dt(created)
            if parsed is not None:
                passed_at[app_id] = parsed
    months: set[str] = set()
    items: list[dict[str, Any]] = []
    for app, project, community, student in rows:
        finished = passed_at.get(app.id) or _as_dt(getattr(app, "updated_at", None))
        if finished is None:
            continue
        stamp = finished
        key = f"{stamp.year:04d}-{stamp.month:02d}"
        months.add(key)
        if key != month:
            continue
        items.append(
            {
                "application_id": app.id,
                "project_title": project.title,
                "community_name": community.name,
                "student_name": student.display_name,
                "finished_at": stamp.isoformat(sep=" ", timespec="minutes"),
            }
        )
    _backfill_roster_notices(db, rows, passed_at)
    return {"items": items, "months": sorted(months, reverse=True)}


def _backfill_roster_notices(db: Session, rows: list, passed_at: dict[int, datetime]) -> None:
    """已经结项、但当时还没通知组委会的申请，补一条站内消息。"""
    from intern_platform.services.message_service import committee_user_ids

    user_ids = committee_user_ids(db)
    if not user_ids or not rows:
        return
    created = False
    for app, project, _community, student in rows:
        exists = db.scalar(
            select(Notification.id).where(
                Notification.kind == "committee_roster",
                Notification.application_id == app.id,
            )
        )
        if exists:
            continue
        who = student.display_name or "学生"
        when = passed_at.get(app.id)
        when_text = when.strftime("%Y-%m-%d") if when else ""
        body = f"「{project.title}」{who} 已于 {when_text} 结项，直接计入结项名单。"
        for user_id in user_ids:
            NotificationService(db).create(
                user_id=user_id,
                title="有任务已结项",
                body=body,
                kind="committee_roster",
                project_id=project.id,
                application_id=app.id,
            )
        created = True
    if created:
        db.commit()


@router.get("/committee/content/{kind}")
def get_content(
    kind: str,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _committee(auth)
    if kind not in KEYS:
        raise HTTPException(status_code=404, detail="未知内容")
    data = _load(db, KEYS[kind], [])
    if kind == "guide":
        return {"books": data if isinstance(data, list) else []}
    return {"items": data if isinstance(data, list) else []}


@router.put("/committee/content/{kind}")
def put_content(
    kind: str,
    body: SiteBody,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _committee(auth)
    if kind not in ("slides", "news", "guide"):
        raise HTTPException(status_code=404, detail="未知内容")
    before = _load(db, KEYS[kind], []) if kind == "news" else []
    _save(db, KEYS[kind], body.books if kind == "guide" else body.items)
    if kind == "news":
        _notify_changed_news(db, before if isinstance(before, list) else [], body.items)
    return {"ok": True}


@router.get("/committee/publicity-queue")
def publicity_queue(
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    _committee(auth)
    data = _load(db, KEYS["queue"], [])
    return data if isinstance(data, list) else []


@router.put("/committee/publicity-queue")
def save_publicity_queue(
    body: SiteBody,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _committee(auth)
    _save(db, KEYS["queue"], body.items)
    return {"ok": True}


@router.get("/committee/directory/facets")
def directory_facets(
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    role: str = Query(default="student", pattern="^(student|mentor|org)$"),
) -> dict:
    """表头下拉用：各列已有的值。人数很多时姓名和邮箱只给出前 300 个，状态和所属给全量。"""
    _committee(auth)
    if role == "org":
        rows = db.scalars(select(Community).where(Community.status == "approved").order_by(Community.name.asc())).all()
        admin_role = db.scalar(select(Role).where(Role.code == "community_admin"))
        emails: list[str] = []
        if admin_role:
            emails = [
                item
                for item in db.scalars(
                    select(User.email)
                    .join(UserRole, UserRole.user_id == User.id)
                    .where(UserRole.role_id == admin_role.id, UserRole.community_id.is_not(None))
                    .distinct()
                    .order_by(User.email.asc())
                ).all()
                if item
            ]
        return {
            "names": [row.name for row in rows],
            "emails": emails,
            "orgs": [row.invite_code for row in rows if row.invite_code],
            "statuses": ["使用中", "已停用"],
        }
    role_code = "student" if role == "student" else "mentor"
    base = (
        select(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(Role.code == role_code)
    )
    names = db.scalars(
        base.with_only_columns(User.display_name).distinct().order_by(User.display_name.asc()).limit(300)
    ).all()
    emails = db.scalars(
        base.with_only_columns(User.email).distinct().order_by(User.email.asc()).limit(300)
    ).all()
    orgs = db.scalars(
        select(Community.name)
        .join(UserRole, UserRole.community_id == Community.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(Role.code == role_code)
        .distinct()
        .order_by(Community.name.asc())
    ).all()
    return {"names": [item for item in names if item], "emails": [item for item in emails if item], "orgs": list(orgs), "statuses": ["使用中", "已停用"]}


@router.get("/committee/directory")
def directory(
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    role: str = Query(default="student", pattern="^(student|mentor|org)$"),
    name: str = "",
    email: str = "",
    org: str = "",
    invite: str = "",
    status: str = "",
    q: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
) -> dict:
    _committee(auth)
    _ensure_disabled()
    name_q = name.strip()
    email_q = email.strip()
    org_q = org.strip()
    invite_q = invite.strip()
    keyword = q.strip()
    if role == "org":
        stmt = select(Community).where(Community.status == "approved")
        if name_q:
            stmt = stmt.where(Community.name == name_q)
        if invite_q:
            stmt = stmt.where(Community.invite_code == invite_q)
        if email_q:
            admin_role = db.scalar(select(Role).where(Role.code == "community_admin"))
            matched = select(UserRole.community_id).join(User, User.id == UserRole.user_id).where(
                UserRole.role_id == (admin_role.id if admin_role else -1),
                User.email == email_q,
            )
            stmt = stmt.where(Community.id.in_(matched))
        if keyword:
            admin_role = db.scalar(select(Role).where(Role.code == "community_admin"))
            mail_hit = select(UserRole.community_id).join(User, User.id == UserRole.user_id).where(
                UserRole.role_id == (admin_role.id if admin_role else -1),
                User.email.contains(keyword),
            )
            stmt = stmt.where(
                or_(
                    Community.name.contains(keyword),
                    Community.invite_code.contains(keyword),
                    Community.id.in_(mail_hit),
                )
            )
        admin_role = db.scalar(select(Role).where(Role.code == "community_admin"))
        if status in ("disabled", "active") and admin_role is not None:
            stopped = (
                select(UserRole.community_id)
                .join(User, User.id == UserRole.user_id)
                .where(UserRole.role_id == admin_role.id, text("users.disabled = 1"))
            )
            if status == "disabled":
                stmt = stmt.where(Community.id.in_(stopped))
            else:
                stmt = stmt.where(Community.id.notin_(stopped))
        total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
        rows = db.scalars(stmt.order_by(Community.id.asc()).offset((page - 1) * page_size).limit(page_size)).all()
        admin_role = db.scalar(select(Role).where(Role.code == "community_admin"))
        items = []
        for community in rows:
            admin_email = ""
            admin = None
            if admin_role:
                uid = db.scalar(
                    select(UserRole.user_id).where(
                        UserRole.role_id == admin_role.id,
                        UserRole.community_id == community.id,
                    )
                )
                admin = db.get(User, uid) if uid else None
                if admin and admin.display_name:
                    admin_email = f"{admin.display_name} · {admin.email}"
                else:
                    admin_email = admin.email if admin else ""
            flag = 0
            if admin is not None:
                try:
                    raw = db.execute(
                        text("SELECT disabled FROM users WHERE id = :id"),
                        {"id": admin.id},
                    ).scalar()
                    flag = int(raw or 0)
                except Exception:
                    db.rollback()
                    flag = 0
            items.append(
                {
                    "id": community.id,
                    "name": community.name,
                    "email": admin_email,
                    "school": community.slug,
                    "disabled": flag,
                    "orgs": [community.invite_code or ""],
                }
            )
        return {"total": total, "page": page, "page_size": page_size, "rows": items}

    role_code = "student" if role == "student" else "mentor"
    stmt = (
        select(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(Role.code == role_code)
    )
    if name_q:
        stmt = stmt.where(User.display_name == name_q)
    if email_q:
        stmt = stmt.where(User.email == email_q)
    if org_q:
        stmt = stmt.join(Community, Community.id == UserRole.community_id).where(Community.name == org_q)
    if status == "disabled":
        stmt = stmt.where(text("users.disabled = 1"))
    elif status == "active":
        stmt = stmt.where(text("(users.disabled = 0 OR users.disabled IS NULL)"))
    if keyword:
        stmt = stmt.where(or_(User.display_name.contains(keyword), User.email.contains(keyword)))
    distinct_ids = stmt.with_only_columns(User.id).distinct().subquery()
    total = int(db.scalar(select(func.count()).select_from(distinct_ids)) or 0)
    users = db.scalars(
        select(User)
        .where(User.id.in_(select(distinct_ids.c.id)))
        .order_by(User.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    disabled = {}
    if users:
        flags = db.execute(
            text("SELECT id, disabled FROM users WHERE id IN (%s)" % ",".join(str(int(u.id)) for u in users))
        ).all()
        disabled = {int(row[0]): int(row[1] or 0) for row in flags}
    items = []
    for user in users:
        names = db.scalars(
            select(Community.name)
            .join(UserRole, UserRole.community_id == Community.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id == user.id, Role.code == role_code)
        ).all()
        items.append(
            {
                "id": user.id,
                "name": user.display_name,
                "email": user.email,
                "school": user.school,
                "disabled": disabled.get(user.id, 0),
                "orgs": list(names),
            }
        )
    return {"total": total, "page": page, "page_size": page_size, "rows": items}


class DisableBody(BaseModel):
    disabled: bool


@router.post("/committee/users/{user_id}/disabled")
def set_disabled(
    user_id: int,
    body: DisableBody,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    ledger: LedgerRequestContext = Depends(get_ledger_context),
) -> dict:
    _committee(auth)
    _ensure_disabled()
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == auth.id:
        raise HTTPException(status_code=400, detail="不能停用自己")
    before_flag = db.execute(
        text("SELECT disabled FROM users WHERE id = :id"),
        {"id": user_id},
    ).scalar()
    db.execute(
        text("UPDATE users SET disabled = :flag WHERE id = :id"),
        {"flag": 1 if body.disabled else 0, "id": user_id},
    )
    AuditLogRepository(db).create(
        actor_id=auth.id,
        actor_role="committee",
        action="user.set_disabled",
        resource_type="user",
        resource_id=user_id,
        before={"disabled": int(before_flag or 0)},
        after={"disabled": 1 if body.disabled else 0, "email": user.email},
        outcome="SUCCESS",
        request_id=ledger.request_id,
        trace_id=ledger.trace_id,
        ip=ledger.ip,
        user_agent=ledger.user_agent,
    )
    db.commit()
    return {"ok": True}


@router.post("/committee/communities/{community_id}/disabled")
def set_community_disabled(
    community_id: int,
    body: DisableBody,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    ledger: LedgerRequestContext = Depends(get_ledger_context),
) -> dict:
    _committee(auth)
    _ensure_disabled()
    community = db.get(Community, community_id)
    if community is None:
        raise HTTPException(status_code=404, detail="组织不存在")
    admin_role = db.scalar(select(Role).where(Role.code == "community_admin"))
    if admin_role is None:
        raise HTTPException(status_code=400, detail="这个组织没有管理员账号")
    admin_ids = [
        int(item)
        for item in db.scalars(
            select(UserRole.user_id).where(
                UserRole.role_id == admin_role.id,
                UserRole.community_id == community_id,
            )
        ).all()
    ]
    if not admin_ids:
        raise HTTPException(status_code=400, detail="这个组织没有管理员账号")
    if body.disabled and auth.id in admin_ids:
        raise HTTPException(status_code=400, detail="不能停用自己")
    db.execute(
        text("UPDATE users SET disabled = :flag WHERE id IN (%s)" % ",".join(str(item) for item in admin_ids)),
        {"flag": 1 if body.disabled else 0},
    )
    AuditLogRepository(db).create(
        actor_id=auth.id,
        actor_role="committee",
        action="community.set_disabled",
        resource_type="community",
        resource_id=community_id,
        after={
            "disabled": 1 if body.disabled else 0,
            "admin_user_ids": admin_ids,
            "name": community.name,
        },
        outcome="SUCCESS",
        request_id=ledger.request_id,
        trace_id=ledger.trace_id,
        ip=ledger.ip,
        user_agent=ledger.user_agent,
    )
    db.commit()
    return {"ok": True}


@router.post("/committee/communities/{community_id}/retire")
def retire_community(
    community_id: int,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    ledger: LedgerRequestContext = Depends(get_ledger_context),
) -> dict:
    _committee(auth)
    community = db.get(Community, community_id)
    if community is None:
        raise HTTPException(status_code=404, detail="组织不存在")
    before_status = community.status
    active = db.scalar(
        select(Application.id)
        .join(Project, Project.id == Application.project_id)
        .where(
            Project.community_id == community_id,
            Application.status.notin_(("draft", "withdrawn", "rejected", "completed")),
        )
    )
    if active:
        community.status = "suspended"
        new_status = "suspended"
    else:
        community.status = "rejected"
        community.review_comment = "组委会删除"
        new_status = "rejected"
    AuditLogRepository(db).create(
        actor_id=auth.id,
        actor_role="committee",
        action="community.retire",
        resource_type="community",
        resource_id=community_id,
        before={"status": before_status},
        after={"status": new_status, "had_active_applications": bool(active)},
        outcome="SUCCESS",
        request_id=ledger.request_id,
        trace_id=ledger.trace_id,
        ip=ledger.ip,
        user_agent=ledger.user_agent,
    )
    db.commit()
    return {"ok": True, "status": new_status}
