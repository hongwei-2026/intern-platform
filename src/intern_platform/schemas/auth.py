"""通用用户 / 鉴权 Schema。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RoleOut(BaseModel):
    code: str
    community_id: int | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str
    school: str | None = None
    github_id: str | None = None
    gitea_id: str | None = None
    gitcode_id: str | None = None
    gitee_id: str | None = None
    gitlink_id: str | None = None
    oauth_avatars: dict[str, str] = Field(default_factory=dict)
    member_no: str | None = None
    bio: str | None = None
    phone: str | None = None
    major: str | None = None
    grade: str | None = None
    degree: str | None = None
    homepage_url: str | None = None
    contact_email: str | None = None
    city: str | None = None
    auth_provider: str = "local"
    roles: list[RoleOut] = Field(default_factory=list)


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=6, max_length=128)
    display_name: str = Field(min_length=1, max_length=128)
    school: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserUpdateRequest(BaseModel):
    """个人资料可改字段。平台账号 ID / 学号等身份字段禁止手填，仅走 OAuth 绑定。"""

    display_name: str | None = None
    school: str | None = None
    bio: str | None = None
    phone: str | None = None
    major: str | None = None
    grade: str | None = None
    degree: str | None = None
    homepage_url: str | None = None
    contact_email: str | None = None
    city: str | None = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=128)


class RoleGrantRequest(BaseModel):
    user_id: int
    role_code: str
    community_id: int | None = None
