"""社区对外字段编解码：tags / intro_body。"""

from __future__ import annotations

import json
from typing import Any

from intern_platform.models.community import Community
from intern_platform.schemas.business import CommunityOut

ALLOWED_BLOCK_TYPES = frozenset({"paragraph", "heading", "image", "table", "video"})
MAX_TAGS = 12
MAX_TAG_LEN = 24
MAX_BLOCKS = 40


def parse_tags(raw: str | list[str] | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        items = raw
    else:
        text = str(raw).strip()
        if not text:
            return []
        try:
            data = json.loads(text)
            items = data if isinstance(data, list) else []
        except json.JSONDecodeError:
            items = [s.strip() for s in text.replace("，", ",").split(",") if s.strip()]
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        tag = str(item).strip()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        out.append(tag[:MAX_TAG_LEN])
        if len(out) >= MAX_TAGS:
            break
    return out


def dumps_tags(tags: list[str] | None) -> str | None:
    cleaned = parse_tags(tags)
    if not cleaned:
        return None
    return json.dumps(cleaned, ensure_ascii=False)


def _clean_block(raw: dict[str, Any]) -> dict[str, Any] | None:
    btype = str(raw.get("type") or "").strip()
    if btype not in ALLOWED_BLOCK_TYPES:
        return None
    bid = str(raw.get("id") or "")[:40]
    if btype in ("paragraph", "heading"):
        text = str(raw.get("text") or "").strip()
        if not text:
            return None
        return {"id": bid, "type": btype, "text": text[:8000]}
    if btype == "image":
        url = str(raw.get("url") or "").strip()
        if not url:
            return None
        return {
            "id": bid,
            "type": "image",
            "url": url[:1024],
            "caption": str(raw.get("caption") or "").strip()[:200],
        }
    if btype == "video":
        url = str(raw.get("url") or "").strip()
        if not url:
            return None
        return {"id": bid, "type": "video", "url": url[:1024]}
    if btype == "table":
        headers = [str(h).strip()[:80] for h in (raw.get("headers") or [])][:12]
        rows_in = raw.get("rows") or []
        rows: list[list[str]] = []
        if isinstance(rows_in, list):
            for row in rows_in[:30]:
                if not isinstance(row, list):
                    continue
                rows.append([str(c).strip()[:200] for c in row[:12]])
        if not headers and not rows:
            return None
        return {"id": bid, "type": "table", "headers": headers, "rows": rows}
    return None


def parse_intro_body(raw: str | dict[str, Any] | None) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        data = raw
    else:
        text = str(raw).strip()
        if not text:
            return None
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # 兼容纯文本：包成段落块
            return {
                "blocks": [
                    {"id": "legacy", "type": "paragraph", "text": text[:8000]},
                ]
            }
        if not isinstance(data, dict):
            return None
    blocks_in = data.get("blocks")
    if not isinstance(blocks_in, list):
        return None
    blocks: list[dict[str, Any]] = []
    for item in blocks_in[:MAX_BLOCKS]:
        if not isinstance(item, dict):
            continue
        cleaned = _clean_block(item)
        if cleaned:
            blocks.append(cleaned)
    if not blocks:
        return None
    return {"blocks": blocks}


def dumps_intro_body(body: dict[str, Any] | str | None) -> str | None:
    parsed = parse_intro_body(body)
    if not parsed:
        return None
    return json.dumps(parsed, ensure_ascii=False)


def community_to_out(community: Community, *, include_invite: bool = True) -> CommunityOut:
    return CommunityOut(
        id=community.id,
        name=community.name,
        slug=community.slug,
        description=community.description,
        logo_url=community.logo_url,
        homepage_url=community.homepage_url,
        mirror_doc_url=community.mirror_doc_url,
        gitea_org_url=community.gitea_org_url,
        status=community.status,
        invite_code=community.invite_code if include_invite else None,
        tags=parse_tags(getattr(community, "tags", None)),
        intro_body=parse_intro_body(getattr(community, "intro_body", None)),
    )
