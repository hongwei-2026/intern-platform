"""文件上传（PDF / 图片 / ZIP 交付件）。"""

from __future__ import annotations

import mimetypes
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

from intern_platform.config import PROJECT_ROOT
from intern_platform.db.session import get_db
from intern_platform.dependencies.auth import (
    AuthUser,
    _bearer,
    decode_token,
    get_current_user,
    load_user_roles,
)
from intern_platform.models.user import User
from sqlalchemy.orm import Session

router = APIRouter(prefix="/uploads", tags=["uploads"])

UPLOAD_ROOT = PROJECT_ROOT / "data" / "uploads"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
MAX_PDF_BYTES = 8 * 1024 * 1024
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_ZIP_BYTES = 100 * 1024 * 1024
MAX_VIDEO_BYTES = 40 * 1024 * 1024
MAX_FILE_BYTES = 20 * 1024 * 1024
FILE_EXTS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv", ".zip"}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
PUBLIC_MEDIA = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".webm")
IMAGE_MAGIC = (
    (b"\xff\xd8\xff", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
    (b"RIFF", ".webp"),
)


class UploadOut(BaseModel):
    url: str
    filename: str
    size: int


def _safe_name(name: str, *, force_ext: str | None = None) -> str:
    base = Path(name or "file").name
    base = re.sub(r"[^\w.\-]+", "_", base)
    if force_ext:
        stem = Path(base).stem or "file"
        base = f"{stem}{force_ext}"
    return base[:120]


def _detect_image_ext(raw: bytes, filename: str) -> str | None:
    for magic, ext in IMAGE_MAGIC:
        if raw.startswith(magic):
            if ext == ".webp":
                if len(raw) >= 12 and raw[8:12] == b"WEBP":
                    return ".webp"
                continue
            return ext
    suf = Path((filename or "").lower()).suffix
    if suf in IMAGE_EXTS:
        return suf
    return None


@router.post("/pdf", response_model=UploadOut)
async def upload_pdf(
    file: UploadFile = File(...),
    auth: AuthUser = Depends(get_current_user),
) -> UploadOut:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(raw) > MAX_PDF_BYTES:
        raise HTTPException(status_code=400, detail="PDF 不能超过 8MB")
    if not raw.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="文件不是有效 PDF")

    user_dir = UPLOAD_ROOT / f"u{auth.id}"
    user_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex[:12]}_{_safe_name(file.filename, force_ext='.pdf')}"
    path = user_dir / stored
    path.write_bytes(raw)
    rel = f"/api/v1/uploads/files/u{auth.id}/{stored}"
    return UploadOut(url=rel, filename=file.filename, size=len(raw))


@router.post("/image", response_model=UploadOut)
async def upload_image(
    file: UploadFile = File(...),
    auth: AuthUser = Depends(get_current_user),
) -> UploadOut:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="图片不能超过 5MB")
    ext = _detect_image_ext(raw, file.filename or "")
    if not ext:
        raise HTTPException(status_code=400, detail="仅支持 JPG / PNG / WebP / GIF")

    user_dir = UPLOAD_ROOT / f"u{auth.id}"
    user_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex[:12]}_{_safe_name(file.filename or f'image{ext}', force_ext=ext)}"
    path = user_dir / stored
    path.write_bytes(raw)
    rel = f"/api/v1/uploads/files/u{auth.id}/{stored}"
    return UploadOut(url=rel, filename=file.filename or stored, size=len(raw))


@router.post("/video", response_model=UploadOut)
async def upload_video(
    file: UploadFile = File(...),
    auth: AuthUser = Depends(get_current_user),
) -> UploadOut:
    raw = await file.read()
    name = (file.filename or "").lower()
    if not name.endswith((".mp4", ".webm")):
        raise HTTPException(status_code=400, detail="仅支持 MP4 / WebM")
    if len(raw) > MAX_VIDEO_BYTES:
        raise HTTPException(status_code=400, detail="视频不能超过 40MB")
    ext = ".webm" if name.endswith(".webm") else ".mp4"
    user_dir = UPLOAD_ROOT / f"u{auth.id}"
    user_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex[:12]}_video{ext}"
    (user_dir / stored).write_bytes(raw)
    return UploadOut(url=f"/api/v1/uploads/files/u{auth.id}/{stored}", filename=file.filename or stored, size=len(raw))


@router.post("/file", response_model=UploadOut)
async def upload_file(
    file: UploadFile = File(...),
    auth: AuthUser = Depends(get_current_user),
) -> UploadOut:
    name = file.filename or ""
    ext = Path(name).suffix.lower()
    if ext not in FILE_EXTS:
        raise HTTPException(status_code=400, detail="仅支持 PDF、Word、Excel、PPT、TXT、CSV、ZIP")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="文件不能超过 20MB")
    user_dir = UPLOAD_ROOT / f"u{auth.id}"
    user_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex[:12]}_{_safe_name(name, force_ext=ext)}"
    (user_dir / stored).write_bytes(raw)
    return UploadOut(url=f"/api/v1/uploads/files/u{auth.id}/{stored}", filename=name or stored, size=len(raw))


