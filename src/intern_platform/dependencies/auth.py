"""JWT 鉴权与 RBAC 依赖。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select, text
from sqlalchemy.orm import Session, joinedload

from intern_platform.config import get_settings
from intern_platform.db.session import get_db
from intern_platform.models.role import Role, UserRole
from intern_platform.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_bearer = HTTPBearer(auto_error=False)
ALGORITHM = "HS256"


def password_token_stamp(password_hash: str) -> str:
    """密码变更后使旧 JWT 失效（不新增表字段）。"""
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class RoleBinding:
    code: str
    community_id: int | None = None


@dataclass
class AuthUser:
    user: User
    roles: list[RoleBinding]

    @property
    def id(self) -> int:
        return self.user.id

    def has_role(self, *codes: str) -> bool:
        wanted = set(codes)
        return any(r.code in wanted for r in self.roles)

    def role_codes(self) -> list[str]:
        return sorted({r.code for r in self.roles})

    def community_ids_for(self, role_code: str) -> set[int]:
        return {
            r.community_id
            for r in self.roles
            if r.code == role_code and r.community_id is not None
        }

    def has_community_role(self, role_code: str, community_id: int) -> bool:
        if self.has_role("committee"):
            return True
        # 必须绑定具体 community_id；community_id 为空的旧数据不再视为全局管理员
        return any(
            r.code == role_code and r.community_id == community_id for r in self.roles
        )

    def primary_actor_role(self, *preferred: str) -> str:
        """按优先顺序挑选服务端授权所用角色码。"""
        codes = set(self.role_codes())
        for code in preferred:
            if code in codes:
                return code
        if self.roles:
            return self.roles[0].code
        return "unknown"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(
    *,
    user_id: int,
    email: str,
    roles: list[dict[str, Any]],
    password_hash: str,
    expires_minutes: int | None = None,
) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload = {
        "sub": str(user_id),
        "email": email,
        "roles": roles,
        "pv": password_token_stamp(password_hash),
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])


def load_user_roles(db: Session, user_id: int) -> list[RoleBinding]:
    stmt = (
        select(UserRole)
        .options(joinedload(UserRole.role))
        .where(UserRole.user_id == user_id)
    )
    rows = list(db.scalars(stmt).unique().all())
    return [RoleBinding(code=ur.role.code, community_id=ur.community_id) for ur in rows]


def roles_payload(bindings: list[RoleBinding]) -> list[dict[str, Any]]:
    return [{"code": b.code, "community_id": b.community_id} for b in bindings]


def user_is_disabled(db: Session, user_id: int) -> bool:
    """停用记在后来加上的 users.disabled 列。旧库没有这一列时视为未停用。"""
    try:
        flag = db.execute(
            text("SELECT disabled FROM users WHERE id = :id"),
            {"id": user_id},
        ).scalar()
    except Exception:
        db.rollback()
        return False
    return int(flag or 0) == 1


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> AuthUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或 Token 缺失",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials)
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效 Token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    token_pv = payload.get("pv")
    if token_pv is None or token_pv != password_token_stamp(user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已失效，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user_is_disabled(db, user.id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号已停用，请联系组委会",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return AuthUser(user=user, roles=load_user_roles(db, user.id))


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> AuthUser | None:
    if credentials is None:
        return None
    try:
        return get_current_user(credentials, db)
    except HTTPException:
        return None


def require_roles(*role_codes: str) -> Callable[..., AuthUser]:
    def dependency(auth: AuthUser = Depends(get_current_user)) -> AuthUser:
        if not auth.has_role(*role_codes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要角色之一: {', '.join(role_codes)}",
            )
        return auth

    return dependency


def ensure_student_role(db: Session, user_id: int) -> None:
    role = db.scalar(select(Role).where(Role.code == "student"))
    if role is None:
        role = Role(code="student", name="学生")
        db.add(role)
        db.flush()
    exists = db.scalar(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_id == role.id,
            UserRole.community_id.is_(None),
        )
    )
    if exists is None:
        db.add(UserRole(user_id=user_id, role_id=role.id, community_id=None))
