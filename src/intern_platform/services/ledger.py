"""企业级流水账本：序号、哈希链、校验。"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from intern_platform.models.audit_log import AuditLog
from intern_platform.models.review_record import ReviewRecord
from intern_platform.models.workflow_event import WorkflowEvent

GENESIS_HASH = "0" * 64

LedgerKind = Literal["review", "audit", "workflow"]


def compute_event_hash(payload_dict: dict[str, Any]) -> str:
    """对 payload 做规范 JSON（按 key 排序）后计算 sha256 hex。"""
    canonical = json.dumps(
        payload_dict,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=_json_default,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _json_default(obj: Any) -> str:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def iso_ts(value: datetime | None) -> str | None:
    """归一化为 UTC 墙钟 + Z，避免 SQLite 丢掉 tzinfo 导致哈希不一致。"""
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def next_seq_review(session: Session, application_id: int) -> int:
    """同一 application_id 内单调递增序号。"""
    stmt: Select[tuple[int | None]] = select(func.max(ReviewRecord.seq_no)).where(
        ReviewRecord.application_id == application_id
    )
    current = session.scalar(stmt)
    return int(current or 0) + 1


def next_audit_link(session: Session) -> tuple[int, str]:
    """一次读出最新序号和哈希，登录等热路径不再查两遍。"""
    row = session.execute(
        select(AuditLog.seq_no, AuditLog.event_hash)
        .order_by(AuditLog.seq_no.desc())
        .limit(1)
    ).first()
    if row is None or row[0] is None:
        return 1, GENESIS_HASH
    return int(row[0]) + 1, row[1] or GENESIS_HASH


def next_seq_audit(session: Session) -> int:
    """全局单调递增序号（事务内 max+1）。"""
    seq_no, _prev = next_audit_link(session)
    return seq_no


def next_seq_workflow(session: Session, aggregate_type: str, aggregate_id: str) -> int:
    """同一 aggregate_type + aggregate_id 内单调递增序号。"""
    stmt = select(func.max(WorkflowEvent.seq_no)).where(
        WorkflowEvent.aggregate_type == aggregate_type,
        WorkflowEvent.aggregate_id == aggregate_id,
    )
    current = session.scalar(stmt)
    return int(current or 0) + 1


def get_prev_hash_audit(session: Session) -> str:
    _seq, prev = next_audit_link(session)
    return prev


def get_prev_hash_workflow(
    session: Session, aggregate_type: str, aggregate_id: str
) -> str:
    stmt = (
        select(WorkflowEvent.event_hash)
        .where(
            WorkflowEvent.aggregate_type == aggregate_type,
            WorkflowEvent.aggregate_id == aggregate_id,
        )
        .order_by(WorkflowEvent.seq_no.desc())
        .limit(1)
    )
    prev = session.scalar(stmt)
    return prev if prev else GENESIS_HASH


def build_audit_hash_payload(
    *,
    seq_no: int,
    prev_hash: str,
    action: str,
    resource_type: str,
    resource_id: str,
    actor_id: int | None,
    actor_role: str | None,
    outcome: str,
    request_id: str | None,
    trace_id: str | None,
    before_json: str | None,
    after_json: str | None,
    created_at: datetime,
) -> dict[str, Any]:
    return {
        "action": action,
        "actor_id": actor_id,
        "actor_role": actor_role,
        "after_json": after_json,
        "before_json": before_json,
        "created_at": iso_ts(created_at),
        "outcome": outcome,
        "prev_hash": prev_hash,
        "request_id": request_id,
        "resource_id": resource_id,
        "resource_type": resource_type,
        "seq_no": seq_no,
        "trace_id": trace_id,
    }


def build_workflow_hash_payload(
    *,
    seq_no: int,
    prev_hash: str,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload_json: str | None,
    actor_id: int | None,
    actor_role: str | None,
    request_id: str | None,
    occurred_at: datetime,
) -> dict[str, Any]:
    return {
        "actor_id": actor_id,
        "actor_role": actor_role,
        "aggregate_id": aggregate_id,
        "aggregate_type": aggregate_type,
        "event_type": event_type,
        "occurred_at": iso_ts(occurred_at),
        "payload_json": payload_json,
        "prev_hash": prev_hash,
        "request_id": request_id,
        "seq_no": seq_no,
    }


def verify_audit_chain(session: Session) -> tuple[bool, str | None]:
    """校验 audit_logs 全局哈希链；返回 (ok, error_message)。"""
    rows = list(
        session.scalars(select(AuditLog).order_by(AuditLog.seq_no.asc())).all()
    )
    if not rows:
        return True, None

    expected_prev = GENESIS_HASH
    expected_seq = 1
    for row in rows:
        if row.seq_no != expected_seq:
            return False, f"seq_no gap: expected {expected_seq}, got {row.seq_no}"
        if row.prev_hash != expected_prev:
            return (
                False,
                f"prev_hash mismatch at seq_no={row.seq_no}: "
                f"expected {expected_prev}, got {row.prev_hash}",
            )
        payload = build_audit_hash_payload(
            seq_no=row.seq_no,
            prev_hash=row.prev_hash,
            action=row.action,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            actor_id=row.actor_id,
            actor_role=row.actor_role,
            outcome=row.outcome,
            request_id=row.request_id,
            trace_id=row.trace_id,
            before_json=row.before_json,
            after_json=row.after_json,
            created_at=row.created_at,
        )
        recomputed = compute_event_hash(payload)
        if recomputed != row.event_hash:
            return (
                False,
                f"event_hash mismatch at seq_no={row.seq_no}: "
                f"expected {recomputed}, got {row.event_hash}",
            )
        expected_prev = row.event_hash
        expected_seq += 1
    return True, None


def decision_code_for(action: str) -> str:
    """将状态机 action 归一为决策码。"""
    lowered = action.lower()
    if lowered.startswith("approve"):
        return "APPROVE"
    if lowered.startswith("reject"):
        return "REJECT"
    if lowered.startswith("submit"):
        return "SUBMIT"
    if lowered.startswith("start"):
        return "START"
    return action.upper()


__all__ = [
    "GENESIS_HASH",
    "build_audit_hash_payload",
    "build_workflow_hash_payload",
    "compute_event_hash",
    "decision_code_for",
    "get_prev_hash_audit",
    "get_prev_hash_workflow",
    "iso_ts",
    "next_audit_link",
    "next_seq_audit",
    "next_seq_review",
    "next_seq_workflow",
    "verify_audit_chain",
]
