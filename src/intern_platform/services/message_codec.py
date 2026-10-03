"""申请留言 kind 编解码（兼容无 schema 迁移的存量库）。"""

from __future__ import annotations

import json
from typing import Any

KIND_TAGS: dict[str, str] = {
    "progress": "【进展】",
    "midterm": "【中期】",
    "feedback": "【反馈】",
    "acceptance": "【验收】",
    "official": "【社区通知】",
    "reward": "【奖励】",
}


def pack_message(kind: str, body: str) -> str:
    text = (body or "").strip()
    tag = KIND_TAGS.get(kind or "note", "")
    return f"{tag}{text}" if tag else text


def pack_deliverable_message(
    kind: str,
    *,
    text: str,
    design_doc_url: str = "",
    code_url: str = "",
    attachment_url: str = "",
    attachment_name: str = "",
) -> str:
    """进展/验收类留言：说明 + 链接 + ZIP 交付件。"""
    payload: dict[str, Any] = {
        "text": (text or "").strip(),
        "design_doc_url": (design_doc_url or "").strip(),
        "code_url": (code_url or "").strip(),
        "attachment_url": (attachment_url or "").strip(),
        "attachment_name": (attachment_name or "").strip(),
    }
    return pack_message(kind, json.dumps(payload, ensure_ascii=False))


def unpack_message(raw: str) -> tuple[str, str]:
    text = raw or ""
    for kind, tag in KIND_TAGS.items():
        if text.startswith(tag):
            return kind, text[len(tag) :].lstrip()
    return "note", text


def unpack_deliverable(raw: str) -> dict[str, Any]:
    """解析进展/验收结构化正文；旧纯文本则仅填 text。"""
    kind, body = unpack_message(raw)
    out: dict[str, Any] = {
        "kind": kind,
        "text": body,
        "design_doc_url": "",
        "code_url": "",
        "attachment_url": "",
        "attachment_name": "",
    }
    s = (body or "").strip()
    if s.startswith("{") and s.endswith("}"):
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                out["text"] = str(obj.get("text") or "").strip()
                out["design_doc_url"] = str(obj.get("design_doc_url") or "").strip()
                out["code_url"] = str(obj.get("code_url") or "").strip()
                out["attachment_url"] = str(obj.get("attachment_url") or "").strip()
                out["attachment_name"] = str(obj.get("attachment_name") or "").strip()
                out["decision"] = str(obj.get("decision") or "").strip()
                out["decision_note"] = str(obj.get("decision_note") or "").strip()
        except json.JSONDecodeError:
            pass
    return out
