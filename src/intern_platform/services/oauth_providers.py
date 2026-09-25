"""第三方平台 OAuth2 Authorization Code 配置。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import httpx


@dataclass(frozen=True)
class OAuthProvider:
    key: str
    name: str
    user_field: str  # User 模型字段名，如 github_id
    authorize_url: str
    token_url: str
    userinfo_url: str
    scope: str
    client_id: str
    client_secret: str
    # token 交换是否用 JSON body（GitHub 用 form + Accept json）
    token_as_form: bool = True
    # 从 userinfo JSON 提取登录名
    login_extractor: Callable[[dict[str, Any]], str | None] | None = None

    @property
    def configured(self) -> bool:
        return bool(self.client_id.strip() and self.client_secret.strip())


def _login(data: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def extract_github(data: dict[str, Any]) -> str | None:
    return _login(data, "login")


def extract_gitee_like(data: dict[str, Any]) -> str | None:
    return _login(data, "login", "username", "name")


def extract_gitlab_like(data: dict[str, Any]) -> str | None:
    return _login(data, "username", "login", "name")


@dataclass(frozen=True)
class OAuthProfile:
    login: str
    avatar_url: str | None = None


def extract_avatar(data: dict[str, Any]) -> str | None:
    for key in ("avatar_url", "avatar", "portrait", "head_img", "photo"):
        val = data.get(key)
        if isinstance(val, str) and val.startswith(("http://", "https://")):
            return val
    return None


async def exchange_code(
    provider: OAuthProvider,
    *,
    code: str,
    redirect_uri: str,
) -> str:
    """用 authorization code 换 access_token。"""
    headers = {"Accept": "application/json"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        if provider.key == "gitcode":
            # GitCode: grant_type/code/client_id 走 query，secret 走 form
            url = (
                f"{provider.token_url}"
                f"?grant_type=authorization_code"
                f"&code={code}"
                f"&client_id={provider.client_id}"
            )
            resp = await client.post(
                url,
                data={"client_secret": provider.client_secret, "redirect_uri": redirect_uri},
                headers=headers,
            )
        elif provider.token_as_form:
            payload = {
                "client_id": provider.client_id,
                "client_secret": provider.client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            }
            resp = await client.post(provider.token_url, data=payload, headers=headers)
        else:
            payload = {
                "client_id": provider.client_id,
                "client_secret": provider.client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            }
            resp = await client.post(provider.token_url, json=payload, headers=headers)
        if resp.status_code >= 400:
            raise ValueError(f"{provider.name} 换 token 失败：{resp.text[:300]}")
        data = resp.json()
    token = data.get("access_token")
    if not token:
        raise ValueError(f"{provider.name} 未返回 access_token：{data}")
    return str(token)


async def fetch_profile(provider: OAuthProvider, access_token: str) -> OAuthProfile:
    """拉取平台用户登录名与头像。"""
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
        "User-Agent": "intern-platform-oauth",
    }
    params: dict[str, str] = {}
    if provider.key == "gitee":
        params["access_token"] = access_token
        headers.pop("Authorization", None)

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(provider.userinfo_url, headers=headers, params=params or None)
        if resp.status_code >= 400:
            raise ValueError(f"{provider.name} 拉用户信息失败：{resp.text[:300]}")
        data = resp.json()

    raw = data if isinstance(data, dict) else {}
    extractor = provider.login_extractor or extract_gitee_like
    login = extractor(raw)
    if not login:
        raise ValueError(f"无法从 {provider.name} 用户信息解析登录名")
    return OAuthProfile(login=login, avatar_url=extract_avatar(raw))


async def fetch_profile_with_pat(provider: OAuthProvider, pat: str) -> OAuthProfile:
    """用个人访问令牌拉取资料（GitCode OAuth 应用页不可用时的官方替代方案）。"""
    token = pat.strip()
    if not token:
        raise ValueError("访问令牌不能为空")

    attempts: list[dict[str, str]] = [
        {"Authorization": f"Bearer {token}"},
        {"PRIVATE-TOKEN": token},
    ]
    last_err = "未知错误"
    async with httpx.AsyncClient(timeout=30.0) as client:
        for auth_headers in attempts:
            headers = {
                "Accept": "application/json",
                "User-Agent": "intern-platform-oauth",
                **auth_headers,
            }
            params: dict[str, str] | None = None
            if provider.key == "gitee":
                params = {"access_token": token}
                headers = {"Accept": "application/json", "User-Agent": "intern-platform-oauth"}
            resp = await client.get(provider.userinfo_url, headers=headers, params=params)
            if resp.status_code < 400:
                data = resp.json()
                raw = data if isinstance(data, dict) else {}
                extractor = provider.login_extractor or extract_gitee_like
                login = extractor(raw)
                if not login:
                    raise ValueError(f"无法从 {provider.name} 用户信息解析登录名")
                return OAuthProfile(login=login, avatar_url=extract_avatar(raw))
            last_err = resp.text[:200]

    raise ValueError(f"{provider.name} 令牌无效或权限不足：{last_err}")


async def fetch_login(provider: OAuthProvider, access_token: str) -> str:
    return (await fetch_profile(provider, access_token)).login
