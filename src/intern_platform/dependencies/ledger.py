"""请求级账本上下文：request_id / trace_id / ip / ua。"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from fastapi import Header, Request


@dataclass(frozen=True)
class LedgerRequestContext:
    request_id: str
    trace_id: str
    ip: str | None
    user_agent: str | None
    idempotency_key: str | None


def build_ledger_context(
    request: Request,
    *,
    x_request_id: str | None = None,
    x_trace_id: str | None = None,
    x_idempotency_key: str | None = None,
) -> LedgerRequestContext:
    request_id = x_request_id or str(uuid4())
    trace_id = x_trace_id or request_id
    return LedgerRequestContext(
        request_id=request_id,
        trace_id=trace_id,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
        idempotency_key=x_idempotency_key,
    )


async def get_ledger_context(
    request: Request,
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
    x_trace_id: str | None = Header(default=None, alias="X-Trace-ID"),
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
) -> LedgerRequestContext:
    ctx = build_ledger_context(
        request,
        x_request_id=x_request_id,
        x_trace_id=x_trace_id,
        x_idempotency_key=x_idempotency_key,
    )
    request.state.ledger = ctx
    return ctx


def require_idempotency_key(key: str | None) -> str:
    if not key:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少幂等键 Idempotency-Key / X-Idempotency-Key",
        )
    return key
