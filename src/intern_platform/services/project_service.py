"""项目服务。"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from intern_platform.dependencies.auth import AuthUser
from intern_platform.dependencies.ledger import LedgerRequestContext
from intern_platform.models.community import Community
from intern_platform.models.project import Project
from intern_platform.repositories.audit_log import AuditLogRepository
from intern_platform.repositories.workflow_event import WorkflowEventRepository
from intern_platform.schemas.business import ProjectCreate, ProjectUpdate


def _tech_stack_to_str(value: list[str] | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    return value


class ProjectService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.audits = AuditLogRepository(session)
        self.events = WorkflowEventRepository(session)

    def list_projects(
        self,
        *,
        status: str | None = "published",
        community_id: int | None = None,
        mentor_id: int | None = None,
    ) -> list[Project]:
        stmt = select(Project).order_by(Project.id.desc())
        if status:
            stmt = stmt.where(Project.status == status)
        if community_id is not None:
            stmt = stmt.where(Project.community_id == community_id)
        if mentor_id is not None:
            stmt = stmt.where(Project.mentor_id == mentor_id)
        return list(self.session.scalars(stmt).all())

    def list_for_community(self, community_id: int) -> list[Project]:
        stmt = (
            select(Project)
            .where(Project.community_id == community_id)
            .order_by(Project.id.desc())
        )
        return list(self.session.scalars(stmt).all())

    def list_for_mentor(self, auth: AuthUser) -> list[Project]:
        """仅返回指派给当前导师的项目（草稿/已发布/已下线）。"""
        if not auth.has_role("mentor"):
            return []
        stmt = (
            select(Project)
            .where(Project.mentor_id == auth.id)
            .order_by(Project.id.desc())
        )
        return list(self.session.scalars(stmt).all())

    def get(self, project_id: int) -> Project | None:
        return self.session.get(Project, project_id)

    def create(self, auth: AuthUser, body: ProjectCreate) -> Project:
        community = self.session.get(Community, body.community_id)
        if community is None:
            raise LookupError("社区不存在")
        if community.status != "approved":
            raise ValueError("社区未通过准入，不可创建项目")

        is_org = auth.has_community_role("community_admin", body.community_id) or auth.has_role(
            "committee"
        )
        if is_org:
            mentor_id = body.mentor_id
            if mentor_id is None:
                raise ValueError("请指定负责导师")
            from intern_platform.models.role import Role, UserRole
            from intern_platform.models.user import User

            mentor = self.session.get(User, mentor_id)
            if mentor is None:
                raise LookupError("导师不存在")
            mentor_role = self.session.scalar(select(Role).where(Role.code == "mentor"))
            if mentor_role is None:
                raise ValueError("系统未配置导师角色")
            linked = self.session.scalar(
                select(UserRole).where(
                    UserRole.user_id == mentor_id,
                    UserRole.role_id == mentor_role.id,
                    UserRole.community_id == body.community_id,
                )
            )
            if linked is None and not auth.has_role("committee"):
                raise ValueError("该用户不是本社区导师，请先用组织码加入")
        elif auth.has_role("mentor"):
            raise PermissionError("创建项目由社区管理员在组织工作台完成，导师负责审核与结项")
        else:
            raise PermissionError("无权创建项目")

        project = Project(
            community_id=body.community_id,
            mentor_id=mentor_id if is_org else auth.id,
            title=body.title,
            summary=body.summary,
            description=body.description,
            tech_stack=_tech_stack_to_str(body.tech_stack),
            difficulty=body.difficulty,
            quota=body.quota,
            repo_url=body.repo_url,
            apply_deadline=body.apply_deadline,
            status="draft",
        )
        self.session.add(project)
        self.session.commit()
        self.session.refresh(project)
        return project

    def update(self, auth: AuthUser, project_id: int, body: ProjectUpdate) -> Project:
        project = self.get(project_id)
        if project is None:
            raise LookupError("项目不存在")
        is_org = auth.has_role("committee") or auth.has_community_role(
            "community_admin", project.community_id
        )
        if not (project.mentor_id == auth.id or is_org):
            raise PermissionError("无权修改项目")
        data = body.model_dump(exclude_unset=True)
        if "tech_stack" in data:
            data["tech_stack"] = _tech_stack_to_str(data["tech_stack"])
        # 仅组织侧可改派导师
        if "mentor_id" in data:
            if not is_org:
                raise PermissionError("仅社区管理员可改派负责导师")
            new_mentor_id = data["mentor_id"]
            if new_mentor_id is not None:
                from intern_platform.models.role import Role, UserRole
                from intern_platform.models.user import User

                mentor = self.session.get(User, new_mentor_id)
                if mentor is None:
                    raise LookupError("导师不存在")
                mentor_role = self.session.scalar(select(Role).where(Role.code == "mentor"))
                if mentor_role is None:
                    raise ValueError("系统未配置导师角色")
                linked = self.session.scalar(
                    select(UserRole).where(
                        UserRole.user_id == new_mentor_id,
                        UserRole.role_id == mentor_role.id,
                        UserRole.community_id == project.community_id,
                    )
                )
                if linked is None and not auth.has_role("committee"):
                    raise ValueError("该用户不是本社区导师")
        for key, value in data.items():
            setattr(project, key, value)
        self.session.commit()
        self.session.refresh(project)
        return project

    def publish(
        self,
        auth: AuthUser,
        project_id: int,
        ledger: LedgerRequestContext,
    ) -> Project:
        project = self.get(project_id)
        if project is None:
            raise LookupError("项目不存在")
        if project.mentor_id != auth.id and not (
            auth.has_role("committee")
            or auth.has_community_role("community_admin", project.community_id)
        ):
            raise PermissionError("仅项目导师、社区管理员或组委会可发布")
        before = {"status": project.status}
        project.status = "published"
        actor_role = (
            "committee"
            if auth.has_role("committee") and project.mentor_id != auth.id
            else (
                "community_admin"
                if auth.has_community_role("community_admin", project.community_id)
                and project.mentor_id != auth.id
                else "mentor"
            )
        )
        self.audits.create(
            actor_id=auth.id,
            actor_role=actor_role,
            action="project.publish",
            resource_type="project",
            resource_id=project.id,
            before=before,
            after={"status": project.status},
            outcome="SUCCESS",
            request_id=ledger.request_id,
            trace_id=ledger.trace_id,
            ip=ledger.ip,
            user_agent=ledger.user_agent,
        )
        self.events.create(
            event_type="project.publish",
            aggregate_type="project",
            aggregate_id=project.id,
            payload={"status": "published"},
            request_id=ledger.request_id,
            correlation_id=ledger.request_id,
            actor_id=auth.id,
            actor_role=actor_role,
        )
        self.session.commit()
        self.session.refresh(project)
        return project

    def close(self, auth: AuthUser, project_id: int) -> Project:
        project = self.get(project_id)
        if project is None:
            raise LookupError("项目不存在")
        if project.mentor_id != auth.id and not auth.has_role(
            "committee", "community_admin"
        ):
            raise PermissionError("无权关闭接取")
        project.status = "closed"
        self.session.commit()
        self.session.refresh(project)
        return project
