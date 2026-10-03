"""数据库引擎与会话工厂。"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from intern_platform.config import get_settings

_settings = get_settings()
_url = _settings.resolve_database_url()

_connect_args: dict = {}
if _settings.db_driver == "sqlite":
    _connect_args = {"check_same_thread": False}

engine: Engine = create_engine(
    _url,
    echo=_settings.sqlalchemy_echo,
    future=True,
    connect_args=_connect_args,
)

if _settings.db_driver == "sqlite":

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：请求级会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
