"""users.disabled for committee account disable

Revision ID: 0012_user_disabled
Revises: 0011_audit_seq_unique
Create Date: 2026-10-05 18:40:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0012_user_disabled"
down_revision: Union[str, None] = "0011_audit_seq_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("users")}
    if "disabled" in cols:
        return
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("disabled", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("users")}
    if "disabled" not in cols:
        return
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("disabled")
