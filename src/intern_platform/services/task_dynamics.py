"""项目任务动态（昇腾式报名/进展汇总表）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from intern_platform.models.application import Application
from intern_platform.models.application_message import ApplicationMessage
from intern_platform.models.project import Project
from intern_platform.models.review_record import ReviewRecord
from intern_platform.schemas.business import TaskDynamicsRow
from intern_platform.services.message_codec import KIND_TAGS
from intern_platform.services.project_presenters import _PUBLIC_STATUSES


def _mask_nickname(raw: str | None, email: str | None = None) -> tuple[str, str]:
    base = (raw or "").strip()
    if not base and email:
        base = email.split("@", 1)[0]
    if not base:
        base = "?"
    letter = base[0].upper()
    nick = f"{base[0]}****" if len(base) >= 1 else "?****"
    return nick, letter


def _progress_meta(status: str) -> tuple[str, str]:
    if status in ("submitted", "mentor_review"):
        return "审核中", "blue"
    if status in (
        "community_review",
        "committee_review",
        "selected",
        "in_progress",
        "final_rejected",
    ):
        return "开发中", "orange"
    if status in ("final_submitted", "mentor_final_review", "committee_final_review"):
        return "验收中", "blue"
    if status == "completed":
        return "已结项", "green"
    if status in ("rejected", "withdrawn"):
        return "已结束", "slate"
    return "—", "slate"


def list_task_dynamics(session: Session, project_id: int) -> list[TaskDynamicsRow]:
    project = session.get(Project, project_id)
    if project is None:
        raise LookupError("项目不存在")

    apps = list(
        session.scalars(
            select(Application)
            .where(
                Application.project_id == project_id,
                Application.status.in_(tuple(_PUBLIC_STATUSES)),
            )
            .options(joinedload(Application.student))
            .order_by(Application.created_at.asc(), Application.id.asc())
        )
        .unique()
        .all()
    )
    if not apps:
        return []

    app_ids = [a.id for a in apps]
    msgs = list(
        session.scalars(
            select(ApplicationMessage)
            .where(ApplicationMessage.application_id.in_(app_ids))
            .order_by(ApplicationMessage.id.asc())
        ).all()
    )
    progress_tag = KIND_TAGS["progress"]
    acceptance_tag = KIND_TAGS["acceptance"]

    prog_count: dict[int, int] = {i: 0 for i in app_ids}
    prog_last: dict[int, datetime | None] = {i: None for i in app_ids}
    acc_last: dict[int, datetime | None] = {i: None for i in app_ids}
    for m in msgs:
        body = m.body or ""
        aid = m.application_id
        if body.startswith(progress_tag):
            prog_count[aid] = prog_count.get(aid, 0) + 1
            prog_last[aid] = m.created_at
        elif body.startswith(acceptance_tag):
            acc_last[aid] = m.created_at

    # 验收通过时间：结项通过流水
    passed: dict[int, datetime | None] = {i: None for i in app_ids}
    recs = list(
        session.scalars(
            select(ReviewRecord)
            .where(
                ReviewRecord.application_id.in_(app_ids),
                ReviewRecord.action == "approve_committee_final",
            )
            .order_by(ReviewRecord.id.asc())
        ).all()
    )
    for r in recs:
        passed[r.application_id] = r.created_at

    # 若无验收留言，用 submit_final 时间兜底
    finals = list(
        session.scalars(
            select(ReviewRecord)
            .where(
                ReviewRecord.application_id.in_(app_ids),
                ReviewRecord.action == "submit_final",
            )
            .order_by(ReviewRecord.id.asc())
        ).all()
    )
    for r in finals:
        if not acc_last.get(r.application_id):
            acc_last[r.application_id] = r.created_at

    rows: list[TaskDynamicsRow] = []
    for a in apps:
        student = a.student
        name = student.display_name if student else None
        email = student.email if student else None
        nick, letter = _mask_nickname(name, email)
        label, tone = _progress_meta(a.status)
        rows.append(
            TaskDynamicsRow(
                application_id=a.id,
                nickname=nick,
                avatar_letter=letter,
                registered_at=a.created_at,
                last_progress_at=prog_last.get(a.id),
                progress_count=int(prog_count.get(a.id) or 0),
                last_acceptance_at=acc_last.get(a.id),
                acceptance_passed_at=passed.get(a.id) if a.status == "completed" else None,
                progress_label=label,
                progress_tone=tone,
            )
        )
    return rows
