"""结束对接与终止合作申请。"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from intern_platform.db.base import Base
from intern_platform.models.mixins import CreatedAtMixin


class CooperationCase(CreatedAtMixin, Base):
    __tablename__ = "cooperation_cases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    community_id: Mapped[int] = mapped_column(ForeignKey("communities.id"), nullable=False, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # close | terminate
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # closed | pending | approved | rejected
    reason_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
