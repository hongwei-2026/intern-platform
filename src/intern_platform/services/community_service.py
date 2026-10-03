"""社区服务。"""

from __future__ import annotations

import secrets
import string

from sqlalchemy import select
from sqlalchemy.orm import Session

from intern_platform.dependencies.auth import AuthUser, hash_password
from intern_platform.dependencies.ledger import LedgerRequestContext
from intern_platform.models.community import Community
from intern_platform.models.community_extension import CommunityExtension
from intern_platform.models.role import Role, UserRole
from intern_platform.repositories.audit_log import AuditLogRepository
from intern_platform.repositories.workflow_event import WorkflowEventRepository
from intern_platform.services.community_codec import dumps_intro_body, dumps_tags
from intern_platform.schemas.business import (
    CommunityCreate,
    CommunityJoinOut,
    CommunityJoinRequest,
    CommunityReviewRequest,
    ExtensionUpdate,
)


def _gen_invite_code(name: str) -> str:
    ascii_prefix = "".join(ch for ch in name.upper() if ("A" <= ch <= "Z") or ("0" <= ch <= "9"))
    prefix = (ascii_prefix[:6] or "ORG").ljust(3, "X")[:6]
    suffix = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    return f"{prefix}-{suffix}"


class CommunityService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.audits = AuditLogRepository(session)
        self.events = WorkflowEventRepository(session)

    def list_communities(self, status: str | None = None) -> list[Community]:
        stmt = select(Community).order_by(Community.id.asc())
        if status:
            stmt = stmt.where(Community.status == status)
        return list(self.session.scalars(stmt).all())

    def get_by_slug(self, slug: str) -> Community | None:
        return self.session.scalar(select(Community).where(Community.slug == slug))

    def get(self, community_id: int) -> Community | None:
        return self.session.get(Community, community_id)

    def get_by_invite_code(self, code: str) -> Community | None:
        normalized = code.strip().upper()
        return self.session.scalar(
            select(Community).where(Community.invite_code == normalized)
        )

    def list_mine(self, auth: AuthUser) -> list[Community]:
        """当前用户作为管理员/导师绑定的社区（含组织码）。"""
        if auth.has_role("committee"):
            return self.list_communities(status="approved")
        role_codes = ("community_admin", "mentor")
        stmt = (
            select(Community)
            .join(UserRole, UserRole.community_id == Community.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                UserRole.user_id == auth.id,
                Role.code.in_(role_codes),
            )
            .order_by(Community.id.asc())
            .distinct()
        )
        return list(self.session.scalars(stmt).all())

    def list_admin_of(self, auth: AuthUser) -> list[Community]:
        """仅返回当前用户担任「社区管理员」的社区（不含组委会全站视角）。"""
        ids = sorted(auth.community_ids_for("community_admin"))
        if not ids:
            return []
        stmt = (
            select(Community)
            .where(Community.id.in_(ids))
            .order_by(Community.id.asc())
        )
        return list(self.session.scalars(stmt).all())

    def create_mentor(
        self,
        auth: AuthUser,
        community_id: int,
        *,
        email: str,
        password: str,
        display_name: str,
        ledger: LedgerRequestContext,
    ) -> dict:
        from intern_platform.dependencies.auth import hash_password
        from intern_platform.models.user import User
        from intern_platform.repositories.audit_log import AuditLogRepository

        community = self.get(community_id)
        if community is None:
            raise LookupError("社区不存在")
        if community.status != "approved":
            raise ValueError("社区未准入，不可添加导师")
        if not (
            auth.has_community_role("community_admin", community_id)
            or auth.has_role("committee")
        ):
            raise PermissionError("仅本社区管理员可创建导师账号")

        email_n = email.strip().lower()
        if not email_n or "@" not in email_n:
            raise ValueError("邮箱格式不正确")

        mentor_role = self.session.scalar(select(Role).where(Role.code == "mentor"))
        if mentor_role is None:
            raise LookupError("系统未配置 mentor 角色")

        user = self.session.scalar(select(User).where(User.email == email_n))
        created = False
        if user is None:
            user = User(
                email=email_n,
                password_hash=hash_password(password),
                display_name=display_name.strip() or email_n.split("@")[0],
                auth_provider="local",
            )
            self.session.add(user)
            self.session.flush()
            created = True
        else:
            # 已有账号：绑定角色；可选重置密码（便于管理员代建）
            if password:
                user.password_hash = hash_password(password)
            if display_name.strip():
                user.display_name = display_name.strip()

        exists = self.session.scalar(
            select(UserRole).where(
                UserRole.user_id == user.id,
                UserRole.role_id == mentor_role.id,
                UserRole.community_id == community_id,
            )
        )
        if exists is None:
            self.session.add(
                UserRole(
                    user_id=user.id,
                    role_id=mentor_role.id,
                    community_id=community_id,
                )
            )

        AuditLogRepository(self.session).create(
            actor_id=auth.id,
            actor_role="community_admin",
            action="community.mentor_create",
            resource_type="community",
            resource_id=community_id,
            after={
                "user_id": user.id,
                "email": user.email,
                "created_user": created,
            },
            outcome="SUCCESS",
            request_id=ledger.request_id,
            trace_id=ledger.trace_id,
            ip=ledger.ip,
            user_agent=ledger.user_agent,
        )
        self.session.commit()
        self.session.refresh(user)
        return {
            "user_id": user.id,
            "display_name": user.display_name,
            "email": user.email,
            "role": "mentor",
            "community_id": community_id,
            "community_name": community.name,
            "role_label": "导师",
            "created_user": created,
        }
    def create(self, auth: AuthUser, body: CommunityCreate) -> Community:
        existing = self.get_by_slug(body.slug)
        if existing:
            raise ValueError("slug 已存在")
        community = Community(
            name=body.name,
            slug=body.slug,
            description=body.description,
            homepage_url=body.homepage_url,
            mirror_doc_url=body.mirror_doc_url,
            gitea_org_url=body.gitea_org_url,
            logo_url=body.logo_url,
            status="pending",
            applicant_user_id=auth.id,
        )
        self.session.add(community)
        self.session.flush()
        self.session.add(CommunityExtension(community_id=community.id))
        if auth.has_role("committee") and (body.admin_email or "").strip():
            community.status = "approved"
            community.reviewed_by = auth.id
            if not community.invite_code:
                community.invite_code = _gen_invite_code(community.name)
            self._bind_community_admin(
                community,
                email=body.admin_email or "",
                display_name=body.admin_name or "",
            )
        self.session.commit()
        self.session.refresh(community)
        return community

    def _bind_community_admin(self, community: Community, *, email: str, display_name: str) -> None:
        """组委会开通社区时同时建立该社区的组织账号。"""
        from intern_platform.models.user import User

        email_n = email.strip().lower()
        if "@" not in email_n:
            raise ValueError("管理员邮箱格式不正确")
        admin_role = self.session.scalar(select(Role).where(Role.code == "community_admin"))
        if admin_role is None:
            raise LookupError("系统未配置 community_admin 角色")
        user = self.session.scalar(select(User).where(User.email == email_n))
        if user is not None:
            self._assert_role_compatible(user.id, "community_admin")
        if user is None:
            user = User(
                email=email_n,
                password_hash=hash_password("Demo@123456"),
                display_name=display_name.strip() or email_n.split("@")[0],
                school="华中科技大学",
                auth_provider="local",
            )
            self.session.add(user)
            self.session.flush()
        exists = self.session.scalar(
            select(UserRole).where(
                UserRole.user_id == user.id,
                UserRole.role_id == admin_role.id,
                UserRole.community_id == community.id,
            )
        )
        if exists is None:
            self.session.add(
                UserRole(user_id=user.id, role_id=admin_role.id, community_id=community.id)
            )
        community.applicant_user_id = user.id

    def update_profile(
        self,
        auth: AuthUser,
        community_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        homepage_url: str | None = None,
        mirror_doc_url: str | None = None,
        gitea_org_url: str | None = None,
        logo_url: str | None = None,
        tags: list[str] | None = None,
        intro_body: dict | str | None = None,
    ) -> Community:
        community = self.get(community_id)
        if community is None:
            raise LookupError("社区不存在")
        if not (
            auth.has_community_role("community_admin", community_id)
            or auth.has_role("committee")
        ):
            raise PermissionError("仅本社区管理员可编辑主页")
        if name is not None:
            name_s = name.strip()
            if not name_s:
                raise ValueError("社区名称不能为空")
            community.name = name_s
        if description is not None:
            community.description = description.strip() or None
        if homepage_url is not None:
            community.homepage_url = homepage_url.strip() or None
        if mirror_doc_url is not None:
            community.mirror_doc_url = mirror_doc_url.strip() or None
        if gitea_org_url is not None:
            community.gitea_org_url = gitea_org_url.strip() or None
        if logo_url is not None:
            community.logo_url = logo_url.strip() or None
        if tags is not None:
            community.tags = dumps_tags(tags)
        if intro_body is not None:
            community.intro_body = dumps_intro_body(intro_body)
        self.session.add(community)
        self.session.commit()
        self.session.refresh(community)
        return community

    def _ensure_role(self, *, user_id: int, role_code: str, community_id: int | None) -> None:
        role = self.session.scalar(select(Role).where(Role.code == role_code))
        if role is None:
            raise ValueError(f"角色不存在: {role_code}")
        if community_id is None:
            exists = self.session.scalar(
                select(UserRole).where(
                    UserRole.user_id == user_id,
                    UserRole.role_id == role.id,
                    UserRole.community_id.is_(None),
                )
            )
        else:
            exists = self.session.scalar(
                select(UserRole).where(
                    UserRole.user_id == user_id,
                    UserRole.role_id == role.id,
                    UserRole.community_id == community_id,
                )
            )
        if not exists:
            self.session.add(
                UserRole(user_id=user_id, role_id=role.id, community_id=community_id)
            )

    def review(
        self,
        auth: AuthUser,
        community_id: int,
        body: CommunityReviewRequest,
        ledger: LedgerRequestContext,
    ) -> Community:
        if not auth.has_role("committee"):
            raise PermissionError("仅组委会可审核社区")
        community = self.get(community_id)
        if community is None:
            raise LookupError("社区不存在")
        if community.status != "pending":
            raise ValueError(f"社区状态不可审核: {community.status}")

        before = {"status": community.status}
        community.status = "approved" if body.decision == "approve" else "rejected"
        community.reviewed_by = auth.id
        community.review_comment = body.comment
        if community.status == "approved":
            if not community.invite_code:
                for _ in range(8):
                    code = _gen_invite_code(community.name)
                    if not self.get_by_invite_code(code):
                        community.invite_code = code
                        break
            if community.applicant_user_id:
                self._ensure_role(
                    user_id=community.applicant_user_id,
                    role_code="community_admin",
                    community_id=community.id,
                )
                self._ensure_role(
                    user_id=community.applicant_user_id,
                    role_code="community_admin",
                    community_id=None,
                )
        after = {
            "status": community.status,
            "comment": body.comment,
            "invite_code": community.invite_code,
        }

        self.audits.create(
            actor_id=auth.id,
            actor_role="committee",
            action="community.review",
            resource_type="community",
            resource_id=community.id,
            before=before,
            after=after,
            outcome="SUCCESS",
            request_id=ledger.request_id,
            trace_id=ledger.trace_id,
            ip=ledger.ip,
            user_agent=ledger.user_agent,
        )
        self.events.create(
            event_type="community.review",
            aggregate_type="community",
            aggregate_id=community.id,
            payload=after,
            request_id=ledger.request_id,
            correlation_id=ledger.request_id,
            actor_id=auth.id,
            actor_role="committee",
        )
        self.session.commit()
        self.session.refresh(community)
        return community

    def _assert_role_compatible(self, user_id: int, new_code: str) -> None:
        """一个邮箱只能属于一种身份：学生、导师、组织、组委会互不混用。"""
        labels = {
            "student": "学生",
            "mentor": "导师",
            "community_admin": "组织",
            "committee": "组委会",
        }
        codes = set(
            self.session.scalars(
                select(Role.code)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.user_id == user_id)
            ).all()
        )
        conflict = codes - {new_code}
        if not conflict:
            return
        names = "、".join(labels.get(code, code) for code in sorted(conflict))
        raise ValueError(f"该邮箱已是{names}账号，不能再用作其他身份，请换一个邮箱")

    def join_with_invite(self, auth: AuthUser, body: CommunityJoinRequest) -> CommunityJoinOut:
        community = self.get_by_invite_code(body.invite_code)
        if community is None or community.status != "approved":
            raise LookupError("组织码无效或社区未通过入驻")
        role_code = body.as_role
        self._assert_role_compatible(auth.id, role_code)
        self._ensure_role(user_id=auth.id, role_code=role_code, community_id=community.id)
        self._ensure_role(user_id=auth.id, role_code=role_code, community_id=None)
        self.session.commit()
        return CommunityJoinOut(
            community_id=community.id,
            community_name=community.name,
            role=role_code,
            invite_code=community.invite_code or body.invite_code.strip().upper(),
        )

    def get_extension(self, community_id: int) -> CommunityExtension | None:
        return self.session.scalar(
            select(CommunityExtension).where(
                CommunityExtension.community_id == community_id
            )
        )

    def upsert_extension(
        self,
        auth: AuthUser,
        community_id: int,
        body: ExtensionUpdate,
    ) -> CommunityExtension:
        community = self.get(community_id)
        if community is None:
            raise LookupError("社区不存在")
        if not (
            auth.has_role("committee")
            or auth.has_community_role("community_admin", community_id)
        ):
            raise PermissionError("无权修改社区扩展")

        ext = self.get_extension(community_id)
        if ext is None:
            ext = CommunityExtension(community_id=community_id)
            self.session.add(ext)
        data = body.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(ext, key, value)
        self.session.commit()
        self.session.refresh(ext)
        return ext

    def list_members(
        self,
        auth: AuthUser,
        community_id: int,
        *,
        role_code: str | None = "mentor",
    ) -> list[dict]:
        community = self.get(community_id)
        if community is None:
            raise LookupError("社区不存在")
        if not (
            auth.has_role("committee")
            or auth.has_community_role("community_admin", community_id)
        ):
            raise PermissionError("无权查看成员")

        from intern_platform.models.user import User

        stmt = (
            select(User, Role.code)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.community_id == community_id)
            .order_by(User.id.asc())
        )
        if role_code:
            stmt = stmt.where(Role.code == role_code)
        rows = self.session.execute(stmt).all()
        role_zh = {"mentor": "导师", "community_admin": "社区管理员", "committee": "组委会"}
        return [
            {
                "user_id": user.id,
                "display_name": user.display_name,
                "email": user.email,
                "role": code,
                "community_id": community_id,
                "community_name": community.name,
                "role_label": role_zh.get(code, code),
            }
            for user, code in rows
        ]