@router.post("/zip", response_model=UploadOut)
async def upload_zip(
    file: UploadFile = File(...),
    auth: AuthUser = Depends(get_current_user),
) -> UploadOut:
    """进展/验收交付件：ZIP（可含 PR 说明、Issue、截图等）。"""
    name = file.filename or ""
    if not name.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="只能上传 zip 文件格式")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(raw) > MAX_ZIP_BYTES:
        raise HTTPException(status_code=400, detail="文件最大不超过 100M")
    if not (
        raw.startswith(b"PK\x03\x04")
        or raw.startswith(b"PK\x05\x06")
        or raw.startswith(b"PK\x07\x08")
    ):
        raise HTTPException(status_code=400, detail="文件不是有效 ZIP")

    user_dir = UPLOAD_ROOT / f"u{auth.id}"
    user_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex[:12]}_{_safe_name(name, force_ext='.zip')}"
    path = user_dir / stored
    path.write_bytes(raw)
    rel = f"/api/v1/uploads/files/u{auth.id}/{stored}"
    return UploadOut(url=rel, filename=name, size=len(raw))


@router.get("/files/{user_part}/{filename}")
def get_uploaded_file(
    user_part: str,
    filename: str,
    access_token: str | None = Query(default=None),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> FileResponse:
    if not re.fullmatch(r"u\d+", user_part):
        raise HTTPException(status_code=404, detail="not found")
    if "/" in filename or ".." in filename or "\\" in filename:
        raise HTTPException(status_code=404, detail="文件不存在")
    path = (UPLOAD_ROOT / user_part / filename).resolve()
    if UPLOAD_ROOT.resolve() not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")

    lower = filename.lower()
    public_media = lower.endswith(PUBLIC_MEDIA)
    if not public_media:
        viewer = _viewer(db, credentials, access_token)
        if viewer is None:
            raise HTTPException(status_code=401, detail="请先登录后再下载")
        owner_id = int(user_part[1:])
        if not _can_download(db, viewer, owner_id):
            raise HTTPException(status_code=403, detail="无权下载该文件")

    media = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    disposition = "inline"
    if lower.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".webm")):
        if lower.endswith((".jpg", ".jpeg")):
            media = "image/jpeg"
        elif lower.endswith(".png"):
            media = "image/png"
        elif lower.endswith(".webp"):
            media = "image/webp"
        elif lower.endswith(".gif"):
            media = "image/gif"
    else:
        if lower.endswith(".pdf"):
            media = "application/pdf"
        elif lower.endswith(".zip"):
            media = "application/zip"
        disposition = "attachment"
    headers = {"X-Content-Type-Options": "nosniff"}
    if public_media:
        headers["Cache-Control"] = "public, max-age=3600"
    else:
        headers["Cache-Control"] = "private, no-store"
    return FileResponse(
        path,
        media_type=media,
        filename=filename,
        content_disposition_type=disposition,
        headers=headers,
    )


def _viewer(
    db: Session,
    credentials: HTTPAuthorizationCredentials | None,
    access_token: str | None,
) -> AuthUser | None:
    token = None
    if credentials is not None and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    elif access_token:
        token = access_token
    if not token:
        return None
    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub"))
    except Exception:
        return None
    user = db.get(User, user_id)
    if user is None:
        return None
    return AuthUser(user=user, roles=load_user_roles(db, user.id))


def _can_download(db: Session, viewer: AuthUser, owner_id: int) -> bool:
    """本人 / 组委会 / 名下课题导师 / 同社区管理员可下载。"""
    if viewer.id == owner_id:
        return True
    if viewer.has_role("committee"):
        return True

    from sqlalchemy import select

    from intern_platform.models.application import Application
    from intern_platform.models.project import Project

    if viewer.has_role("mentor"):
        linked = db.scalar(
            select(Application.id)
            .join(Project, Project.id == Application.project_id)
            .where(
                Project.mentor_id == viewer.id,
                Application.student_id == owner_id,
            )
            .limit(1)
        )
        if linked is not None:
            return True

    community_ids = viewer.community_ids_for("community_admin")
    if community_ids:
        linked = db.scalar(
            select(Application.id)
            .join(Project, Project.id == Application.project_id)
            .where(
                Project.community_id.in_(community_ids),
                Application.student_id == owner_id,
            )
            .limit(1)
        )
        if linked is not None:
            return True
        # 同社区其他管理员上传的结项材料等
        from intern_platform.models.role import Role, UserRole

        admin_role = db.scalar(select(Role).where(Role.code == "community_admin"))
        if admin_role is not None:
            peer = db.scalar(
                select(UserRole.id).where(
                    UserRole.user_id == owner_id,
                    UserRole.role_id == admin_role.id,
                    UserRole.community_id.in_(community_ids),
                ).limit(1)
            )
            if peer is not None:
                return True
    return False
