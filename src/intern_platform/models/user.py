"""用户模型。"""

from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from intern_platform.db.base import Base
from intern_platform.models.mixins import TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    school: Mapped[str | None] = mapped_column(String(128))
    github_id: Mapped[str | None] = mapped_column(String(128))
    gitea_id: Mapped[str | None] = mapped_column(String(128))
    gitcode_id: Mapped[str | None] = mapped_column(String(128))
    gitee_id: Mapped[str | None] = mapped_column(String(128))
    gitlink_id: Mapped[str | None] = mapped_column(String(128))
    # JSON: {"gitcode":"https://...avatar...","github":"..."}
    oauth_avatars: Mapped[str | None] = mapped_column(Text)
    member_no: Mapped[str | None] = mapped_column(String(64))
    bio: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(32))
    major: Mapped[str | None] = mapped_column(String(128))
    grade: Mapped[str | None] = mapped_column(String(64))
    degree: Mapped[str | None] = mapped_column(String(64))
    homepage_url: Mapped[str | None] = mapped_column(String(512))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(128))
    auth_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="local")
    external_subject: Mapped[str | None] = mapped_column(String(255))
    disabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")
