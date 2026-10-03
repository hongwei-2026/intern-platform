"""申请状态机：严格迁移图。"""

from __future__ import annotations

from enum import Enum


class ApplicationStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    MENTOR_REVIEW = "mentor_review"
    COMMUNITY_REVIEW = "community_review"
    COMMITTEE_REVIEW = "committee_review"
    SELECTED = "selected"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    IN_PROGRESS = "in_progress"
    FINAL_SUBMITTED = "final_submitted"
    MENTOR_FINAL_REVIEW = "mentor_final_review"
    COMMUNITY_FINAL_REVIEW = "community_final_review"
    COMMITTEE_FINAL_REVIEW = "committee_final_review"
    COMPLETED = "completed"
    FINAL_REJECTED = "final_rejected"


class TransitionAction(str, Enum):
    SUBMIT = "submit"
    START_MENTOR_REVIEW = "start_mentor_review"
    APPROVE_MENTOR = "approve_mentor"
    APPROVE_COMMUNITY = "approve_community"
    APPROVE_COMMITTEE = "approve_committee"
    REJECT = "reject"
    START_PROGRESS = "start_progress"
    SUBMIT_FINAL = "submit_final"
    START_MENTOR_FINAL = "start_mentor_final"
    APPROVE_MENTOR_FINAL = "approve_mentor_final"
    SUBMIT_COMMUNITY_FINAL = "submit_community_final"
    APPROVE_COMMITTEE_FINAL = "approve_committee_final"
    REJECT_FINAL = "reject_final"
    # 开发期：学生放弃 / 导师取消接取
    WITHDRAW = "withdraw"
    CANCEL_ASSIGNMENT = "cancel_assignment"


# (from_status, action) -> to_status
TRANSITION_MAP: dict[tuple[ApplicationStatus, TransitionAction], ApplicationStatus] = {
    (ApplicationStatus.DRAFT, TransitionAction.SUBMIT): ApplicationStatus.SUBMITTED,
    (ApplicationStatus.SUBMITTED, TransitionAction.START_MENTOR_REVIEW): ApplicationStatus.MENTOR_REVIEW,
    (ApplicationStatus.MENTOR_REVIEW, TransitionAction.APPROVE_MENTOR): ApplicationStatus.COMMUNITY_REVIEW,
    (ApplicationStatus.MENTOR_REVIEW, TransitionAction.REJECT): ApplicationStatus.REJECTED,
    (ApplicationStatus.COMMUNITY_REVIEW, TransitionAction.APPROVE_COMMUNITY): ApplicationStatus.COMMITTEE_REVIEW,
    (ApplicationStatus.COMMUNITY_REVIEW, TransitionAction.REJECT): ApplicationStatus.REJECTED,
    (ApplicationStatus.COMMITTEE_REVIEW, TransitionAction.APPROVE_COMMITTEE): ApplicationStatus.SELECTED,
    (ApplicationStatus.COMMITTEE_REVIEW, TransitionAction.REJECT): ApplicationStatus.REJECTED,
    # 导师通过（名额已预留）即可进入开发，社区/组委会确认并行不挡开工（对齐昇腾任务开发）
    (ApplicationStatus.COMMUNITY_REVIEW, TransitionAction.START_PROGRESS): ApplicationStatus.IN_PROGRESS,
    (ApplicationStatus.COMMITTEE_REVIEW, TransitionAction.START_PROGRESS): ApplicationStatus.IN_PROGRESS,
    (ApplicationStatus.SELECTED, TransitionAction.START_PROGRESS): ApplicationStatus.IN_PROGRESS,
    (ApplicationStatus.IN_PROGRESS, TransitionAction.SUBMIT_FINAL): ApplicationStatus.FINAL_SUBMITTED,
    # 验收未通过后可再次提交验收（审核中不可再交，由业务层拦截）
    (ApplicationStatus.FINAL_REJECTED, TransitionAction.SUBMIT_FINAL): ApplicationStatus.FINAL_SUBMITTED,
    (ApplicationStatus.FINAL_SUBMITTED, TransitionAction.START_MENTOR_FINAL): ApplicationStatus.MENTOR_FINAL_REVIEW,
    (ApplicationStatus.MENTOR_FINAL_REVIEW, TransitionAction.APPROVE_MENTOR_FINAL): ApplicationStatus.COMMUNITY_FINAL_REVIEW,
    (ApplicationStatus.COMMUNITY_FINAL_REVIEW, TransitionAction.SUBMIT_COMMUNITY_FINAL): ApplicationStatus.COMMITTEE_FINAL_REVIEW,
    (ApplicationStatus.MENTOR_FINAL_REVIEW, TransitionAction.REJECT_FINAL): ApplicationStatus.FINAL_REJECTED,
    (ApplicationStatus.COMMITTEE_FINAL_REVIEW, TransitionAction.APPROVE_COMMITTEE_FINAL): ApplicationStatus.COMPLETED,
    (ApplicationStatus.COMMITTEE_FINAL_REVIEW, TransitionAction.REJECT_FINAL): ApplicationStatus.FINAL_REJECTED,
    # 名额预留后 / 开发中可放弃或取消（释放名额，可再次申请）
    (ApplicationStatus.COMMUNITY_REVIEW, TransitionAction.WITHDRAW): ApplicationStatus.WITHDRAWN,
    (ApplicationStatus.COMMITTEE_REVIEW, TransitionAction.WITHDRAW): ApplicationStatus.WITHDRAWN,
    (ApplicationStatus.SELECTED, TransitionAction.WITHDRAW): ApplicationStatus.WITHDRAWN,
    (ApplicationStatus.IN_PROGRESS, TransitionAction.WITHDRAW): ApplicationStatus.WITHDRAWN,
    (ApplicationStatus.FINAL_REJECTED, TransitionAction.WITHDRAW): ApplicationStatus.WITHDRAWN,
    (ApplicationStatus.COMMUNITY_REVIEW, TransitionAction.CANCEL_ASSIGNMENT): ApplicationStatus.WITHDRAWN,
    (ApplicationStatus.COMMITTEE_REVIEW, TransitionAction.CANCEL_ASSIGNMENT): ApplicationStatus.WITHDRAWN,
    (ApplicationStatus.SELECTED, TransitionAction.CANCEL_ASSIGNMENT): ApplicationStatus.WITHDRAWN,
    (ApplicationStatus.IN_PROGRESS, TransitionAction.CANCEL_ASSIGNMENT): ApplicationStatus.WITHDRAWN,
    (ApplicationStatus.FINAL_REJECTED, TransitionAction.CANCEL_ASSIGNMENT): ApplicationStatus.WITHDRAWN,
}

