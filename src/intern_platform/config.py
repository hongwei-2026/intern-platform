"""应用配置：支持 SQLite / PostgreSQL / MySQL 切换。"""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录：intern-platform/
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """从环境变量 / .env 加载运行时配置。"""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="intern-platform", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    api_prefix: str = Field(default="/api/v1", alias="API_PREFIX")
    # 生产环境用 .env 里的随机 SECRET_KEY，不要使用默认占位符
    secret_key: str = Field(default="change-me-in-production", alias="SECRET_KEY")
    access_token_expire_minutes: int = Field(
        default=60 * 24, alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
        alias="CORS_ORIGINS",
    )
    # 浏览器可访问的前端 / API 根地址（OAuth 回调与跳转用）
    frontend_base: str = Field(default="http://127.0.0.1:5173", alias="FRONTEND_BASE")
    public_api_base: str = Field(default="http://127.0.0.1:8000", alias="PUBLIC_API_BASE")
    # 未配置 Client ID/Secret 时，开发环境可用本地「同意授权」模拟真实 OAuth UX
    oauth_dev_mock: bool = Field(default=True, alias="OAUTH_DEV_MOCK")

    github_client_id: str = Field(default="", alias="GITHUB_CLIENT_ID")
    github_client_secret: str = Field(default="", alias="GITHUB_CLIENT_SECRET")
    gitee_client_id: str = Field(default="", alias="GITEE_CLIENT_ID")
    gitee_client_secret: str = Field(default="", alias="GITEE_CLIENT_SECRET")
    gitcode_client_id: str = Field(default="", alias="GITCODE_CLIENT_ID")
    gitcode_client_secret: str = Field(default="", alias="GITCODE_CLIENT_SECRET")
    gitlink_client_id: str = Field(default="", alias="GITLINK_CLIENT_ID")
    gitlink_client_secret: str = Field(default="", alias="GITLINK_CLIENT_SECRET")
    gitea_base_url: str = Field(
        default="https://git.hust.openatom.club", alias="GITEA_BASE_URL"
    )
    gitea_client_id: str = Field(default="", alias="GITEA_CLIENT_ID")
    gitea_client_secret: str = Field(default="", alias="GITEA_CLIENT_SECRET")

    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_from: str = Field(default="", alias="SMTP_FROM")

    db_driver: Literal["sqlite", "postgres", "mysql"] = Field(
        default="sqlite", alias="DB_DRIVER"
    )
    database_url: str = Field(
        default="sqlite:///./data/intern.db", alias="DATABASE_URL"
    )

    @field_validator("db_driver", mode="before")
    @classmethod
    def normalize_driver(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    def resolve_database_url(self) -> str:
        """将相对 SQLite 路径解析为基于项目根的绝对路径。"""
        url = self.database_url
        if self.db_driver == "sqlite" and url.startswith("sqlite:///./"):
            relative = url.removeprefix("sqlite:///./")
            absolute = (PROJECT_ROOT / relative).resolve()
            absolute.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{absolute.as_posix()}"
        return url

    @property
    def sqlalchemy_echo(self) -> bool:
        return os.getenv("SQL_ECHO", "").lower() in {"1", "true", "yes"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
