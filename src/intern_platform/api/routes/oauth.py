"""第三方平台 OAuth 绑定路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from intern_platform.config import get_settings
from intern_platform.db.session import get_db
from intern_platform.dependencies.auth import AuthUser, get_current_user, require_roles
from intern_platform.schemas.auth import UserOut
from intern_platform.services import oauth_service as oauth

router = APIRouter(prefix="/auth/oauth", tags=["oauth"])

OAUTH_BIND_COOKIE = "oauth_bind_sess"


class OAuthProviderStatus(BaseModel):
    key: str
    name: str
    configured: bool
    mode: str = Field(description="real | setup | unavailable")
    callback_uri: str = ""
    create_url: str = ""
    hint: str = ""


class OAuthStartResponse(BaseModel):
    provider: str
    mode: str
    authorize_url: str
    state: str
    callback_uri: str = ""
    create_url: str = ""
    hint: str = ""


class SaveClientRequest(BaseModel):
    client_id: str = Field(min_length=4, max_length=256)
    client_secret: str = Field(min_length=4, max_length=256)


class PatBindRequest(BaseModel):
    token: str = Field(min_length=8, max_length=512)


def _set_bind_cookie(response: Response, user_id: int) -> None:
    settings = get_settings()
    secure = settings.public_api_base.startswith("https://")
    response.set_cookie(
        key=OAUTH_BIND_COOKIE,
        value=oauth.create_oauth_bind_cookie(user_id=user_id),
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )


def _clear_bind_cookie(response: Response) -> None:
    settings = get_settings()
    secure = settings.public_api_base.startswith("https://")
    response.delete_cookie(
        key=OAUTH_BIND_COOKIE,
        path="/",
        httponly=True,
        samesite="lax",
        secure=secure,
    )


@router.get("/providers", response_model=list[OAuthProviderStatus])
def list_providers() -> list[OAuthProviderStatus]:
    settings = get_settings()
    out: list[OAuthProviderStatus] = []
    for key, p in oauth.build_providers(settings).items():
        docs = oauth.PROVIDER_DOCS.get(key, {})
        if p.configured:
            mode = "real"
        else:
            mode = "unavailable"
        out.append(
            OAuthProviderStatus(
                key=key,
                name=p.name,
                configured=p.configured,
                mode=mode,
                callback_uri=oauth.callback_uri(key, settings),
                create_url=docs.get("create_url", ""),
                hint=docs.get("hint", ""),
            )
        )
    return out


@router.get("/{provider}/start", response_model=OAuthStartResponse)
def oauth_start(
    provider: str,
    response: Response,
    auth: AuthUser = Depends(get_current_user),
) -> OAuthStartResponse:
    settings = get_settings()
    p = oauth.get_provider(provider, settings)
    if p is None:
        raise HTTPException(status_code=404, detail="不支持的平台")

    docs = oauth.PROVIDER_DOCS.get(p.key, {})
    state = oauth.create_oauth_state(user_id=auth.id, provider=p.key)
    cb = oauth.callback_uri(p.key, settings)
    _set_bind_cookie(response, auth.id)

    if p.configured:
        url = oauth.build_authorize_url(p, state, settings)
        return OAuthStartResponse(
            provider=p.key,
            mode="real",
            authorize_url=url,
            state=state,
            callback_uri=cb,
            create_url=docs.get("create_url", ""),
            hint=docs.get("hint", ""),
        )

    # 用户侧不跳转开发者配置页；返回 unavailable，由前端展示「暂未开通」
    return OAuthStartResponse(
        provider=p.key,
        mode="unavailable",
        authorize_url="",
        state=state,
        callback_uri=cb,
        create_url=docs.get("create_url", ""),
        hint=docs.get("hint", ""),
    )


@router.delete("/{provider}/bind", response_model=UserOut)
def oauth_unbind(
    provider: str,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    settings = get_settings()
    p = oauth.get_provider(provider, settings)
    if p is None:
        raise HTTPException(status_code=404, detail="不支持的平台")
    return oauth.unbind_field(db, auth.user, p.user_field, provider=p.key)


@router.post("/{provider}/pat", response_model=UserOut)
async def bind_with_pat(
    provider: str,
    body: PatBindRequest,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    """用个人访问令牌绑定（不落库令牌，仅拉取用户名/头像）。"""
    settings = get_settings()
    p = oauth.get_provider(provider, settings)
    if p is None:
        raise HTTPException(status_code=404, detail="不支持的平台")
    if p.key not in {"gitcode", "gitee", "github", "gitea", "gitlink"}:
        raise HTTPException(status_code=400, detail="该平台不支持令牌绑定")
    try:
        out, _login = await oauth.complete_pat_bind(db, auth, provider=p, pat=body.token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return out


@router.post("/{provider}/client")
def save_oauth_client(
    provider: str,
    body: SaveClientRequest,
    auth: AuthUser = Depends(require_roles("committee")),
) -> dict[str, object]:
    """组委会配置平台级 OAuth Client：全体用户可一键官方授权。"""
    _ = auth
    settings = get_settings()
    p = oauth.get_provider(provider, settings)
    if p is None:
        raise HTTPException(status_code=404, detail="不支持的平台")
    oauth.save_client_override(p.key, body.client_id, body.client_secret)
    refreshed = oauth.get_provider(p.key, settings)
    return {
        "ok": True,
        "provider": p.key,
        "configured": bool(refreshed and refreshed.configured),
        "callback_uri": oauth.callback_uri(p.key, settings),
    }


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    settings = get_settings()
    p = oauth.get_provider(provider, settings)
    if p is None:
        return RedirectResponse(
            oauth.frontend_bind_redirect(provider=provider, ok=False, error="unsupported_provider"),
            status_code=302,
        )
    if error:
        msg = error_description or error
        resp = RedirectResponse(
            oauth.frontend_bind_redirect(provider=p.key, ok=False, error=msg),
            status_code=302,
        )
        _clear_bind_cookie(resp)
        return resp
    if not code or not state:
        resp = RedirectResponse(
            oauth.frontend_bind_redirect(provider=p.key, ok=False, error="missing_code_or_state"),
            status_code=302,
        )
        _clear_bind_cookie(resp)
        return resp
    bind_cookie = request.cookies.get(OAUTH_BIND_COOKIE)
    try:
        _out, login = await oauth.complete_oauth_bind(
            db,
            provider=p,
            code=code,
            state=state,
            bind_cookie=bind_cookie,
        )
    except Exception as exc:  # noqa: BLE001
        resp = RedirectResponse(
            oauth.frontend_bind_redirect(provider=p.key, ok=False, error=str(exc)),
            status_code=302,
        )
        _clear_bind_cookie(resp)
        return resp
    resp = RedirectResponse(
        oauth.frontend_bind_redirect(provider=p.key, ok=True, login=login),
        status_code=302,
    )
    _clear_bind_cookie(resp)
    return resp
