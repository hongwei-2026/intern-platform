"""申请模型。"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from intern_platform.db.base import Base
from intern_platform.models.mixins import TimestampMixin


class Application(TimestampMixin, Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("project_id", "student_id", name="uq_application_project_student"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    statement: Mapped[str | None] = mapped_column(Text)
    attachment_url: Mapped[str | None] = mapped_column(String(512))
    extra_fields: Mapped[str | None] = mapped_column(Text)  # JSON
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="draft", index=True)
    current_node: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    project = relationship("Project", back_populates="applications")
    student = relationship("User", foreign_keys=[student_id])
    review_records = relationship(
        "ReviewRecord",
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="ReviewRecord.id",
    )
    final_submission = relationship(
        "FinalSubmission",
        back_populates="application",
        uselist=False,
        cascade="all, delete-orphan",
    )
    messages = relationship(
        "ApplicationMessage",
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="ApplicationMessage.id",
    )
