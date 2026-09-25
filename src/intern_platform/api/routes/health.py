"""健康检查路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from intern_platform import __version__
from intern_platform.config import get_settings
from intern_platform.db.session import get_db
from intern_platform.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    settings = get_settings()
    # 轻量探测连接
    db.execute(text("SELECT 1"))
    return HealthResponse(
        status="ok",
        ok=True,
        db_driver=settings.db_driver,
        app=settings.app_name,
        version=__version__,
    )
