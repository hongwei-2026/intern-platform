"""文件上传（PDF / 图片 / ZIP 交付件）。"""

from __future__ import annotations

import mimetypes
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from intern_platform.config import PROJECT_ROOT
from intern_platform.dependencies.auth import AuthUser, get_current_user

router = APIRouter(prefix="/uploads", tags=["uploads"])

UPLOAD_ROOT = PROJECT_ROOT / "data" / "uploads"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
MAX_PDF_BYTES = 8 * 1024 * 1024
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_ZIP_BYTES = 100 * 1024 * 1024

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
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
def get_uploaded_file(user_part: str, filename: str) -> FileResponse:
    if not re.fullmatch(r"u\d+", user_part):
        raise HTTPException(status_code=404, detail="not found")
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=404, detail="文件不存在")
    path = UPLOAD_ROOT / user_part / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")

    media = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    lower = filename.lower()
    disposition = "inline"
    if lower.endswith(".pdf"):
        media = "application/pdf"
    elif lower.endswith((".jpg", ".jpeg")):
        media = "image/jpeg"
    elif lower.endswith(".png"):
        media = "image/png"
    elif lower.endswith(".webp"):
        media = "image/webp"
    elif lower.endswith(".gif"):
        media = "image/gif"
    elif lower.endswith(".zip"):
        media = "application/zip"
        disposition = "attachment"
    return FileResponse(
        path,
        media_type=media,
        filename=filename,
        content_disposition_type=disposition,
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
            "Access-Control-Allow-Origin": "*",
        },
    )
