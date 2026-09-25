"""profile bindings: gitcode/gitee/gitlink on users

Revision ID: 0004_profile_bindings
Revises: 0003_task3
Create Date: 2026-09-18 18:55:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_profile_bindings"
down_revision: Union[str, None] = "0003_task3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("gitcode_id", sa.String(length=128), nullable=True))
        batch.add_column(sa.Column("gitee_id", sa.String(length=128), nullable=True))
        batch.add_column(sa.Column("gitlink_id", sa.String(length=128), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("gitlink_id")
        batch.drop_column("gitee_id")
        batch.drop_column("gitcode_id")
