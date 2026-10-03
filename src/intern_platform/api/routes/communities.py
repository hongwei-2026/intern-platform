"""社区路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from intern_platform.db.session import get_db
from intern_platform.dependencies.auth import (
    AuthUser,
    get_current_user,
    get_optional_user,
    require_roles,
)
from intern_platform.dependencies.ledger import LedgerRequestContext, get_ledger_context
from intern_platform.schemas.business import (
    CommunityCreate,
    CommunityJoinOut,
    CommunityJoinRequest,
    CommunityMemberOut,
    CommunityOut,
    CommunityReviewRequest,
    CommunityUpdate,
    ExtensionOut,
    ExtensionUpdate,
    MentorCreateRequest,
)
from intern_platform.services.community_codec import community_to_out
from intern_platform.services.community_service import CommunityService

router = APIRouter(prefix="/communities", tags=["communities"])


@router.get("", response_model=list[CommunityOut])
def list_communities(
    status: str | None = Query(default="approved"),
    auth: AuthUser | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> list[CommunityOut]:
    wanted = (status or "approved").strip().lower()
    if wanted != "approved" and (auth is None or not auth.has_role("committee")):
        raise HTTPException(status_code=403, detail="未公开的社区列表仅组委会可查看")
    rows = CommunityService(db).list_communities(status=wanted)
    # 组织码不对外公开列表暴露
    return [community_to_out(r, include_invite=False) for r in rows]


@router.post("/join", response_model=CommunityJoinOut)
def join_community(
    body: CommunityJoinRequest,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CommunityJoinOut:
    try:
        return CommunityService(db).join_with_invite(auth, body)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/mine", response_model=list[CommunityOut])
def my_communities(
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CommunityOut]:
    rows = CommunityService(db).list_mine(auth)
    return [community_to_out(r) for r in rows]


@router.get("/admin-of", response_model=list[CommunityOut])
def communities_i_admin(
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CommunityOut]:
    """社区管理员：只返回自己管理的社区（一人一社为主）。"""
    if not auth.has_role("community_admin", "committee"):
        raise HTTPException(status_code=403, detail="仅社区管理员可访问")
    # 组委会不走组织台「管理本社」语义；返回空，避免做成全站组织列表
    if auth.has_role("committee") and not auth.community_ids_for("community_admin"):
        return []
    rows = CommunityService(db).list_admin_of(auth)
    return [community_to_out(r) for r in rows]


@router.post(
    "/{community_id:int}/mentors",
    response_model=CommunityMemberOut,
    status_code=201,
)
def create_community_mentor(
    community_id: int,
    body: MentorCreateRequest,
    auth: AuthUser = Depends(require_roles("community_admin", "committee")),
    db: Session = Depends(get_db),
    ledger: LedgerRequestContext = Depends(get_ledger_context),
) -> CommunityMemberOut:
    try:
        row = CommunityService(db).create_mentor(
            auth,
            community_id,
            email=body.email,
            password=body.password,
            display_name=body.display_name,
            ledger=ledger,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CommunityMemberOut.model_validate(row)


@router.get("/{slug}", response_model=CommunityOut)
def get_community(slug: str, db: Session = Depends(get_db)) -> CommunityOut:
    row = CommunityService(db).get_by_slug(slug)
    if row is None:
        raise HTTPException(status_code=404, detail="社区不存在")
    # 公开详情不暴露组织码
    return community_to_out(row, include_invite=False)


@router.post("", response_model=CommunityOut, status_code=201)
def create_community(
    body: CommunityCreate,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CommunityOut:
    try:
        row = CommunityService(db).create(auth, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return community_to_out(row)


@router.patch("/{community_id:int}", response_model=CommunityOut)
def update_community(
    community_id: int,
    body: CommunityUpdate,
    auth: AuthUser = Depends(require_roles("community_admin", "committee")),
    db: Session = Depends(get_db),
) -> CommunityOut:
    try:
        row = CommunityService(db).update_profile(
            auth,
            community_id,
            name=body.name,
            description=body.description,
            homepage_url=body.homepage_url,
            mirror_doc_url=body.mirror_doc_url,
            gitea_org_url=body.gitea_org_url,
            logo_url=body.logo_url,
            tags=body.tags,
            intro_body=body.intro_body,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return community_to_out(row)


@router.post("/{community_id}/review", response_model=CommunityOut)
def review_community(
    community_id: int,
    body: CommunityReviewRequest,
    auth: AuthUser = Depends(require_roles("committee")),
    db: Session = Depends(get_db),
    ledger: LedgerRequestContext = Depends(get_ledger_context),
) -> CommunityOut:
    try:
        row = CommunityService(db).review(auth, community_id, body, ledger)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return community_to_out(row)


@router.get("/{community_id}/members", response_model=list[CommunityMemberOut])
def list_community_members(
    community_id: int,
    role: str | None = Query(default="mentor"),
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CommunityMemberOut]:
    try:
        rows = CommunityService(db).list_members(auth, community_id, role_code=role)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [CommunityMemberOut.model_validate(r) for r in rows]


@router.get("/{community_id}/extension", response_model=ExtensionOut)
def get_extension(
    community_id: int,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExtensionOut:
    svc = CommunityService(db)
    community = svc.get(community_id)
    if community is None:
        raise HTTPException(status_code=404, detail="社区不存在")
    if not (
        auth.has_role("committee")
        or auth.has_community_role("community_admin", community_id)
    ):
        raise HTTPException(status_code=403, detail="无权查看扩展配置")
    ext = svc.get_extension(community_id)
    if ext is None:
        raise HTTPException(status_code=404, detail="扩展不存在")
    return ExtensionOut.model_validate(ext)


@router.put("/{community_id}/extension", response_model=ExtensionOut)
def put_extension(
    community_id: int,
    body: ExtensionUpdate,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExtensionOut:
    try:
        ext = CommunityService(db).upsert_extension(auth, community_id, body)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ExtensionOut.model_validate(ext)
