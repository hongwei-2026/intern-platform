"""FastAPI 应用入口。"""

from __future__ import annotations

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from intern_platform.api.routes import api_router
from intern_platform.config import get_settings
from intern_platform.dependencies.ledger import build_ledger_context


class LedgerContextMiddleware(BaseHTTPMiddleware):
    """为每个请求附着 request_id / trace_id / ip / ua。"""

    async def dispatch(self, request: Request, call_next) -> Response:  # noqa: ANN001
        ctx = build_ledger_context(
            request,
            x_request_id=request.headers.get("X-Request-ID"),
            x_trace_id=request.headers.get("X-Trace-ID"),
            x_idempotency_key=request.headers.get("X-Idempotency-Key"),
        )
        request.state.ledger = ctx
        response = await call_next(request)
        response.headers.setdefault("X-Request-ID", ctx.request_id)
        response.headers.setdefault("X-Trace-ID", ctx.trace_id)
        return response


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="华科开放原子开源实习管理系统",
        description="华科开源原子 · 开源实习管理系统 API",
        version="0.1.0",
    )
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Trace-ID"],
    )
    app.add_middleware(LedgerContextMiddleware)
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