# 状态对应的当前审核节点
STATUS_NODE: dict[ApplicationStatus, str] = {
    ApplicationStatus.DRAFT: "none",
    ApplicationStatus.SUBMITTED: "mentor",
    ApplicationStatus.MENTOR_REVIEW: "mentor",
    ApplicationStatus.COMMUNITY_REVIEW: "community",
    ApplicationStatus.COMMITTEE_REVIEW: "committee",
    ApplicationStatus.SELECTED: "none",
    ApplicationStatus.REJECTED: "none",
    ApplicationStatus.WITHDRAWN: "none",
    ApplicationStatus.IN_PROGRESS: "none",
    ApplicationStatus.FINAL_SUBMITTED: "mentor",
    ApplicationStatus.MENTOR_FINAL_REVIEW: "mentor",
    ApplicationStatus.COMMUNITY_FINAL_REVIEW: "community",
    ApplicationStatus.COMMITTEE_FINAL_REVIEW: "committee",
    ApplicationStatus.COMPLETED: "none",
    ApplicationStatus.FINAL_REJECTED: "none",
}


class IllegalTransitionError(ValueError):
    """非法状态迁移。"""

    def __init__(
        self,
        from_status: str,
        action: str,
        *,
        allowed: list[str] | None = None,
    ) -> None:
        self.from_status = from_status
        self.action = action
        self.allowed = allowed or []
        detail = (
            f"非法状态迁移: status={from_status!r} action={action!r}"
            + (f"; 允许的 action={self.allowed}" if self.allowed else "")
        )
        super().__init__(detail)


def resolve_transition(
    from_status: str | ApplicationStatus,
    action: str | TransitionAction,
) -> ApplicationStatus:
    """解析合法迁移目标状态；非法则抛出 IllegalTransitionError。"""
    try:
        status = ApplicationStatus(from_status)
    except ValueError as exc:
        raise IllegalTransitionError(str(from_status), str(action)) from exc

    try:
        act = TransitionAction(action)
    except ValueError as exc:
        allowed = [
            a.value
            for (s, a) in TRANSITION_MAP
            if s == status
        ]
        raise IllegalTransitionError(status.value, str(action), allowed=allowed) from exc

    key = (status, act)
    if key not in TRANSITION_MAP:
        allowed = [a.value for (s, a) in TRANSITION_MAP if s == status]
        raise IllegalTransitionError(status.value, act.value, allowed=allowed)

    return TRANSITION_MAP[key]


def allowed_actions(from_status: str | ApplicationStatus) -> list[str]:
    status = ApplicationStatus(from_status)
    return [a.value for (s, a) in TRANSITION_MAP if s == status]
