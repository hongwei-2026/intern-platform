"""鉴权路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from intern_platform.db.session import get_db
from intern_platform.dependencies.auth import AuthUser, get_current_user, load_user_roles, require_roles
from intern_platform.dependencies.ledger import LedgerRequestContext, get_ledger_context
from intern_platform.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    RoleGrantRequest,
    TokenResponse,
    UserOut,
    UserUpdateRequest,
)
from intern_platform.schemas.business import MentorRegisterRequest
from intern_platform.services.auth_service import AuthService, user_to_out

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(
    body: RegisterRequest,
    db: Session = Depends(get_db),
    ledger: LedgerRequestContext = Depends(get_ledger_context),
) -> TokenResponse:
    try:
        return AuthService(db).register(body, ledger)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/register-mentor", response_model=TokenResponse)
def register_mentor(
    body: MentorRegisterRequest,
    db: Session = Depends(get_db),
    ledger: LedgerRequestContext = Depends(get_ledger_context),
) -> TokenResponse:
    try:
        return AuthService(db).register_mentor(
            email=body.email,
            password=body.password,
            display_name=body.display_name,
            invite_code=body.invite_code,
            ledger=ledger,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    db: Session = Depends(get_db),
    ledger: LedgerRequestContext = Depends(get_ledger_context),
) -> TokenResponse:
    try:
        return AuthService(db).login(body, ledger)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/me", response_model=UserOut)
def me(auth: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)) -> UserOut:
    bindings = load_user_roles(db, auth.id)
    return user_to_out(auth.user, bindings)


@router.patch("/me", response_model=UserOut)
def patch_me(
    body: UserUpdateRequest,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    return AuthService(db).update_me(auth, body)


@router.post("/me/password")
def change_password(
    body: ChangePasswordRequest,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    try:
        AuthService(db).change_password(auth, body)
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}

@router.post("/roles", response_model=UserOut)
def grant_role(
    body: RoleGrantRequest,
    auth: AuthUser = Depends(require_roles("committee")),
    db: Session = Depends(get_db),
    ledger: LedgerRequestContext = Depends(get_ledger_context),
) -> UserOut:
    try:
        return AuthService(db).grant_role(auth, body, ledger)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
