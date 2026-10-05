"""OAuth 绑定：state 签发、回调落库、本地 Client 覆盖配置。"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from intern_platform.config import PROJECT_ROOT, Settings, get_settings
from intern_platform.dependencies.auth import ALGORITHM, AuthUser, load_user_roles
from intern_platform.models.user import User
from intern_platform.schemas.auth import UserOut
from intern_platform.services.auth_service import user_to_out
from intern_platform.services.oauth_providers import (
    OAuthProvider,
    exchange_code,
    extract_github,
    extract_gitee_like,
    extract_gitlab_like,
    fetch_profile,
    fetch_profile_with_pat,
)

# 单进程一次性 state 消费（云端单 API 容器足够；多副本需共享存储）
_used_states: dict[str, float] = {}
_used_lock = threading.Lock()
_STATE_TTL_SEC = 600

OAUTH_CLIENTS_PATH = PROJECT_ROOT / "data" / "oauth_clients.json"

PROVIDER_DOCS: dict[str, dict[str, str]] = {
    "github": {
        "create_url": "https://github.com/settings/applications/new",
        "hint": "GitHub → Settings → Developer settings → OAuth Apps → New OAuth App",
    },
    "gitee": {
        "create_url": "https://gitee.com/oauth/applications/new",
        "hint": "Gitee → 设置 → 第三方应用 → 创建应用",
    },
    "gitcode": {
        # 普通账号访问 /setting/applications 会 404/无权限，不要再引导点进去
        "create_url": "",
        "hint": "GitCode 个人账号目前打不开「创建 OAuth 应用」页（404/无权限）。若俱乐部已有 Client ID/Secret 可直接粘贴；否则请先开通 GitHub/Gitee。",
    },
    "gitlink": {
        # 首页无创建入口；需登录后进个人设置找「应用 / Applications」
        "create_url": "https://www.gitlink.org.cn/login",
        "hint": "登录 GitLink → 右上角头像 → 设置 → 应用（Applications）→ 新建 OAuth 应用。回调地址粘贴本页第 2 步（须完全一致）；权限勾选 read_user。把 Application ID / Secret 填回第 3 步保存。找不到「应用」入口可先用已开通的 Gitee，或联系 gitlink@ccf.org.cn。",
    },
    "gitea": {
        # git.hust.openatom.club 当前公网无法解析，勿再引导外链
        "create_url": "",
        "hint": "俱乐部 Gitea（git.hust.openatom.club）当前公网无法访问，可能仅校园网/内网可用。能打开时再在「设置 → 应用」创建 OAuth2；若已有 Client ID/密钥可直接粘贴保存。",
    },
}


def load_client_overrides() -> dict[str, dict[str, str]]:
    if not OAUTH_CLIENTS_PATH.exists():
        return {}
    try:
        raw = json.loads(OAUTH_CLIENTS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for key, val in raw.items():
        if isinstance(val, dict):
            cid = str(val.get("client_id") or "").strip()
            secret = str(val.get("client_secret") or "").strip()
            if cid and secret:
                out[str(key)] = {"client_id": cid, "client_secret": secret}
    return out


def save_client_override(provider: str, client_id: str, client_secret: str) -> None:
    OAUTH_CLIENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if OAUTH_CLIENTS_PATH.exists():
        try:
            data = json.loads(OAUTH_CLIENTS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
    if not isinstance(data, dict):
        data = {}
    data[provider] = {
        "client_id": client_id.strip(),
        "client_secret": client_secret.strip(),
    }
    OAUTH_CLIENTS_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _creds(settings: Settings, key: str, env_id: str, env_secret: str) -> tuple[str, str]:
    overrides = load_client_overrides().get(key)
    if overrides:
        return overrides["client_id"], overrides["client_secret"]
    return env_id, env_secret


def build_providers(settings: Settings | None = None) -> dict[str, OAuthProvider]:
    s = settings or get_settings()
    gitea_base = s.gitea_base_url.rstrip("/")
    gh_id, gh_sec = _creds(s, "github", s.github_client_id, s.github_client_secret)
    ge_id, ge_sec = _creds(s, "gitee", s.gitee_client_id, s.gitee_client_secret)
    gc_id, gc_sec = _creds(s, "gitcode", s.gitcode_client_id, s.gitcode_client_secret)
    gl_id, gl_sec = _creds(s, "gitlink", s.gitlink_client_id, s.gitlink_client_secret)
    ga_id, ga_sec = _creds(s, "gitea", s.gitea_client_id, s.gitea_client_secret)
    return {
        "github": OAuthProvider(
            key="github",
            name="GitHub",
            user_field="github_id",
            authorize_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            userinfo_url="https://api.github.com/user",
            scope="read:user",
            client_id=gh_id,
            client_secret=gh_sec,
            login_extractor=extract_github,
        ),
        "gitee": OAuthProvider(
            key="gitee",
            name="Gitee",
            user_field="gitee_id",
            authorize_url="https://gitee.com/oauth/authorize",
            token_url="https://gitee.com/oauth/token",
            userinfo_url="https://gitee.com/api/v5/user",
            scope="user_info",
            client_id=ge_id,
            client_secret=ge_sec,
            login_extractor=extract_gitee_like,
        ),
        "gitcode": OAuthProvider(
            key="gitcode",
            name="GitCode",
            user_field="gitcode_id",
            authorize_url="https://gitcode.com/oauth/authorize",
            token_url="https://gitcode.com/oauth/token",
            userinfo_url="https://api.gitcode.com/api/v5/user",
            scope="user_info",
            client_id=gc_id,
            client_secret=gc_sec,
            login_extractor=extract_gitee_like,
        ),
        "gitlink": OAuthProvider(
            key="gitlink",
            name="GitLink",
            user_field="gitlink_id",
            authorize_url="https://www.gitlink.org.cn/oauth/authorize",
            token_url="https://www.gitlink.org.cn/oauth/token",
            userinfo_url="https://www.gitlink.org.cn/api/v4/user",
            scope="read_user",
            client_id=gl_id,
            client_secret=gl_sec,
            login_extractor=extract_gitlab_like,
        ),
        "gitea": OAuthProvider(
            key="gitea",
            name="俱乐部 Gitea",
            user_field="gitea_id",
            authorize_url=f"{gitea_base}/login/oauth/authorize",
            token_url=f"{gitea_base}/login/oauth/access_token",
            userinfo_url=f"{gitea_base}/api/v1/user",
            scope="read:user",
            client_id=ga_id,
            client_secret=ga_sec,
            login_extractor=extract_github,
        ),
    }


def get_provider(key: str, settings: Settings | None = None) -> OAuthProvider | None:
    return build_providers(settings).get(key)


def callback_uri(provider_key: str, settings: Settings | None = None) -> str:
    s = settings or get_settings()
    base = s.public_api_base.rstrip("/")
    prefix = s.api_prefix.rstrip("/")
    return f"{base}{prefix}/auth/oauth/{provider_key}/callback"


def create_oauth_state(*, user_id: int, provider: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=10)
    payload = {
        "typ": "oauth_bind",
        "sub": str(user_id),
        "provider": provider,
        "jti": uuid.uuid4().hex,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_oauth_bind_cookie(*, user_id: int) -> str:
    """发起绑定时写入的短时会话 cookie，回调时与 state.sub 交叉校验。"""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=10)
    payload = {
        "typ": "oauth_bind_sess",
        "sub": str(user_id),
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def parse_oauth_bind_cookie(cookie: str | None) -> int:
    if not cookie:
        raise ValueError("缺少绑定会话，请重新从本站发起授权")
    settings = get_settings()
    try:
        payload = jwt.decode(cookie, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError("绑定会话无效或已过期，请重新发起授权") from exc
    if payload.get("typ") != "oauth_bind_sess":
        raise ValueError("绑定会话无效")
    return int(payload["sub"])


def parse_oauth_state(state: str) -> dict[str, Any]:
    payload = decode_oauth_state(state)
    if payload.get("typ") != "oauth_bind":
        raise ValueError("无效 OAuth state")
    return payload


def decode_oauth_state(state: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(state, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError("OAuth state 无效或已过期") from exc


def consume_oauth_state(state: str) -> dict[str, Any]:
    """解析并一次性消费 state，防止重放。"""
    payload = parse_oauth_state(state)
    key = hashlib.sha256(state.encode("utf-8")).hexdigest()
    now = time.time()
    with _used_lock:
        stale = [k for k, ts in _used_states.items() if now - ts > _STATE_TTL_SEC]
        for k in stale:
            _used_states.pop(k, None)
        if key in _used_states:
            raise ValueError("OAuth state 已使用，请重新发起授权")
        _used_states[key] = now
    return payload


def build_authorize_url(provider: OAuthProvider, state: str, settings: Settings | None = None) -> str:
    s = settings or get_settings()
    params = {
        "client_id": provider.client_id,
        "redirect_uri": callback_uri(provider.key, s),
        "response_type": "code",
        "scope": provider.scope,
        "state": state,
    }
    sep = "&" if "?" in provider.authorize_url else "?"
    return f"{provider.authorize_url}{sep}{urlencode(params)}"


def _read_avatars(user: User) -> dict[str, str]:
    raw = getattr(user, "oauth_avatars", None) or ""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if isinstance(v, str) and v}


def _write_avatar(user: User, provider: str, avatar_url: str | None) -> None:
    avatars = _read_avatars(user)
    if avatar_url:
        avatars[provider] = avatar_url
    else:
        avatars.pop(provider, None)
    user.oauth_avatars = json.dumps(avatars, ensure_ascii=False) if avatars else None


def bind_login(
    db: Session,
    user: User,
    field: str,
    login: str,
    *,
    provider: str | None = None,
    avatar_url: str | None = None,
) -> UserOut:
    login = (login or "").strip()
    if not login:
        raise ValueError("平台账号为空，无法绑定")
    col = getattr(User, field, None)
    if col is None:
        raise ValueError("不支持的绑定字段")
    taken = db.scalar(select(User).where(col == login, User.id != user.id))
    if taken is not None:
        label = provider or field
        raise ValueError(f"该{label}账号已绑定其他用户")
    setattr(user, field, login)
    if provider:
        _write_avatar(user, provider, avatar_url)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user_to_out(user, load_user_roles(db, user.id))


def unbind_field(db: Session, user: User, field: str, provider: str | None = None) -> UserOut:
    setattr(user, field, None)
    if provider:
        _write_avatar(user, provider, None)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user_to_out(user, load_user_roles(db, user.id))


async def complete_oauth_bind(
    db: Session,
    *,
    provider: OAuthProvider,
    code: str,
    state: str,
    bind_cookie: str | None = None,
) -> tuple[UserOut, str]:
    payload = consume_oauth_state(state)
    if payload.get("provider") != provider.key:
        raise ValueError("OAuth state 与平台不匹配")
    user_id = int(payload["sub"])
    cookie_uid = parse_oauth_bind_cookie(bind_cookie)
    if cookie_uid != user_id:
        raise ValueError("绑定会话与授权发起人不一致")
    user = db.get(User, user_id)
    if user is None:
        raise LookupError("用户不存在")

    settings = get_settings()
    token = await exchange_code(
        provider,
        code=code,
        redirect_uri=callback_uri(provider.key, settings),
    )
    profile = await fetch_profile(provider, token)
    out = bind_login(
        db,
        user,
        provider.user_field,
        profile.login,
        provider=provider.key,
        avatar_url=profile.avatar_url,
    )
    return out, profile.login


async def complete_pat_bind(
    db: Session,
    auth: AuthUser,
    *,
    provider: OAuthProvider,
    pat: str,
) -> tuple[UserOut, str]:
    profile = await fetch_profile_with_pat(provider, pat)
    out = bind_login(
        db,
        auth.user,
        provider.user_field,
        profile.login,
        provider=provider.key,
        avatar_url=profile.avatar_url,
    )
    return out, profile.login


def frontend_bind_redirect(
    *,
    provider: str,
    ok: bool,
    login: str | None = None,
    error: str | None = None,
) -> str:
    settings = get_settings()
    base = settings.frontend_base.rstrip("/")
    q: dict[str, str] = {"tab": "bindings", "bind": provider}
    if ok:
        q["bind_ok"] = "1"
        if login:
            q["login"] = login
    else:
        q["bind_ok"] = "0"
        if error:
            # 仅 ASCII 安全：urlencode 会处理中文；避免把原始异常塞爆 URL
            q["bind_err"] = error[:180]
    return f"{base}/me?{urlencode(q)}"
