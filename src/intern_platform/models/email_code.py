"""邮箱验证码（注册等）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from intern_platform.db.base import Base
from intern_platform.models.mixins import TimestampMixin


class EmailVerificationCode(TimestampMixin, Base):
    __tablename__ = "email_verification_codes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False, default="register")
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    send_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
