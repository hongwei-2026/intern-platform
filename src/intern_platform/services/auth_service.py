"""鉴权业务服务。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from intern_platform.dependencies.auth import (
    AuthUser,
    create_access_token,
    ensure_student_role,
    hash_password,
    load_user_roles,
    roles_payload,
    verify_password,
)
from intern_platform.dependencies.ledger import LedgerRequestContext
from intern_platform.models.role import Role, UserRole
from intern_platform.models.user import User
from intern_platform.repositories.audit_log import AuditLogRepository
from intern_platform.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    RoleGrantRequest,
    RoleOut,
    TokenResponse,
    UserOut,
    UserUpdateRequest,
)


def user_to_out(user: User, roles: list | None = None) -> UserOut:
    bindings = roles if roles is not None else []
    avatars: dict[str, str] = {}
    raw = getattr(user, "oauth_avatars", None) or ""
    if raw:
        try:
            import json

            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                avatars = {str(k): str(v) for k, v in parsed.items() if isinstance(v, str)}
        except Exception:  # noqa: BLE001
            avatars = {}
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        school=user.school,
        github_id=user.github_id,
        gitea_id=user.gitea_id,
        gitcode_id=getattr(user, "gitcode_id", None),
        gitee_id=getattr(user, "gitee_id", None),
        gitlink_id=getattr(user, "gitlink_id", None),
        oauth_avatars=avatars,
        member_no=user.member_no,
        bio=user.bio,
        phone=getattr(user, "phone", None),
        major=getattr(user, "major", None),
        grade=getattr(user, "grade", None),
        degree=getattr(user, "degree", None),
        homepage_url=getattr(user, "homepage_url", None),
        contact_email=getattr(user, "contact_email", None),
        city=getattr(user, "city", None),
        auth_provider=user.auth_provider,
        roles=[RoleOut(code=b.code, community_id=b.community_id) for b in bindings],
    )


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.audits = AuditLogRepository(session)

    def register(self, body: RegisterRequest, ledger: LedgerRequestContext) -> TokenResponse:
        existing = self.session.scalar(select(User).where(User.email == body.email))
        if existing:
            raise ValueError("邮箱已注册")
        user = User(
            email=body.email.strip().lower(),
            password_hash=hash_password(body.password),
            display_name=body.display_name,
            school=body.school,
            auth_provider="local",
        )
        self.session.add(user)
        self.session.flush()
        ensure_student_role(self.session, user.id)
        self.session.flush()
        bindings = load_user_roles(self.session, user.id)
        token = create_access_token(
            user_id=user.id,
            email=user.email,
            roles=roles_payload(bindings),
        )
        self.audits.create(
            actor_id=user.id,
            actor_role="student",
            action="auth.register",
            resource_type="user",
            resource_id=user.id,
            after={"email": user.email},
            outcome="SUCCESS",
            request_id=ledger.request_id,
            trace_id=ledger.trace_id,
            ip=ledger.ip,
            user_agent=ledger.user_agent,
        )
        self.session.commit()
        return TokenResponse(access_token=token, user=user_to_out(user, bindings))

    def register_mentor(
        self,
        *,
        email: str,
        password: str,
        display_name: str,
        invite_code: str,
        ledger: LedgerRequestContext,
    ) -> TokenResponse:
        """导师自助注册：邀请码校验通过后绑定对应社区，不公开邀请码。"""
        from intern_platform.services.community_service import CommunityService

        email_n = email.strip().lower()
        if not email_n or "@" not in email_n:
            raise ValueError("邮箱格式不正确")
        existing = self.session.scalar(select(User).where(User.email == email_n))
        if existing:
            raise ValueError("邮箱已注册，请直接登录；若需加入社区，请联系社区管理员")

        svc = CommunityService(self.session)
        community = svc.get_by_invite_code(invite_code)
        if community is None:
            raise ValueError("邀请码无效")
        if community.status != "approved":
            raise ValueError("该社区尚未准入")

        user = User(
            email=email_n,
            password_hash=hash_password(password),
            display_name=display_name.strip() or email_n.split("@")[0],
            auth_provider="local",
        )
        self.session.add(user)
        self.session.flush()

        mentor_role = self.session.scalar(select(Role).where(Role.code == "mentor"))
        if mentor_role is None:
            raise LookupError("系统未配置 mentor 角色")
        self.session.add(
            UserRole(
                user_id=user.id,
                role_id=mentor_role.id,
                community_id=community.id,
            )
        )
        self.session.flush()
        bindings = load_user_roles(self.session, user.id)
        token = create_access_token(
            user_id=user.id,
            email=user.email,
            roles=roles_payload(bindings),
        )
        self.audits.create(
            actor_id=user.id,
            actor_role="mentor",
            action="auth.register_mentor",
            resource_type="user",
            resource_id=user.id,
            after={"email": user.email, "community_id": community.id},
            outcome="SUCCESS",
            request_id=ledger.request_id,
            trace_id=ledger.trace_id,
            ip=ledger.ip,
            user_agent=ledger.user_agent,
        )
        self.session.commit()
        return TokenResponse(access_token=token, user=user_to_out(user, bindings))

    def login(self, body: LoginRequest, ledger: LedgerRequestContext) -> TokenResponse:
        email = body.email.strip().lower()
        user = self.session.scalar(select(User).where(User.email == email))
        ok = user is not None and verify_password(body.password, user.password_hash)
        if not ok:
            self.audits.create(
                actor_id=user.id if user else None,
                actor_role="anonymous",
                action="auth.login",
                resource_type="user",
                resource_id=user.id if user else email,
                outcome="FAIL",
                request_id=ledger.request_id,
                trace_id=ledger.trace_id,
                ip=ledger.ip,
                user_agent=ledger.user_agent,
            )
            self.session.commit()
            raise PermissionError("邮箱或密码错误")

        bindings = load_user_roles(self.session, user.id)
        token = create_access_token(
            user_id=user.id,
            email=user.email,
            roles=roles_payload(bindings),
        )
        self.audits.create(
            actor_id=user.id,
            actor_role=bindings[0].code if bindings else "unknown",
            action="auth.login",
            resource_type="user",
            resource_id=user.id,
            outcome="SUCCESS",
            request_id=ledger.request_id,
            trace_id=ledger.trace_id,
            ip=ledger.ip,
            user_agent=ledger.user_agent,
        )
        self.session.commit()
        return TokenResponse(access_token=token, user=user_to_out(user, bindings))

    def update_me(self, auth: AuthUser, body: UserUpdateRequest) -> UserOut:
        user = auth.user
        data = body.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(user, key, value)
        self.session.add(user)
        self.session.commit()
        bindings = load_user_roles(self.session, user.id)
        return user_to_out(user, bindings)

    def change_password(self, auth: AuthUser, body: ChangePasswordRequest) -> None:
        user = auth.user
        if not verify_password(body.old_password, user.password_hash):
            raise PermissionError("原密码不正确")
        user.password_hash = hash_password(body.new_password)
        self.session.add(user)
        self.session.commit()

    def grant_role(
        self,
        auth: AuthUser,
        body: RoleGrantRequest,
        ledger: LedgerRequestContext,
    ) -> UserOut:
        if not auth.has_role("committee"):
            raise PermissionError("仅组委会可赋权")
        role = self.session.scalar(select(Role).where(Role.code == body.role_code))
        if role is None:
            raise LookupError(f"角色不存在: {body.role_code}")
        target = self.session.get(User, body.user_id)
        if target is None:
            raise LookupError("用户不存在")
        stmt = select(UserRole).where(
            UserRole.user_id == body.user_id,
            UserRole.role_id == role.id,
        )
        if body.community_id is None:
            stmt = stmt.where(UserRole.community_id.is_(None))
        else:
            stmt = stmt.where(UserRole.community_id == body.community_id)
        exists = self.session.scalar(stmt)
        if not exists:
            self.session.add(
                UserRole(
                    user_id=body.user_id,
                    role_id=role.id,
                    community_id=body.community_id,
                )
            )
        self.audits.create(
            actor_id=auth.id,
            actor_role="committee",
            action="user.role_grant",
            resource_type="user",
            resource_id=body.user_id,
            after={
                "role_code": body.role_code,
                "community_id": body.community_id,
            },
            outcome="SUCCESS",
            request_id=ledger.request_id,
            trace_id=ledger.trace_id,
            ip=ledger.ip,
            user_agent=ledger.user_agent,
        )
        self.session.commit()
        bindings = load_user_roles(self.session, target.id)
        return user_to_out(target, bindings)
