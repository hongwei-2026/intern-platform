"""社区 / 项目 / 公示等业务 Schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CommunityCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    homepage_url: str | None = None
    mirror_doc_url: str | None = None
    gitea_org_url: str | None = None
    logo_url: str | None = None
    tags: list[str] | None = None
    intro_body: dict[str, Any] | str | None = None
    admin_name: str | None = None
    admin_email: str | None = None


class CommunityUpdate(BaseModel):
    """社区管理员维护对外主页信息。"""

    name: str | None = None
    description: str | None = None
    homepage_url: str | None = None
    mirror_doc_url: str | None = None
    gitea_org_url: str | None = None
    logo_url: str | None = None
    tags: list[str] | None = None
    intro_body: dict[str, Any] | str | None = None


class CommunityReviewRequest(BaseModel):
    decision: str = Field(..., pattern="^(approve|reject)$")
    comment: str | None = None


class CommunityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    description: str | None = None
    logo_url: str | None = None
    homepage_url: str | None = None
    mirror_doc_url: str | None = None
    gitea_org_url: str | None = None
    status: str
    invite_code: str | None = None
    tags: list[str] = Field(default_factory=list)
    intro_body: dict[str, Any] | None = None


class CommunityJoinRequest(BaseModel):
    invite_code: str = Field(min_length=4, max_length=32)
    as_role: str = Field(default="mentor", pattern="^(mentor|community_admin)$")


class CommunityJoinOut(BaseModel):
    community_id: int
    community_name: str
    role: str
    invite_code: str


class ExtensionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    community_id: int
    profile_blocks: str | None = None
    application_schema: str | None = None
    final_schema: str | None = None
    enabled_modules: str | None = None


class ExtensionUpdate(BaseModel):
    profile_blocks: str | None = None
    application_schema: str | None = None
    final_schema: str | None = None
    enabled_modules: str | None = None


class ProjectCreate(BaseModel):
    community_id: int
    title: str
    summary: str | None = None
    description: str | None = None
    tech_stack: list[str] | str | None = None
    difficulty: str | None = None
    quota: int = 1
    repo_url: str | None = None
    apply_deadline: datetime | None = None
    # 组织创建项目时指定负责导师；导师本人创建时可省略（兼容旧调用）
    mentor_id: int | None = None


class CommunityMemberOut(BaseModel):
    user_id: int
    display_name: str
    email: str
    role: str
    community_id: int | None = None
    community_name: str | None = None
    role_label: str | None = None


class MentorCreateRequest(BaseModel):
    """社区管理员为本社区创建/绑定导师账号（可选；推荐导师自助注册）。"""

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=128)
    display_name: str = Field(min_length=1, max_length=128)


class MentorRegisterRequest(BaseModel):
    """导师自助注册：须填写社区管理员私下发放的邀请码。"""

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=128)
    display_name: str = Field(min_length=1, max_length=128)
    invite_code: str = Field(min_length=4, max_length=32)
class ProjectUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None
    description: str | None = None
    tech_stack: list[str] | str | None = None
    difficulty: str | None = None
    quota: int | None = None
    repo_url: str | None = None
    apply_deadline: datetime | None = None
    mentor_id: int | None = None


class ProjectAssigneeOut(BaseModel):
    """项目公开页展示：谁在审 / 谁已接取。"""

    application_id: int
    student_id: int
    student_name: str | None = None
    status: str
    # assigned=已占用名额 reviewing=审核进行中
    kind: str = "assigned"


class TaskDynamicsRow(BaseModel):
    """昇腾式任务动态：项目维度报名/进展汇总（昵称脱敏）。"""

    application_id: int
    nickname: str
    avatar_letter: str
    registered_at: datetime | None = None
    last_progress_at: datetime | None = None
    progress_count: int = 0
    last_acceptance_at: datetime | None = None
    acceptance_passed_at: datetime | None = None
    progress_label: str = "—"
    progress_tone: str = "slate"  # orange | blue | green | slate | red


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    community_id: int
    mentor_id: int
    title: str
    summary: str | None = None
    description: str | None = None
    tech_stack: str | None = None
    difficulty: str | None = None
    quota: int
    repo_url: str | None = None
    apply_deadline: datetime | None = None
    status: str
    # 已占用名额（录取后至结项）
    assignees: list[ProjectAssigneeOut] = []
    # 审核进行中（尚未录取，供他人知悉竞争情况）
    applicants_reviewing: list[ProjectAssigneeOut] = []
    seats_taken: int = 0
    seats_available: int | None = None
    reviewing_count: int = 0
    mentor_name: str | None = None
    mentor_email: str | None = None


class ApplicationCreate(BaseModel):
    statement: str | None = None
    attachment_url: str | None = None
    extra_fields: dict[str, Any] | None = None
    submit: bool = False


class ApplicationUpdate(BaseModel):
    statement: str | None = None
    attachment_url: str | None = None
    extra_fields: dict[str, Any] | None = None


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    student_id: int
    student_name: str | None = None
    student_email: str | None = None
    statement: str | None = None
    attachment_url: str | None = None
    extra_fields: str | None = None
    resume_pdf: str | None = None
    design_pdf: str | None = None
    status: str
    current_node: str
    version: int = 0
    project_title: str | None = None
    # 该生最近一次进展或验收的时间，用来把最新的排到上面
    latest_update_at: datetime | None = None
    # progress=新进展，acceptance=新验收；导师点掉标记后为空
    update_badge: str | None = None
    review_records: list[dict] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ReviewRequest(BaseModel):
    decision: str = Field(..., pattern="^(approve|reject)$")
    comment: str | None = None
    version: int | None = None
    idempotency_key: str | None = None
    request_id: str | None = None
    trace_id: str | None = None


class ReviewResponse(BaseModel):
    application_id: int
    from_status: str
    to_status: str
    action: str
    idempotent_replay: bool = False
    version: int
    mail_sent: bool | None = None
    mail_hint: str | None = None


class AnnouncementCreate(BaseModel):
    type: str = Field(..., pattern="^(selection|final|general)$")
    title: str
    body: str | None = None
    community_id: int | None = None
    project_id: int | None = None
    application_id: int | None = None
    is_public: bool = True


class AnnouncementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    title: str
    body: str | None = None
    community_id: int | None = None
    project_id: int | None = None
    application_id: int | None = None
    published_by: int
    published_at: datetime | None = None
    is_public: int


class FinalUpsert(BaseModel):
    """验收材料：说明 + ZIP（PR/Issue/截图等）+ 设计文档链接 + 代码链接。"""

    # 代码仓 / PR 链接（库字段 pr_mr_url）
    pr_mr_url: str = Field(min_length=1, max_length=512)
    # 设计文档链接
    report_url: str | None = Field(default=None, max_length=512)
    # 阶段说明
    report_text: str | None = Field(default=None, max_length=2000)
    extra_fields: dict[str, Any] | None = None


class FinalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    pr_mr_url: str
    report_url: str | None = None
    report_text: str | None = None
    extra_fields: str | None = None
    status: str


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    # progress=更新进展 midterm=中期反馈 feedback=导师反馈 note=普通备注
    kind: str = Field(
        default="note",
        pattern="^(note|progress|midterm|feedback|acceptance|official|reward)$",
    )
    design_doc_url: str | None = Field(default=None, max_length=512)
    code_url: str | None = Field(default=None, max_length=512)
    attachment_url: str | None = Field(default=None, max_length=512)
    attachment_name: str | None = Field(default=None, max_length=256)


class RewardDecision(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    note: str | None = Field(default=None, max_length=500)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    sender_id: int
    body: str
    kind: str = "note"
    design_doc_url: str | None = None
    code_url: str | None = None
    attachment_url: str | None = None
    attachment_name: str | None = None
    community_name: str | None = None
    reward_status: str | None = None
    created_at: datetime | None = None


class PortalLinksOut(BaseModel):
    home_url: str | None = None
    docs_url: str | None = None
    join_guide_url: str | None = None
    gitea_url: str | None = None
    mirror_url: str | None = None
    raw: dict[str, str | None] = Field(default_factory=dict)
