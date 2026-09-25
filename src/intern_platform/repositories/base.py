"""APPEND-ONLY 基类：仅 insert + query。"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from intern_platform.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class AppendOnlyRepository(Generic[ModelT]):
    """严格追加写仓库：禁止 update / delete API。"""

    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    def insert(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        self.session.flush()
        return entity

    def get(self, entity_id: int) -> ModelT | None:
        return self.session.get(self.model, entity_id)

    def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        order_by: Any | None = None,
    ) -> list[ModelT]:
        stmt = select(self.model)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        else:
            stmt = stmt.order_by(self.model.id.asc())  # type: ignore[attr-defined]
        stmt = stmt.offset(offset).limit(limit)
        return list(self.session.scalars(stmt).all())
