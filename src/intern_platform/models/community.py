"""社区模型。"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from intern_platform.db.base import Base
from intern_platform.models.mixins import TimestampMixin


class Community(TimestampMixin, Base):
    __tablename__ = "communities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    logo_url: Mapped[str | None] = mapped_column(String(512))
    homepage_url: Mapped[str | None] = mapped_column(String(512))
    mirror_doc_url: Mapped[str | None] = mapped_column(String(512))
    gitea_org_url: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    applicant_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    review_comment: Mapped[str | None] = mapped_column(Text)
    invite_code: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    # 对外标签 JSON 数组，如 ["内核","驱动"]
    tags: Mapped[str | None] = mapped_column(Text)
    # 富文本介绍帖：JSON { blocks: [...] }，支持段落/标题/图片/表格/视频
    intro_body: Mapped[str | None] = mapped_column(Text)

    projects = relationship("Project", back_populates="community")
    extension = relationship(
        "CommunityExtension",
        back_populates="community",
        uselist=False,
        cascade="all, delete-orphan",
    )
