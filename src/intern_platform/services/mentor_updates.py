"""导师侧栏：最近一次进展/验收，以及点掉提示后的已读水位。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from intern_platform.models.application import Application
from intern_platform.models.application_message import ApplicationMessage
from intern_platform.models.mentor_update_seen import MentorUpdateSeen
from intern_platform.models.project import Project
from intern_platform.schemas.business import ApplicationOut
from intern_platform.services.message_codec import unpack_message

_PREFIXES = ("【进展】", "【中期】", "【验收】")


def _ensure(session: Session) -> None:
    MentorUpdateSeen.__table__.create(bind=session.get_bind(), checkfirst=True)


def _latest(session: Session, application_ids: list[int]) -> dict[int, tuple[int, str, datetime | None]]:
    if not application_ids:
        return {}
    rows = session.scalars(
        select(ApplicationMessage)
        .where(
            ApplicationMessage.application_id.in_(application_ids),
            or_(*[ApplicationMessage.body.like(f"{prefix}%") for prefix in _PREFIXES]),
        )
        .order_by(ApplicationMessage.id.desc())
    ).all()
    found: dict[int, tuple[int, str, datetime | None]] = {}
    for msg in rows:
        if msg.application_id in found:
            continue
        kind, _body = unpack_message(msg.body)
        if kind not in ("progress", "midterm", "acceptance"):
            continue
        badge = "acceptance" if kind == "acceptance" else "progress"
        found[msg.application_id] = (msg.id, badge, msg.created_at)
    return found


def attach_update_flags(session: Session, mentor_id: int, outs: list[ApplicationOut]) -> None:
    _ensure(session)
    ids = [item.id for item in outs]
    latest = _latest(session, ids)
    if not latest:
        return
    seen_rows = session.scalars(
        select(MentorUpdateSeen).where(
            MentorUpdateSeen.mentor_id == mentor_id,
            MentorUpdateSeen.application_id.in_(list(latest)),
        )
    ).all()
    seen = {row.application_id: int(row.message_id or 0) for row in seen_rows}
    for item in outs:
        hit = latest.get(item.id)
        if hit is None:
            continue
        message_id, badge, at = hit
        item.latest_update_at = at
        if message_id > seen.get(item.id, 0):
            item.update_badge = badge


def acknowledge_update(session: Session, mentor_id: int, application_id: int) -> None:
    """把该申请当前最新的进展或验收记成已看。之后再有新的才会重新出现标记。"""
    _ensure(session)
    app = session.get(Application, application_id)
    if app is None:
        raise LookupError("申请不存在")
    project = app.project or session.get(Project, app.project_id)
    if project is None or project.mentor_id != mentor_id:
        raise PermissionError("只能处理自己负责的任务")
    latest = _latest(session, [application_id]).get(application_id)
    if latest is None:
        return
    message_id = latest[0]
    row = session.scalar(
        select(MentorUpdateSeen).where(
            MentorUpdateSeen.mentor_id == mentor_id,
            MentorUpdateSeen.application_id == application_id,
        )
    )
    if row is None:
        session.add(
            MentorUpdateSeen(
                mentor_id=mentor_id,
                application_id=application_id,
                message_id=message_id,
            )
        )
    else:
        row.message_id = message_id
    session.commit()
