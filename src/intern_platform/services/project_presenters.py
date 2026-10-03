"""项目 DTO 组装：附加接取 / 审核中学生信息（公开页可见）。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from intern_platform.models.application import Application
from intern_platform.models.project import Project
from intern_platform.models.user import User
from intern_platform.schemas.business import ProjectAssigneeOut, ProjectOut

# 占用名额：导师通过之后即预留（含待社区/组委会），避免他人不知满员还做材料
_SEAT_STATUSES = frozenset(
    {
        "community_review",
        "committee_review",
        "selected",
        "in_progress",
        "final_submitted",
        "mentor_final_review",
        "committee_final_review",
        "final_rejected",
        "completed",
    }
)

# 尚未占用名额：仍在导师关之前竞争
_REVIEW_STATUSES = frozenset(
    {
        "submitted",
        "mentor_review",
    }
)

_PUBLIC_STATUSES = _SEAT_STATUSES | _REVIEW_STATUSES


def seat_taken_count(session: Session, project_id: int) -> int:
    """导师通过后即计入占用名额。"""
    n = session.scalar(
        select(func.count())
        .select_from(Application)
        .where(
            Application.project_id == project_id,
            Application.status.in_(tuple(_SEAT_STATUSES)),
        )
    )
    return int(n or 0)


def _row_to_assignee(a: Application, *, kind: str) -> ProjectAssigneeOut:
    return ProjectAssigneeOut(
        application_id=a.id,
        student_id=a.student_id,
        student_name=(a.student.display_name if a.student else None),
        status=a.status,
        kind=kind,
    )


def _split_rows(rows: list[Application]) -> tuple[list[ProjectAssigneeOut], list[ProjectAssigneeOut]]:
    assignees: list[ProjectAssigneeOut] = []
    reviewing: list[ProjectAssigneeOut] = []
    for a in rows:
        if a.status in _SEAT_STATUSES:
            # community/committee = 导师已通过、名额已预留
            kind = (
                "reserved"
                if a.status in ("community_review", "committee_review")
                else "assigned"
            )
            assignees.append(_row_to_assignee(a, kind=kind))
        elif a.status in _REVIEW_STATUSES:
            reviewing.append(_row_to_assignee(a, kind="reviewing"))
    return assignees, reviewing


def _with_mentor(out: ProjectOut, mentor: User | None) -> ProjectOut:
    if mentor is None:
        return out
    return out.model_copy(
        update={"mentor_name": mentor.display_name, "mentor_email": mentor.email}
    )


def _enrich(project: Project, rows: list[Application]) -> ProjectOut:
    assignees, reviewing = _split_rows(rows)
    taken = len(assignees)
    out = ProjectOut.model_validate(project)
    return out.model_copy(
        update={
            "assignees": assignees,
            # 公开页不公示审核中名单（对标开源之夏：只公示中选）
            "applicants_reviewing": [],
            "seats_taken": taken,
            "seats_available": max(0, int(project.quota or 0) - taken),
            "reviewing_count": len(reviewing),
        }
    )


def project_to_out(session: Session, project: Project) -> ProjectOut:
    stmt = (
        select(Application)
        .where(
            Application.project_id == project.id,
            Application.status.in_(tuple(_PUBLIC_STATUSES)),
        )
        .options(joinedload(Application.student))
        .order_by(Application.id.asc())
    )
    rows = list(session.scalars(stmt).unique().all())
    mentor = session.get(User, project.mentor_id)
    return _with_mentor(_enrich(project, rows), mentor)


def projects_to_out(session: Session, projects: list[Project]) -> list[ProjectOut]:
    if not projects:
        return []
    ids = [p.id for p in projects]
    stmt = (
        select(Application)
        .where(
            Application.project_id.in_(ids),
            Application.status.in_(tuple(_PUBLIC_STATUSES)),
        )
        .options(joinedload(Application.student))
        .order_by(Application.id.asc())
    )
    by_project: dict[int, list[Application]] = {pid: [] for pid in ids}
    for a in session.scalars(stmt).unique().all():
        by_project.setdefault(a.project_id, []).append(a)
    mentor_ids = {project.mentor_id for project in projects}
    mentors = {
        user.id: user
        for user in session.scalars(select(User).where(User.id.in_(mentor_ids))).all()
    }
    return [
        _with_mentor(_enrich(project, by_project.get(project.id, [])), mentors.get(project.mentor_id))
        for project in projects
    ]
