"""上传附件 URL 白名单：只允许本站相对路径，并可绑定上传者目录。"""

from __future__ import annotations

UPLOAD_URL_PREFIX = "/api/v1/uploads/files/"


def is_safe_upload_url(
    url: str | None,
    *,
    allow_empty: bool = True,
    owner_user_id: int | None = None,
) -> bool:
    if url is None:
        return allow_empty
    value = str(url).strip()
    if not value:
        return allow_empty
    lower = value.lower()
    if lower.startswith("javascript:") or lower.startswith("data:"):
        return False
    if "://" in value or value.startswith("//"):
        return False
    if not value.startswith(UPLOAD_URL_PREFIX):
        return False
    rest = value[len(UPLOAD_URL_PREFIX) :]
    if not rest or ".." in rest or "\\" in rest or rest.startswith("/"):
        return False
    if owner_user_id is not None:
        expected = f"u{int(owner_user_id)}/"
        if not rest.startswith(expected):
            return False
    return True


def require_safe_upload_url(
    url: str | None,
    *,
    field: str = "附件",
    owner_user_id: int | None = None,
) -> str | None:
    if url is None:
        return None
    value = str(url).strip()
    if not value:
        return None
    if not is_safe_upload_url(value, allow_empty=False, owner_user_id=owner_user_id):
        if owner_user_id is not None and value.startswith(UPLOAD_URL_PREFIX):
            raise ValueError(f"{field}只能使用本人上传的文件")
        raise ValueError(f"{field}只允许本站上传路径（{UPLOAD_URL_PREFIX}…）")
    return value


def sanitize_upload_fields(
    *,
    attachment_url: str | None = None,
    extra_fields: dict | None = None,
    owner_user_id: int | None = None,
) -> tuple[str | None, dict | None]:
    safe_attachment = require_safe_upload_url(
        attachment_url, field="附件", owner_user_id=owner_user_id
    )
    if extra_fields is None:
        return safe_attachment, None
    cleaned = dict(extra_fields)
    for key in ("resume_pdf", "design_pdf"):
        if key in cleaned and cleaned[key] is not None:
            cleaned[key] = require_safe_upload_url(
                str(cleaned[key]), field=key, owner_user_id=owner_user_id
            )
    return safe_attachment, cleaned
